"""Shared control API for JSON lines and a bounded loopback-only HTTP server."""
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import threading
import tarfile
import xml.etree.ElementTree as ET
import copy

from .beats import BANK_NAME, catalog, get_beat
from .drum_song import validate_beat_bank
from .hydrogen import command_message
from .perform import options, settings
from .sequencer import demo_session, integer, number
from .service import Transport
from .control_reference import reference, UI_MAP, BEAT_EDITOR

COMMANDS = ("status", "capabilities", "events", "perform-options", "perform-configure",
            "perform", "perform-update", "demo", "play", "drums", "beats-list",
            "beats-load", "beats-select", "beats-play", "sound-follow", "stop", "panic", "quit",
            "loop-configure", "loop-start", "loop-record", "loop-cancel", "loop-mute",
            "loop-step", "loop-clear", "loop-undo", "loop-export", "loop-import",
            "pistil-enable", "pistil-status", "layer-select", "layer-editor", "layer-preset",
            "beat-get", "beat-save", "kits-list", "kits-import", "sample-upload", "sound-preview", "clock-configure", "drums-length", "tempo", "mixer-set", "pause", "resume", "play-along", "beat-edit", "sounds-list", "command-help", "key-start", "key-monitor", "key-events")


class Controller:
    def __init__(self, send, report, drums=None, *, drum_bank=None, drum_library=None):
        self.lock = threading.Lock()
        self.event_lock = threading.Lock()
        self.events = deque(maxlen=256)
        self.event_id = 0
        self.closed = threading.Event()
        self.report_output = report
        self.send_lock = threading.Lock()
        def software_send(message):
            with self.send_lock:
                send(message)
        from .pistil_host import SoundRouter
        self.sounds = SoundRouter(software_send)
        self.software_send = self.sounds.send_live
        self.sound_follower = None
        self.key_monitor = None
        self.midi_connection = None
        from .drum_sequencer import StudioDrums
        from .drum_library import DrumLibrary
        self.library = drum_library or DrumLibrary()
        self.transport = Transport(self.software_send, self.report,
                                   StudioDrums(drums, self.library) if drums is not None else None)
        self.transport.looper.router = self.sounds
        from .play_along import PlayAlong
        self.play_along = PlayAlong(lambda m:self.sounds.send_layer(6,m),self.report,
            lambda:self.transport.playing and not self.transport.timeline.paused)
        self.transport.tempo_sink = self._send_tempo
        self.defaults = settings({})
        self.bank_path = validate_beat_bank(drum_bank) if drum_bank else None
        self.bank_requested = False
        self.selected_beat = None
        self.drum_state = {"playing_requested": False, "bpm": 96, "volume": .3, "pattern": None}

    def report(self, value):
        if value.get("event") in ("completed", "stopped", "playback_error") and hasattr(self, "drum_state"):
            self.drum_state["playing_requested"] = False
            self.transport.timeline.stop()
        with self.event_lock:
            self.event_id += 1
            event = {**value, "event_id": self.event_id}
            self.events.append(event)
        self.report_output(event)

    def snapshot(self):
        live = self.transport.live
        from .paths import data_dir, host_path
        input_name = (self.sound_follower.input_name if self.sound_follower else
                      live.input_name if live else self.play_along.state.get('input') or 'Orchid')
        connection = self.midi_connection.snapshot(input_name) if self.midi_connection else {
            'input':input_name,'connected':None,'state':'unknown','error':None,'stale':True}
        return {"playing": self.transport.playing,
                "storage":{"data_dir":str(data_dir()),"host_path":str(host_path())},
                "orchid_connection":connection,
                "tempo":self.transport.timeline.snapshot(),
                "mixer":copy.deepcopy(self.sounds.mix),
                "play_along":dict(self.play_along.state),
                "midi_clock":self.transport.clock_output.snapshot(),
                "sound_follow": dict(self.sound_follower.state) if self.sound_follower else {"enabled": False},
                "key_monitor": dict(self.key_monitor.state) if self.key_monitor else {"enabled": False},
                "performance": {"input": live.input_name, "chord_channel": live.chord_channel,
                                "output_channel": live.output_channel, "settings": {**live.config,"bpm":self.transport.timeline.target_bpm},
                                "pending_updates": live.updates.qsize()} if live else None,
                "performance_defaults": dict(self.defaults),
                "looper": self.transport.looper.snapshot(),
                "instruments": self.sounds.snapshot(),
                "hydrogen_enabled": self.transport.drums is not None and getattr(self.transport.drums.client,"native_audio",False) is not True,
                "drums_enabled": self.transport.drums is not None,
                "drums": {**self.drum_state, "beat": self.selected_beat, "bank_path": self.bank_path,
                          "bank_load_requested": self.bank_requested, "confirmed": False,
                          "sequencer": self.transport.drums.snapshot() if self.transport.drums else None},
                "last_event_id": self.event_id,
                "synchronization": "Studio owns the beat timeline; native drums and Pistil share one audio engine when the native host is enabled"}

    def _select_layer(self, slot, arming=False):
        integer(slot,1,6,'slot')
        looper = self.transport.looper
        with looper.lock:
            if looper.take and not arming and slot != looper.take['slot']+1:
                raise ValueError('finish or cancel the take before selecting another sound layer')
            if looper.bus and slot != self.sounds.selected:
                looper.bus.release('monitor')
            self.sounds.select(slot)

    def _send_tempo(self, bpm):
        if self.sounds.healthy():self.sounds.host.call('tempo',bpm=bpm,wait=False)

    def _set_tempo(self, value, transition_seconds=2):
        bpm=number(value,30,300,'bpm')
        self.transport.set_tempo(bpm,transition_seconds)
        self.defaults['bpm']=bpm;self.drum_state['bpm']=bpm
        if self.sounds.healthy():self.sounds.host.call('tempo',bpm=self.transport.timeline.bpm)
        return bpm

    def _audio_ready(self):
        if self.sounds.host:
            if not self.sounds.healthy():
                result=self._execute({'command':'pistil-enable'})
                self.report({'event':'audio_recovered','restored':'last saved sound checkpoint'})
            self.sounds.capture()

    def _drums(self):
        if self.transport.drums is None:
            raise ValueError("Hydrogen control requires serve --hydrogen")
        return self.transport.drums

    def _beat(self, identifier):
        beat = next((b for b in self.library.catalog() if b["id"]==identifier), None)
        if beat is None:
            raise ValueError("unknown beat; use beats-list")
        if not self.bank_requested:
            raise ValueError("load the electronic bank with beats-load before selecting a named beat")
        return beat

    def _resolve_drums(self, value):
        if not isinstance(value, dict) or "beat" not in value:
            return value
        if "pattern" in value:
            raise ValueError("use drums.beat or drums.pattern, not both")
        beat = self._beat(value["beat"])
        self._drums().prepare({"pattern":beat["pattern"]})
        return {**{k: v for k, v in value.items() if k != "beat"}, "pattern": beat["pattern"]}

    def execute(self, request):
        with self.lock:
            request_id = request.get("id") if isinstance(request, dict) else None
            try:
                if not isinstance(request, dict):
                    raise ValueError("request must be a JSON object")
                if self.closed.is_set():
                    raise ValueError("service is closing")
                result = self._execute(request)
                return {"id": request_id, **result}
            except (ValueError, TypeError, RuntimeError, OSError, ET.ParseError, tarfile.TarError) as exc:
                return {"id": request_id, "status": "error", "error": str(exc)}

    def _execute(self, request):
        command = request.get("command")
        transport = self.transport
        if command == 'command-help':
            return {'status':'ok','commands':reference(request.get('name')),'ui_map':copy.deepcopy(UI_MAP),'beat_editor':copy.deepcopy(BEAT_EDITOR)}
        if command == 'sounds-list':
            from .catalog import sounds
            return {'status':'ok',**sounds(),'drum_sounds':self.library.sound_list(),'kits':copy.deepcopy(self.library.kits)}
        if command == 'beat-edit':
            from .beat_edit import edit
            if ('document' in request)==('beat' in request):raise ValueError('supply document or beat, not both')
            document=request['document'] if 'document' in request else self.library.get(request['beat'])
            return {'status':'ok',**edit(document,request,self.library.sounds)}
        if command == 'key-start':
            enabled=request.get('enabled')
            if type(enabled) is not bool:raise ValueError('enabled must be boolean')
            looper=transport.looper
            if looper.take:raise ValueError('finish or cancel the take before changing key start')
            if enabled and not looper.playing:
                if transport.playing:raise ValueError('stop other playback before arming key start')
                self._execute({**request,'command':'loop-start','wait_for_key':True})
            with looper.lock:looper.start_on_key=enabled
            return {'status':'ok','looper':looper.snapshot()}
        if command == 'drums-length':
            result=self._drums().set_length(request.get('bars'),self.selected_beat)
            return {**result,'sequencer':self._drums().snapshot()}
        if command == 'tempo':
            self._set_tempo(request.get('bpm'),request.get('transition_seconds',2))
            return {'status':'ok','tempo':transport.timeline.snapshot()}
        if command in ('pause','resume'):
            transport.pause(command=='pause')
            if command=='pause':self.sounds.panic()
            return {'status':'ok','tempo':transport.timeline.snapshot()}
        if command == 'play-along':
            if not self.sounds.healthy():raise ValueError('enable native Pistil audio for play-along')
            self.play_along.configure(request.get('enabled'),
                request.get('input',self.play_along.state['input']),
                request.get('chord_channel',self.play_along.state['chord_channel']),
                request.get('velocity_limit',self.play_along.state['velocity_limit']))
            return {'status':'ok','play_along':dict(self.play_along.state)}
        if command == 'mixer-set':
            if not self.sounds.healthy():raise ValueError('enable native audio for independent mixer controls')
            target=request.get('channel');values={k:request[k] for k in ('volume','pan') if k in request}
            if not values:raise ValueError('supply volume or pan')
            self.sounds.set_mix(target,values)
            if target=='drums' and 'volume' in values:
                self._drums().command('volume',values['volume']);self.drum_state['volume']=values['volume']
            return {'status':'ok','mixer':copy.deepcopy(self.sounds.mix)}
        if command == "clock-configure":
            if transport.playing:raise ValueError("stop playback before changing MIDI clock output")
            return {"status":"ok", "midi_clock":transport.clock_output.configure(request.get("enabled"),request.get("offset_ms",40))}
        if command == "status":
            return {"status": "ok", **self.snapshot()}
        if command in ("capabilities", "perform-options"):
            return {"status": "ok", "api_version": 1, "commands": list(COMMANDS), "command_reference": reference(), "ui_map":copy.deepcopy(UI_MAP), "beat_editor":copy.deepcopy(BEAT_EDITOR), **options(),
                    "looper": {"slots": 4, "clear": "loop-clear: slot 1–4, or omit for all; available during playback except an active take; keeps sounds; stop then loop-undo to restore", "bars": [1, 16], "grids": [0, .25, .5, 1], "default_grid": .5, "count_in_beats": [0, 16], "step_notes": "MIDI pitches 0–127", "sound": "independent AU sounds when pistil-enable is active; otherwise shared standalone sound"},
                    "beats": self.library.catalog(), "drum_actions": ["stop", "mute", "unmute",
                        "panic", "volume", "pattern",
                        "strip-volume", "strip-pan", "strip-mute-toggle", "strip-solo-toggle"]}
        if command in ('pistil-enable','pistil-status','layer-select','layer-editor','layer-preset'):
            if command == 'pistil-enable':
                if transport.playing:
                    raise ValueError('stop playback before enabling independent sounds')
                from .paths import host_path
                path = host_path()
                changed=self.sounds.enable(path)
                if not changed and transport.drums and transport.drums.loaded:
                    return {'status':'ok','instruments':self.sounds.snapshot()}
                from .drum_audio import NativeDrumAudio
                from .drum_sequencer import StudioDrums
                if transport.drums:
                    transport.drums.stop()
                transport.drums=StudioDrums(NativeDrumAudio(self.sounds,self.library),self.library)
                transport.looper.drums=transport.drums
                transport.drums.load()
                transport.drums.command('volume',self.sounds.mix['drums']['volume'])
                self.drum_state['volume']=self.sounds.mix['drums']['volume']
                self.bank_requested=True
            elif command == 'pistil-status':
                if self.sounds.host:
                    return {'status':'ok', 'instruments':self.sounds.snapshot(), 'host':self.sounds.host.call('status')}
            else:
                slot = integer(request.get('slot'),1,6,'slot')
                if command == 'layer-select':
                    self._select_layer(slot)
                else:
                    if not self.sounds.host:
                        raise ValueError('enable independent Pistil sounds first')
                    if command == 'layer-preset':
                        preset=integer(request.get('preset'),1,100,'preset')
                        self.sounds.preset(slot,preset)
                    else:
                        self._select_layer(slot)
                        self.sounds.host.call('editor',slot=slot)
            return {'status':'ok','instruments':self.sounds.snapshot()}
        if isinstance(command, str) and command.startswith("loop-"):
            looper = transport.looper
            if command == "loop-configure":
                values = request.get('settings')
                if not isinstance(values, dict):
                    raise ValueError('settings must be an object')
                looper.configure(values)
            elif command == "loop-start":
                from .hydrogen import session_drums
                config = settings({**self.defaults, **request.get('settings', {})})
                resolved = self._resolve_drums(request.get('drums'))
                drum_config = session_drums({'drums':resolved})
                wait_for_key=request.get('wait_for_key',False)
                if type(wait_for_key) is not bool:raise ValueError('wait_for_key must be boolean')
                if wait_for_key and request.get('slot') is not None:raise ValueError('key start cannot arm a recording take')
                # Full settings validation precedes any transport interruption.
                from .midi import VIRTUAL_PORT
                if not isinstance(request.get('input'), str) or not request['input'].strip() or request['input'] == VIRTUAL_PORT:
                    raise ValueError('loop-start requires an exact physical input')
                integer(request.get('chord_channel'),1,16,'chord_channel')
                integer(request.get('output_channel',1),1,16,'output_channel')
                if request.get('slot') is not None:
                    integer(request['slot'],1,4,'slot')
                if drum_config is not None:
                    self._drums().prepare(drum_config)
                self._audio_ready()
                transport.stop()
                if request.get('slot') is not None:
                    self._select_layer(request['slot'])
                if self.sounds.host:
                    self.sounds.host.call('tempo',bpm=config['bpm'])
                looper.start(input_name=request['input'], chord_channel=request['chord_channel'],
                             output_channel=request.get('output_channel',1), config=config,
                             drum_config=drum_config, record_slot=request.get('slot'),wait_for_key=wait_for_key)
                self._set_tempo(config['bpm'])
                self.drum_state.update(playing_requested=drum_config is not None,bpm=config['bpm'])
                if drum_config:
                    self.drum_state.update(pattern=drum_config['pattern'],volume=drum_config.get('volume',.3))
                    self.sounds.mix['drums']['volume']=self.drum_state['volume']
                    self.selected_beat = request['drums'].get('beat')
            elif command == 'loop-record':
                config = settings({**self.defaults, **request.get('settings', {}), 'bpm':looper.perform['bpm']})
                looper.arm(request.get('slot'),config)
                self._select_layer(request['slot'], arming=True)
            elif command == 'loop-export':
                document = looper.export()
                document['drums'] = {'beat':self.selected_beat,'volume':self.drum_state['volume'],
                                     'loop_bars':transport.drums.loop_bars if transport.drums else None,
                                     'document':self.library.get(self.selected_beat) if self.selected_beat else None}
                instruments = self.sounds.capture() if self.sounds.healthy() else self.sounds.checkpoint
                if instruments is None and self.sounds.host and self.sounds.recovery_path.is_file():
                    instruments=json.loads(self.sounds.recovery_path.read_text())
                if instruments is not None:
                    document['instruments'] = instruments
                document['performance']['bpm']=self.defaults['bpm']
                return {'status':'ok','document':document}
            elif command == 'loop-import':
                document = request.get('document')
                if transport.playing:
                    raise ValueError('stop playback before importing loops and sounds')
                from .looper import Looper
                validator = Looper(lambda m: None, lambda e: None)
                validator.restore(document)
                drum_save=document.get('drums')
                if drum_save and drum_save.get('document'):
                    from .drum_library import validate
                    validate(drum_save['document'],self.library.sounds)
                    number(drum_save.get('volume',.3),0,1.5,'drum volume')
                    from .drum_sequencer import StudioDrums
                    StudioDrums.validate_bars(drum_save.get('loop_bars'))
                if 'instruments' in document:
                    self.sounds.restore(document['instruments'])
                looper.restore(document)
                self._set_tempo(document['performance']['bpm'])
                if drum_save and drum_save.get('document'):
                    restored=self.library.save(drum_save['document'])
                    self.selected_beat=restored['id']
                    self.drum_state['volume']=drum_save.get('volume',.3)
                    self.sounds.mix['drums']['volume']=self.drum_state['volume']
                    if transport.drums:
                        transport.drums.command('volume',self.drum_state['volume'])
                        transport.drums.set_length(drum_save.get('loop_bars'),self.selected_beat)
            elif command in ('loop-cancel','loop-mute','loop-step','loop-clear','loop-undo'):
                resolved = dict(request)
                if command == 'loop-step':
                    resolved['settings'] = settings({**self.defaults, **request.get('settings', {})})
                looper.edit(command[5:],resolved)
            else:
                raise ValueError('unknown loop command')
            return {'status':'ok','looper':looper.snapshot()}
        if command == "events":
            after = integer(request.get("after", 0), 0, 2**63 - 1, "after")
            with self.event_lock:
                return {"status": "ok", "events": [e for e in self.events if e["event_id"] > after],
                        "last_event_id": self.event_id,
                        "truncated": bool(self.events and after < self.events[0]["event_id"] - 1)}
        if command == "key-monitor":
            from .key_monitor import KeyMonitor
            enabled = request.get("enabled", True)
            if type(enabled) is not bool:
                raise ValueError("enabled must be true or false")
            timeline = transport.timeline
            def beat_at(t):  # beats only mean something while the Studio timeline runs
                return timeline.position(t) if timeline.running else None
            monitor = (KeyMonitor(self.report, request.get("input"), request.get("chord_channel", 3), beat_at)
                       if enabled else None)
            if self.key_monitor:
                self.key_monitor.stop()
            self.key_monitor = monitor
            if monitor:
                monitor.start()
            return {"status": "ok", "key_monitor": dict(monitor.state) if monitor else {"enabled": False}}
        if command == "key-events":
            after = integer(request.get("after", 0), 0, 2**63 - 1, "after")
            if not self.key_monitor:
                raise ValueError("key-monitor is not enabled")
            return {"status": "ok", **self.key_monitor.events(after), "key_monitor": dict(self.key_monitor.state)}
        if command == "sound-follow":
            from .sound_follow import SoundFollower
            enabled = request.get("enabled", True)
            if type(enabled) is not bool:
                raise ValueError("enabled must be true or false")
            follower = SoundFollower(self.sounds.sound, self.report, request.get("input")) if enabled else None
            if self.sound_follower:
                self.sound_follower.stop()
            self.sound_follower = follower
            if follower:
                follower.start()
            return {"status": "ok", "sound_follow": dict(follower.state) if follower else {"enabled": False}}
        if command == "perform-configure":
            changes = request.get("settings")
            if not isinstance(changes, dict):
                raise ValueError("settings must be an object")
            updated=settings({**self.defaults, **changes})
            if 'bpm' in changes:self._set_tempo(updated['bpm'])
            self.defaults=updated
            with transport.looper.lock:transport.looper.live_config=dict(updated)
            return {"status": "ok", "settings": dict(self.defaults), "applies_to": "next perform start"}
        if command in ("perform", "play", "demo"):
            original = request if command == "perform" else (demo_session() if command == "demo" else request.get("session"))
            if not isinstance(original, dict):
                raise ValueError("session must be an object")
            resolved = {**original, "drums": self._resolve_drums(original.get("drums"))}
            self._audio_ready()
            if command == "perform":
                changes = request.get("settings", {})
                if not isinstance(changes, dict):
                    raise ValueError("settings must be an object")
                resolved["settings"] = settings({**self.defaults, **changes})
                self.sounds.select(5)
                transport.perform(resolved)
                tempo = resolved["settings"]["bpm"]
            else:
                transport.play(resolved, bpm=request.get("bpm",self.defaults["bpm"]), transpose=request.get("transpose", 0),
                               repeats=request.get("repeats", 1))
                tempo = request.get("bpm", self.defaults["bpm"])
            self._set_tempo(tempo)
            self.drum_state["playing_requested"] = resolved["drums"] is not None
            self.drum_state["bpm"] = tempo
            if resolved["drums"]:
                self.drum_state.update({k: resolved["drums"].get(k, .3) for k in ("pattern", "volume")})
                self.selected_beat = original["drums"].get("beat")
                self.sounds.mix["drums"]["volume"]=self.drum_state["volume"]
        elif command == "perform-update":
            if transport.live is None or not transport.playing:
                raise ValueError("no live performance is running")
            changes = request.get("settings")
            if not isinstance(changes, dict):
                raise ValueError("settings must be an object")
            settings({**transport.live.config,**changes})
            if "bpm" in changes:self._set_tempo(changes["bpm"])
            transport.live.update(changes)
            return {"status": "queued", "command": command, "settings": dict(changes),
                    "confirmation": "poll status or events for perform_updated"}
        elif command == "beats-list":
            return {"status": "ok", "bank": next(iter(self.library.documents.values())).get("bank", BANK_NAME), "beats": self.library.catalog(),
                    "bank_path": self.bank_path, "load_requested": self.bank_requested}
        elif command == "beats-load":
            drums = self._drums()
            if transport.playing:
                raise ValueError("stop playback before loading the sound rack")
            result = drums.load()
            self.bank_requested = True
            return {**result, "bank": "Studio mixed sound rack", "sounds":len(self.library.sounds)}
        elif command == "beat-get":
            document=self.library.get(request.get('beat'))
            return {"status":"ok", "document":document, "playback_document":transport.drums.arrange(document) if transport.drums else document}
        elif command == "beat-save":
            document = self.library.save(request.get('document'))
            result = {"status":"ok"}
            if self.selected_beat == document['id'] and transport.drums:
                result = transport.drums.select(document['id'])
            return {**result, "document":document}
        elif command == "kits-list":
            return {"status":"ok", "kits":self.library.kits, "sounds":self.library.sound_list(), "capacity":92}
        elif command in ("kits-import", "sample-upload"):
            drums=self._drums()
            if transport.playing:
                raise ValueError('stop playback before importing sounds')
            old_sounds,old_kits=copy.deepcopy(self.library.sounds),copy.deepcopy(self.library.kits)
            try:
                if command == 'kits-import':
                    path=request.get('path')
                    if not isinstance(path,str) or not path.strip():
                        raise ValueError('path must be a drumkit directory or .h2drumkit archive')
                    kit=self.library.import_kit(path)
                else:
                    kit=self.library.upload(request.get('name'),request.get('data'),request.get('license','User supplied'))
                drums.load();self.bank_requested=True
            except Exception:
                self.library.sounds,self.library.kits=old_sounds,old_kits
                self.library.persist()
                raise
            return {'status':'ok' if getattr(drums.client,'native_audio',False) is True else 'sent','kit':kit}
        elif command == 'sound-preview':
            drums=self._drums()
            if transport.playing:
                raise ValueError('stop playback before previewing sounds')
            identifier=request.get('sound')
            if not drums.loaded or identifier not in self.library.sounds:
                raise ValueError('load the sound rack and select an available sound')
            velocity=number(request.get('velocity',.5),.01,1,'velocity')
            drums.client.command('volume',.3)
            drums.client.command('unmute')
            return drums.client.command('note-on',velocity,36+list(self.library.sounds).index(identifier))
        elif command == "beats-select":
            drums = self._drums()
            beat = self._beat(request.get("beat"))
            result = drums.command("pattern", beat["pattern"])
            self.selected_beat = beat["id"]
            self.drum_state["pattern"] = beat["pattern"]
            return {**result, "beat": beat, "tempo_changed": False}
        elif command == "beats-play":
            drums = self._drums()
            if transport.playing:
                raise ValueError("use perform with drums.beat for coordinated playback; stop first")
            beat = self._beat(request.get("beat", self.selected_beat))
            bpm = number(request.get("bpm", self.defaults["bpm"]), 30, 300, "bpm")
            volume = number(request.get("volume", .3), 0, 1.5, "volume")
            self._audio_ready()
            transport.play_drums(bpm, {"pattern": beat["pattern"], "volume": volume})
            self._set_tempo(bpm)
            self.sounds.mix["drums"]["volume"]=volume
            self.selected_beat = beat["id"]
            self.drum_state.update(playing_requested=True, bpm=bpm, volume=volume, pattern=beat["pattern"])
            return {"status": "sent", "beat": beat, "bpm": bpm, "confirmed": False}
        elif command == "drums":
            drums = self._drums()
            action = request.get("action")
            if not isinstance(action, str):
                raise ValueError("Hydrogen action must be a string")
            if action == "feedback":
                return {"status": "observed", "feedback": drums.feedback()}
            if action=='bpm':
                self._set_tempo(request.get('value'));return {'status':'ok','tempo':transport.timeline.snapshot()}
            if transport.playing and action in { "play", "pause", "stop", "mode", "open-song", "kit"}:
                raise ValueError("stop the session before changing drum transport, tempo, song or kit")
            if action == "panic":
                drums.panic()
                self.drum_state["playing_requested"] = False
                return {"status": "sent", "confirmed": False}
            command_message(action, request.get("value"), request.get("strip"))
            result = drums.command(action, request.get("value"), request.get("strip"))
            if action=="volume":self.sounds.mix["drums"]["volume"]=request.get("value")
            if action in ("volume", "bpm", "pattern"):
                self.drum_state[action] = request.get("value")
            if action == "pattern":
                self.selected_beat = None
            if action in ("play", "pause", "stop"):
                self.drum_state["playing_requested"] = action == "play"
            if action == "open-song":
                self.bank_requested, self.selected_beat = False, None
            return result
        elif command in ("stop", "panic", "quit"):
            (transport.panic if command in ("panic", "quit") else transport.stop)()
            self.sounds.panic()
            self.drum_state["playing_requested"] = False
            if command == "quit":
                self.closed.set()
                return {"status": "closing"}
        else:
            raise ValueError("command must be " + ", ".join(COMMANDS))
        return {"status": "ok", "command": command, "playing": transport.playing}

    def close(self):
        with self.lock:
            self.closed.set()
            if self.midi_connection:self.midi_connection.close()
            self.play_along.stop()
            if self.sound_follower:
                self.sound_follower.stop()
            if self.key_monitor:
                self.key_monitor.stop()
            try:
                self.transport.panic()
            finally:
                self.transport.clock_output.close()
                self.sounds.close()


class HttpAPI:
    def __init__(self, controller, port):
        integer(port, 1024, 65535, "API port")
        self.controller = controller
        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def log_message(self, *args):
                pass

            def reply(self, code, data):
                payload = json.dumps(data, allow_nan=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)

            def allowed(self):
                # Reject browser cross-origin requests and DNS-rebinding Host values.
                host = self.headers.get("Host")
                if host not in (f"127.0.0.1:{port}", f"localhost:{port}") or self.headers.get("Origin") not in (None, f"http://{host}"):
                    self.reply(403, {"status": "error", "error": "local API clients only"})
                    return False
                return True

            def do_GET(self):
                if not self.allowed():
                    return
                if self.path in ("/", "/drum-editor.js", "/studio.js", "/studio.css"):
                    payload = files("orchid_studio").joinpath("studio.html" if self.path == "/" else self.path[1:]).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8" if self.path == "/" else "text/css; charset=utf-8" if self.path.endswith(".css") else "application/javascript; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                command = {"/status": "status", "/capabilities": "capabilities", "/beats": "beats-list"}.get(self.path)
                if command is None:
                    self.reply(404, {"status": "error", "error": "unknown API route"})
                    return
                self.reply(200, controller.execute({"command": command}))

            def do_POST(self):
                if not self.allowed():
                    return
                if self.path != "/command":
                    self.reply(404, {"status": "error", "error": "use /command"})
                    return
                try:
                    if self.headers.get_content_type() != "application/json":
                        raise ValueError("Content-Type must be application/json")
                    if self.headers.get("Transfer-Encoding") is not None:
                        raise ValueError("chunked requests are unsupported")
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 1 <= size <= 16 * 1024 * 1024:
                        raise ValueError("JSON body must be 1–16777216 bytes")
                    data = self.rfile.read(size)
                    if len(data) != size:
                        raise ValueError("incomplete request body")
                    def invalid_constant(value):
                        raise ValueError("non-finite JSON number: " + value)
                    request = json.loads(data, parse_constant=invalid_constant)
                    result = controller.execute(request)
                    self.reply(400 if result.get("status") == "error" else 200, result)
                except (ValueError, UnicodeError) as exc:
                    self.reply(400, {"status": "error", "error": str(exc)})
        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, name="orchid-http", daemon=True)

    def __enter__(self):
        self.thread.start()
        self.controller.report({"event": "api_ready", "url": f"http://127.0.0.1:{self.server.server_port}", "api_version": 1})
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
