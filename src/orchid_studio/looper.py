"""Software-clocked chord looper. No hardware output or incoming-clock dependency."""
import copy
import math
import threading
import time

from .midi import VIRTUAL_PORT, backend, exact_port
from .perform import PerformanceEngine, settings
from .sequencer import Player, compile_session, integer, number

DEFAULTS = {"bars": 4, "grid": .5, "count_in": 4}


def loop_settings(values):
    if not isinstance(values, dict) or set(values) - set(DEFAULTS):
        raise ValueError("loop settings are bars, grid and count_in")
    result = {**DEFAULTS, **values}
    integer(result['bars'], 1, 16, 'bars')
    if type(result['grid']) not in (int, float) or result['grid'] not in (0, .25, .5, 1):
        raise ValueError('grid must be 0 (free), .25, .5 or 1 beat')
    integer(result['count_in'], 0, 16, 'count_in')
    return result


def quantize(notes, length, grid):
    """Snap attacks/releases; group near-simultaneous chord notes before snapping.

    Caller supplies beat times. A fixed 0.12-beat grouping window protects chords
    arriving across adjacent polling batches or either side of a grid midpoint.
    """
    result = []
    anchor = None
    def snap(value):
        return math.floor(value / grid + .5 + 1e-9) * grid if grid else value
    for note in sorted(notes, key=lambda n: n['beat']):
        start = note['beat']
        if anchor is None or start - anchor > .12:
            anchor = start
        onset = min(length - (grid or .001), max(0, snap(anchor if grid else start)))
        end = min(length, max(onset + (grid or .01), snap(start + note['duration'])))
        result.append({**note, 'beat': onset, 'duration': end - onset})
    # Coalesce same-pitch collisions after snapping; never create ambiguous overlaps.
    merged = []
    for pitch in sorted({n['note'] for n in result}):
        previous = None
        for note in sorted((n for n in result if n['note'] == pitch), key=lambda n:n['beat']):
            if previous and note['beat'] < previous['beat'] + previous['duration'] - 1e-9:
                end = max(note['beat'] + note['duration'], previous['beat'] + previous['duration'])
                previous['duration'] = end - previous['beat']
            else:
                previous = dict(note)
                merged.append(previous)
    return sorted(merged, key=lambda n:(n['beat'], n['note']))


def render(notes, length, config):
    """Bake a snapped chord clip through the existing Perform engine in beat time."""
    config = settings({**config, 'bpm': 60, 'chord_window_ms': 0})
    incoming = []
    for n in notes:
        incoming.extend(((n['beat'], (0x90, n['note'], n['velocity'])),
                         (n['beat'] + n['duration'], (0x80, n['note'], 0))))
    incoming.sort(key=lambda e:(e[0], e[1][0] != 0x80))
    active, output = {}, []
    now = 0
    def send(msg):
        if msg[0] & 0xF0 == 0x90 and msg[2]:
            active[msg[1]] = (now, msg[2])
        elif msg[0] & 0xF0 == 0x80 and msg[1] in active:
            start, velocity = active.pop(msg[1])
            if now - start > 1e-8:
                output.append({'beat':start, 'duration':now-start, 'note':msg[1], 'velocity':velocity})
    engine = PerformanceEngine(send, 1, 1, config, 0)
    # Include exact input timestamps in addition to the 96 PPQN rendering grid.
    times = sorted({i / 96 for i in range(round(length * 96) + 1)} | {t for t, _ in incoming})
    cursor = 0
    for now in times:
        if now >= length:
            break
        engine._clock(now)
        while cursor < len(incoming) and incoming[cursor][0] <= now + 1e-9:
            engine.receive(incoming[cursor][1], now)
            cursor += 1
        engine.advance(now)
    now = length
    engine.panic()
    return sorted(output, key=lambda n:(n['beat'], n['note']))


class Voices:
    """Shared-pitch ownership prevents a layer release from cutting another layer."""
    def __init__(self, send, channel):
        self.send, self.channel = send, channel - 1
        self.owners = {}

    def receive(self, owner, msg):
        kind = msg[0] & 0xF0
        if kind not in (0x80, 0x90):
            return  # Engine-local panic must not silence other layers.
        pitch = msg[1]
        owners = self.owners.setdefault(pitch, set())
        if kind == 0x90 and msg[2]:
            if not owners:
                self.send([0x90 | self.channel, pitch, msg[2]])
            owners.add(owner)
        else:
            owners.discard(owner)
            if not owners:
                self.send([0x80 | self.channel, pitch, 0])
                self.owners.pop(pitch, None)

    def release(self, owner):
        for pitch, owners in list(self.owners.items()):
            if owner in owners:
                self.receive(owner, [0x80, pitch, 0])

    def panic(self):
        player = Player(self.send, {self.channel})
        player.active = {(self.channel, p) for p in self.owners}
        try:
            player.panic()
        finally:
            self.owners.clear()


class LayerVoices:
    """Each AU owns its notes; live monitoring has a separate channel outside recording."""
    def __init__(self, router):
        self.router = router
        self.voices = [Voices(lambda m, slot=i+1: router.send_layer(slot,m),1) for i in range(5)]
        self.monitor_slot=5

    def receive(self, owner, message):
        index = self.monitor_slot-1 if owner == 'monitor' else owner
        self.voices[index].receive(owner,message)

    def release(self, owner):
        for voice in self.voices:
            voice.release(owner)

    def panic(self):
        errors=[]
        for voice in self.voices:
            try:voice.panic()
            except Exception as exc:errors.append(exc)
        if errors:raise RuntimeError('layer MIDI cleanup failed') from errors[0]


class Looper:
    def __init__(self, send, report, drums=None):
        self.send, self.report, self.drums = send, report, drums
        self.clock_output=None
        self.tempo_tick=None
        self.timeline=None
        self.router = None
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.worker = None
        self.config = dict(DEFAULTS)
        self.perform = settings({})
        self.layers = [self.empty(i) for i in range(4)]
        self.undo_layers = None
        self.take = None
        self.pending_compose = None  # a composition waiting for the next loop boundary (loop-compose)
        self.beat = 0.
        self.held = {}
        self.error = None
        self.bus = None
        self.drum_config = None
        self.live_config=None
        self.start_on_key=False
        self.wait_for_key=False
        self.key_start_timing=None

    @staticmethod
    def empty(i):
        return {'slot':i + 1, 'name':f'Layer {i + 1}', 'muted':False, 'chords':[], 'notes':[], 'settings':None}

    @property
    def playing(self):
        return self.worker is not None and self.worker.is_alive()

    @property
    def length(self):
        return self.config['bars'] * 4

    def snapshot(self):
        with self.lock:
            return {'running':self.playing, 'settings':dict(self.config), 'bpm':self.perform['bpm'],
                    'beat':round(self.beat, 3), 'position':round(max(0,self.beat) % self.length, 3),
                    'phase':('paused' if self.timeline and self.timeline.paused else 'count-in' if self.beat < 0 else 'recording' if self.take and self.beat >= self.take['start'] else 'armed' if self.take else 'playing') if self.playing else 'stopped',
                    'record_slot':self.take['slot'] + 1 if self.take else None,
                    'beats_until_record':round(max(0,self.take['start']-self.beat),3) if self.take else None,
                    'key_start_timing':copy.deepcopy(self.key_start_timing),
                    'start_on_key':self.start_on_key, 'waiting_for_key':bool(self.start_on_key and self.timeline and self.timeline.paused),
                    'held_notes':sorted(self.held), 'undo_available':self.undo_layers is not None,
                    'error':self.error,
                    'layers':[{k:v for k,v in layer.items() if k not in ('notes','chords','settings')} |
                              {'note_count':len(layer['notes']), 'chord_note_count':len(layer['chords']),
                               'mode':layer['settings']['mode'] if layer['settings'] else None,
                               'notes':[{k:n[k] for k in ('beat','duration','note','velocity')} for n in layer['notes']]} for layer in self.layers]}

    def configure(self, values):
        config = loop_settings({**self.config, **values})
        with self.lock:
            if self.playing:
                raise ValueError('stop loops before changing loop length or quantization')
            if config['bars'] != self.config['bars'] and any(l['notes'] for l in self.layers):
                raise ValueError('clear all layers before changing loop length')
            if config['bars'] != self.config['bars']:
                self.undo_layers = None
            self.config = config

    def arm(self, slot, config):
        index = integer(slot, 1, 4, 'slot') - 1
        config = settings(config)
        with self.lock:
            if not self.playing:
                raise ValueError('start the looper before arming a take')
            if self.take:
                raise ValueError('a take is already armed; cancel it first')
            start = 0 if self.beat < 0 else (math.floor(self.beat / self.length) + 1) * self.length
            self.take = {'slot':index, 'start':start, 'active':{}, 'notes':[], 'settings':config, 'started':False}

    def _finish_note(self, pitch, beat):
        start, velocity = self.take['active'].pop(pitch)
        self.take['notes'].append({'beat':start, 'duration':max(.001,min(self.length,beat-self.take['start'])-start), 'note':pitch, 'velocity':velocity})

    def _record(self, msg):
        t = self.take
        if not t or not t['started'] or not t['start'] <= self.beat < t['start'] + self.length:
            return
        pitch = msg[1]
        if pitch in t['active']:
            self._finish_note(pitch, self.beat)
        if msg[0] & 0xF0 == 0x90 and msg[2]:
            t['active'][pitch] = (max(0,self.beat-t['start']),msg[2])

    def _compose(self, request):
        """Replace one layer with a whole composition: chords at beats, each {beat, duration, notes, velocity?}. While
        the loops play it takes over at the next loop boundary, so a pass in progress plays on undisturbed (for
        example a live take of the same music, which the composition then repeats exactly); stopped, at once.
        Caller holds the lock."""
        index = integer(request.get('slot'),1,4,'slot')-1
        chords = request.get('chords')
        if not isinstance(chords,list) or not 1 <= len(chords) <= 512:
            raise ValueError('chords must list 1–512 chords')
        entries = []
        for chord in chords:
            if not isinstance(chord,dict):
                raise ValueError('each chord needs beat, duration and notes')
            pitches = chord.get('notes')
            if not isinstance(pitches,list) or not 1 <= len(pitches) <= 16:
                raise ValueError('each chord needs 1–16 MIDI pitches')
            beat = number(chord.get('beat'),0,self.length-.001,'beat')
            duration = min(number(chord.get('duration',1),.125,64,'duration'), self.length-beat)  # held to the loop's end at most
            velocity = integer(chord.get('velocity',80),1,127,'velocity')
            entries += [{'beat':beat,'duration':duration,'note':integer(p,0,127,'note'),'velocity':velocity} for p in sorted(set(pitches))]
        config = settings(request.get('settings',self.perform))
        entries = quantize(entries,self.length,self.config['grid'])
        if len(entries) > 2048:
            raise ValueError('a layer supports at most 2048 chord notes')
        if self.playing:
            boundary = (math.floor(max(0,self.beat)/self.length)+1)*self.length
            self.pending_compose = {'index':index,'chords':entries,'config':config,'at':boundary}
            return {'slot':index+1,'applies_at_beat':boundary,'chord_notes':len(entries)}
        self._commit(index,entries,config)
        return {'slot':index+1,'applies_at_beat':None,'chord_notes':len(entries)}

    def _land_compose(self):
        """A waiting composition takes over its layer once the loop reaches its boundary. Caller holds the lock."""
        compose = self.pending_compose
        if compose and self.beat >= compose['at']:
            self.pending_compose = None
            if self.bus:
                self.bus.release(compose['index'])
            self._commit(compose['index'],compose['chords'],compose['config'])
            self.report({'event':'loop_composed','slot':compose['index']+1,'beat':compose['at']})

    def _commit(self, index, chords, config):
        if len(chords) > 2048:
            raise ValueError('a layer supports at most 2048 chord notes')
        notes = render(chords, self.length, config)
        self.undo_layers = copy.deepcopy(self.layers)
        self.layers[index] = {**self.layers[index], 'chords':chords, 'notes':notes, 'settings':dict(config)}

    def edit(self, action, request):
        with self.lock:
            if action == 'cancel':
                self.take = None
                return
            if action == 'mute':
                index = integer(request.get('slot'),1,4,'slot')-1
                muted = request.get('muted')
                if type(muted) is not bool:
                    raise ValueError('muted must be true or false')
                self.layers[index]['muted'] = muted
                if muted and self.bus:
                    self.bus.release(index)
                return
            if action == 'clear':
                slot = request.get('slot')
                if slot is not None:integer(slot,1,4,'slot')
                if self.take:raise ValueError('finish or cancel the take before clearing a layer')
                indices=[i for i,layer in enumerate(self.layers)
                         if (slot is None or slot==i+1) and (layer['notes'] or layer['chords'])]
                if not indices:return
                self.undo_layers=copy.deepcopy(self.layers)
                for index in indices:
                    if self.bus:self.bus.release(index)
                    self.layers[index]=self.empty(index)
                return
            if action == 'compose':
                return self._compose(request)
            if self.playing:
                raise ValueError('stop loops before step editing, undoing or importing; takes record live')
            if action == 'undo':
                if self.undo_layers is None:
                    raise ValueError('nothing to undo')
                self.layers, self.undo_layers = self.undo_layers, self.layers
            elif action == 'step':
                index = integer(request.get('slot'),1,4,'slot')-1
                pitches = request.get('notes')
                if not isinstance(pitches,list) or not 1 <= len(pitches) <= 16:
                    raise ValueError('notes must contain 1–16 MIDI pitches')
                pitches = sorted({integer(p,0,127,'note') for p in pitches})
                beat = number(request.get('beat'),0,self.length-.001,'beat')
                duration = number(request.get('duration',4),.125,self.length-beat,'duration')
                velocity = integer(request.get('velocity',64),1,127,'velocity')
                config = settings(request.get('settings',self.perform))
                old = self.layers[index]
                if old['settings'] and any(config[k] != old['settings'][k] for k in config if k != 'bpm'):
                    raise ValueError('use the same Perform settings within a layer; clear it to change mode')
                chords = quantize(old['chords'] + [{'beat':beat,'duration':duration,'note':p,'velocity':velocity} for p in pitches], self.length,self.config['grid'])
                self._commit(index,chords,config)
                self.perform = config
            else:
                raise ValueError('unknown loop edit')

    def export(self):
        with self.lock:
            return {'version':1, 'kind':'orchid-loops', 'settings':dict(self.config),
                    'performance':dict(self.perform), 'layers':copy.deepcopy(self.layers)}

    def restore(self, document):
        if not isinstance(document,dict) or document.get('version') != 1 or document.get('kind') != 'orchid-loops':
            raise ValueError('expected an orchid-loops version 1 document')
        config = loop_settings(document.get('settings'))
        performance = settings(document.get('performance'))
        layers = document.get('layers')
        if not isinstance(layers,list) or len(layers) != 4:
            raise ValueError('document must have four layers')
        validated = []
        for i,layer in enumerate(layers):
            if not isinstance(layer,dict) or type(layer.get('muted')) is not bool:
                raise ValueError('each layer needs a muted boolean')
            chords = layer.get('chords')
            compile_session({'version':1,'bpm':performance['bpm'],'length_beats':config['bars']*4,
                             'tracks':[{'name':'chords','channel':1,'notes':chords}]})
            if len(chords)>2048:
                raise ValueError('a layer supports at most 2048 chord notes')
            layer_config = settings(layer['settings']) if layer.get('settings') is not None else None
            if chords and layer_config is None:
                raise ValueError('nonempty layer needs Perform settings')
            validated.append({**self.empty(i), 'muted':layer['muted'], 'chords':copy.deepcopy(chords),
                              'settings':layer_config, 'notes':render(chords,config['bars']*4,layer_config) if chords else []})
        with self.lock:
            if self.playing:
                raise ValueError('stop before importing loops')
            # Undo is scoped to takes/edits with one loop length.
            self.config,self.perform,self.layers,self.undo_layers = config,performance,validated,None

    def start(self, *, input_name, chord_channel, output_channel, config, drum_config=None, record_slot=None, wait_for_key=False):
        if not isinstance(input_name,str) or not input_name.strip() or input_name == VIRTUAL_PORT:
            raise ValueError('loop-start needs an exact physical input')
        integer(chord_channel,1,16,'chord_channel');integer(output_channel,1,16,'output_channel')
        config = settings(config)
        if record_slot is not None:
            integer(record_slot,1,4,'slot')
        if drum_config is not None and self.drums is None:
            raise ValueError('drums require serve --hydrogen')
        if drum_config is not None and hasattr(self.drums, "prepare"):
            self.drums.prepare(drum_config)
        # Open before stopping existing loop playback so a missing input is harmless.
        source = backend().MidiIn()
        try:
            source.open_port(exact_port(source.get_ports(),input_name))
            source.ignore_types(sysex=True,timing=True,active_sense=True)
        except Exception:
            source.close_port();source.delete()
            raise
        self.stop()
        with self.lock:
            self.stop_event.clear();self.error=None;self.held={}
            self.start_on_key=wait_for_key;self.wait_for_key=wait_for_key;self.key_start_timing=None
            self.perform=config;self.live_config=dict(config);self.drum_config=drum_config;self._input_name=input_name
            self.beat=-self.config['count_in'] if record_slot else 0
            self.take = {'slot':record_slot-1,'start':0,'active':{},'notes':[], 'settings':dict(config),'started':False} if record_slot else None
        self.worker=threading.Thread(target=self._run,args=(source,chord_channel,output_channel),name='orchid-looper')
        self.worker.start()

    def stop(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join()
            self.worker=None
        with self.lock:
            self.take=None
            self.held={}
            self.start_on_key=False;self.wait_for_key=False

    def _paused_input(self, source, chord_channel, clock=time.monotonic):
        """Drain paused input; retain the fresh attack that wakes the transport."""
        for _ in range(256):
            packet=source.get_message()
            if packet is None:break
            msg=packet[0]
            if len(msg)!=3 or msg[0]&15!=chord_channel-1:continue
            kind=msg[0]&0xF0
            if kind not in (0x80,0x90):continue
            fresh=kind==0x90 and msg[2]>0 and msg[1] not in self.held
            if kind==0x90 and msg[2]>0:self.held[msg[1]]=msg[2]
            else:self.held.pop(msg[1],None)
            if fresh and self.start_on_key:
                self.key_start_timing={'note':msg[1],'received_at_monotonic':clock(),
                    'midi_to_live_send_ms':None,'midi_to_loop_send_ms':None,'excludes':'Orchid scanning, synth attack and audio/Bluetooth output buffering'}
                self.timeline.pause(False)
                if self.clock_output:self.clock_output.pause(False)
                self.report({'event':'loop_key_started','note':msg[1],'chord_channel':chord_channel})
                return [msg]
        return []

    def _run(self,source,chord_channel,output_channel,clock=time.monotonic):
        self.bus=LayerVoices(self.router) if self.router and self.router.host else Voices(self.send,output_channel)
        if self.clock_output:self.clock_output.begin()
        origin=clock()
        # Count-in prepares a recording take, not playback of an existing song.
        start_beat=-self.config['count_in'] if self.take else 0
        if self.timeline:
            self.timeline.reset(self.perform["bpm"],start_beat)
            if self.wait_for_key:
                self.timeline.pause(True)
                if self.clock_output:self.clock_output.pause(True)
        self.wait_for_key=False
        def monitor_send(message):
            self.bus.receive('monitor',message)
            timing=self.key_start_timing
            if timing and timing['midi_to_live_send_ms'] is None and message[0]&0xF0==0x90 and message[2]>0:
                timing['midi_to_live_send_ms']=round(max(0,clock()-timing['received_at_monotonic'])*1000,3)
                self.report({'event':'key_live_dispatched',**timing})
        monitor=PerformanceEngine(monitor_send,chord_channel,1,self.perform,origin)
        monitor.timeline=self.timeline
        was_paused=False
        previous=-1e-8
        drums_started=False
        next_check=origin+1
        try:
            self.report({'event':'loop_ready','settings':self.config,'bpm':self.perform['bpm']})
            while not self.stop_event.is_set():
                now=clock()
                if self.tempo_tick:self.tempo_tick()
                with self.lock:
                    wake_messages=[]
                    if self.timeline and self.timeline.paused:
                        if not was_paused:
                            self.bus.panic();monitor.panic();was_paused=True
                            if self.drums:self.drums.client.command('stop')
                        wake_messages=self._paused_input(source,chord_channel,clock)
                        if not wake_messages:
                            self.stop_event.wait(.002);continue
                    self.beat=self.timeline.position(now) if self.timeline else (now-origin)*self.perform['bpm']/60+start_beat
                    if was_paused:
                        # Revoice notes spanning the paused cursor without restarting the loop.
                        position=max(0,self.beat)%self.length
                        for index,layer in enumerate(self.layers):
                            if previous>=0 and not layer['muted']:
                                for n in layer['notes']:
                                    if n['beat']<position<n['beat']+n['duration']:self.bus.receive(index,[0x90,n['note'],n['velocity']])
                        was_paused=False
                    if self.clock_output:self.clock_output.advance(self.beat,self.timeline.bpm if self.timeline else self.perform['bpm'])
                    if self.beat>=0 and not drums_started:
                        if self.drum_config:
                            self.drums.start(self.perform['bpm'],self.drum_config)
                        drums_started=True
                    if self.take and self.beat >= self.take['start'] and not self.take['started']:
                        self.take['started']=True
                        self.bus.release(self.take['slot'])
                        self.take['active']={p:(0,v) for p,v in self.held.items()}
                        monitor.update(self.take['settings'],now)
                    if self.take and self.beat >= self.take['start']+self.length:
                        for pitch in list(self.take['active']):
                            self._finish_note(pitch,self.take['start']+self.length)
                        take=self.take; self.take=None
                        if take['notes']:
                            self._commit(take['slot'],quantize(take['notes'],self.length,self.config['grid']),take['settings'])
                        monitor.panic() # Held keys do not double the newly completed take.
                        self.report({'event':'loop_take_complete','slot':take['slot']+1,'empty':not bool(take['notes'])})
                    self._land_compose()
                    if not self.take and self.live_config and any(monitor.config[k]!=v for k,v in self.live_config.items() if k!='bpm'):
                        monitor.update({**self.live_config,'bpm':self.perform['bpm']},now)
                    if isinstance(self.bus,LayerVoices):self.bus.monitor_slot=self.take['slot']+1 if self.take else 5
                    for _ in range(256):
                        if wake_messages:msg=wake_messages.pop(0)
                        else:
                            packet=source.get_message()
                            if packet is None:break
                            msg=packet[0]
                        if len(msg)!=3 or msg[0]&15!=chord_channel-1 or msg[0]&0xF0 not in (0x80,0x90):
                            continue
                        if msg[0]&0xF0==0x90 and msg[2]:
                            self.held[msg[1]]=msg[2]
                        else:
                            self.held.pop(msg[1],None)
                        self._record(msg)
                        monitor.receive(msg,now)
                    monitor.advance(now)
                    if self.beat>=0:
                        # Process releases before attacks; skip stale attacks after a stalled worker.
                        due=[]
                        for index,layer in enumerate(self.layers):
                            if layer['muted'] or (self.take and self.take['started'] and self.take['slot'] == index):
                                continue
                            first=max(0,math.floor(previous/self.length))
                            last=math.floor(self.beat/self.length)
                            if last-first>1:
                                self.bus.release(index);first=last
                            for cycle in range(first,last+1):
                                for n in layer['notes']:
                                    start=cycle*self.length+n['beat'];end=start+n['duration']
                                    if previous < end <= self.beat:
                                        due.append((end,0,index,n))
                                    if previous < start <= self.beat and self.beat-start <= .1*self.perform['bpm']/60 and end>self.beat:
                                        due.append((start,1,index,n))
                        for _,attack,index,n in sorted(due,key=lambda e:(e[0],e[1])):
                            self.bus.receive(index,[0x90 if attack else 0x80,n['note'],n['velocity'] if attack else 0])
                            timing=self.key_start_timing
                            if attack and timing and timing['midi_to_loop_send_ms'] is None:
                                timing['midi_to_loop_send_ms']=round(max(0,clock()-timing['received_at_monotonic'])*1000,3)
                                self.report({'event':'key_loop_dispatched',**timing})
                        if self.drum_config:
                            self.drums.advance(self.beat)
                        previous=self.beat
                if now>=next_check:
                    exact_port(source.get_ports(),self._input_name)
                    next_check=now+1
                self.stop_event.wait(.002)
        except Exception as exc:
            self.error=str(exc)
            self.report({'event':'playback_error','error':str(exc)})
        finally:
            if self.clock_output:self.clock_output.stop()
            try:
                self.bus.panic()
            finally:
                try:
                    if self.drum_config:
                        self.drums.stop()
                finally:
                    source.close_port();source.delete()
                    self.take=None;self.held={};self.bus=None
                    self.report({'event':'stopped','cleanup':'sent'})
