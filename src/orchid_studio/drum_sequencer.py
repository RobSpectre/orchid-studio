"""Beat-position-driven drum scheduling. Hydrogen renders hits, never runs its transport."""
import copy
import math
import random
import threading

from .drum_library import DrumLibrary, validate
from .sequencer import integer, number


class StudioDrums:
    def __init__(self, client, library=None):
        self.client = client
        self.library = library or DrumLibrary()
        self.lock = threading.RLock()
        self.loaded = False
        self.running = False
        self.document = None
        self.loop_bars = None
        self.pending = None
        self.previous = -1e-9
        self.anchor = 0
        self.bpm = 124
        self.dropped = 0
        self.hits_sent = 0
        self.rng = random.Random(0)

    def load(self):
        if getattr(self.client, 'native_audio', False) is True:
            result=self.client.load()
            self.loaded=True
            return result
        path = self.library.rack()
        result = self.client.command('open-song', path)
        self.loaded = True
        return {**result, 'path':path}

    def prepare(self, config):
        if not self.loaded:
            raise ValueError('load the Studio sound rack with beats-load first')
        catalog = self.library.catalog()
        index = integer(config['pattern'], 0, len(catalog)-1, 'pattern')
        return self.arrange(self.library.get(catalog[index]['id']))

    def start(self, bpm, config):
        document = self.prepare(config)
        with self.lock:
            self.client.command('stop')
            self.client.command('volume', config.get('volume',.3))
            self.client.command('unmute')
            self.bpm=bpm;self.document=document;self.previous=-1e-9;self.anchor=0
            self.pending=None;self.running=True;self.hits_sent=0;self.dropped=0
            self.rng.seed(0)

    def select(self, identifier):
        document=self.arrange(self.library.get(identifier))
        with self.lock:
            if self.running:
                boundary=(math.floor(max(0,self.previous)/4)+1)*4
                self.pending=(boundary,document)
                return {'status':'queued','at_beat':boundary}
            self.document=document
            return {'status':'ok'}

    @staticmethod
    def validate_bars(bars):
        if bars is None:return None
        integer(bars,2,64,'drum loop bars')
        if bars%2:raise ValueError('drum loop bars must be a multiple of two')
        return bars

    def arrange(self, document, bars=None):
        source=validate(document,self.library.sounds)
        target=self.loop_bars if bars is None else self.validate_bars(bars)
        if target is None or target==source['bars']:return source
        d=copy.deepcopy(source);d['bars']=target;d['hits']=[]
        for offset in range(0,target*4,source['bars']*4):
            d['hits'].extend({**h,'beat':h['beat']+offset} for h in source['hits'] if h['beat']+offset<target*4)
        return validate(d,self.library.sounds)

    def set_length(self,bars,identifier=None):
        bars=self.validate_bars(bars)
        with self.lock:
            old=self.loop_bars;self.loop_bars=bars
            try:
                target=identifier or (self.pending[1]['id'] if self.pending else self.document['id'] if self.document else None)
                return self.select(target) if target else {'status':'ok'}
            except Exception:
                self.loop_bars=old
                raise

    def advance(self, beat):
        with self.lock:
            if not self.running or beat<0:return
            if beat < self.previous:
                raise ValueError('drum timeline must move forward')
            if self.pending and beat >= self.pending[0]:
                boundary,document=self.pending
                self._emit(min(beat,boundary-1e-9))
                self.document=document;self.anchor=boundary;self.previous=boundary-1e-9
                self.pending=None
            self._emit(beat)

    def _emit(self, beat):
        d=self.document;length=d['bars']*4
        lanes={l['id']:l for l in d['lanes']}
        sounds={identifier:36+i for i,identifier in enumerate(self.library.sounds)}
        first=max(0,math.floor((self.previous-self.anchor)/length))
        last=max(0,math.floor((beat-self.anchor)/length))
        # A stalled process must not burst old hits. Keep at most the current cycle.
        if last-first>1:first=last
        window=.1*self.bpm/60
        due=[]
        for cycle in range(first,last+1):
            for hit in d['hits']:
                pos=hit['beat']
                if int(math.floor(pos*4+1e-8))%2:
                    pos += d['swing']*.25
                # Swing can push a late hit across the boundary; wrap it into this cycle.
                pos %= length
                when=self.anchor+cycle*length+pos
                if self.previous < when <= beat:
                    if beat-when>window:
                        self.dropped+=1;continue
                    due.append((when,hit))
        for _,hit in sorted(due,key=lambda pair:pair[0]):
            lane=lanes[hit['lane']]
            if lane['muted'] or lane['gain']==0 or self.rng.random()>=hit['probability']:continue
            self.client.command('note-on', min(1,hit['velocity']*lane['gain']), sounds[lane['sound']])
            self.hits_sent+=1
        self.previous=beat

    def command(self, action, value=None, strip=None):
        if action=='pattern':
            catalog=self.library.catalog()
            index=integer(value,0,len(catalog)-1,'pattern')
            return self.select(catalog[index]['id'])
        if action in ('play','mode','loop','kit','open-song'):
            raise ValueError('Studio owns drum playback; use beats-play, beats-load or kits-import')
        if action in ('stop','pause'):
            self.stop();return {'status':'ok'}
        if action=='bpm':
            self.bpm=number(value,30,300,'bpm')
            return {'status':'ok'}
        return self.client.command(action,value,strip)

    def feedback(self, *args):
        return self.client.feedback(*args)

    def stop(self):
        with self.lock:
            self.running=False;self.pending=None
            self.client.command('stop')
            # Kill sample tails at Stop, too; no drum transport survives Studio's timeline.
            return self.client.command('mute')

    def panic(self):
        return self.stop()

    def snapshot(self):
        with self.lock:
            return {'clock':'studio', 'renderer':'studio-native' if getattr(self.client,'native_audio',False) is True else 'hydrogen-osc', 'running':self.running,'position':max(0,self.previous),
                    'loop_bars':self.loop_bars, 'bars':self.document['bars'] if self.document else None,
                    'anchor':self.anchor, 'document':copy.deepcopy(self.document),
                    'pending_bars':self.pending[1]['bars'] if self.pending else None,
                    'active_beat':self.document['id'] if self.document else None,
                    'pending_beat':self.pending[1]['id'] if self.pending else None,
                    'switch_at':self.pending[0] if self.pending else None,
                    'hits_sent':self.hits_sent,'late_hits_skipped':self.dropped}
