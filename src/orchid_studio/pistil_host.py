"""Optional native macOS AU host bridge; never opens an Orchid MIDI output."""
import base64
import copy
import json
from pathlib import Path
import plistlib
import queue
import subprocess
import threading
import time

from .paths import data_dir
from .sequencer import integer, number
from .sound_follow import sound_report


class NativeHost:
    def __init__(self, path):
        self.lock=threading.Lock()
        self.pending={}
        self.counter=0
        self.ready=threading.Event()
        self.error=None
        self.process=None
        path=Path(path).resolve()
        if not path.is_file():
            raise ValueError('Build the local Pistil host with orchid-studio build-host first')
        log_path=data_dir()/'pistil-host.log'
        log_path.parent.mkdir(parents=True,exist_ok=True)
        self.log=log_path.open('ab')
        try:
            self.process=subprocess.Popen([str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                          stderr=self.log,text=True,bufsize=1)
            self.reader=threading.Thread(target=self._read,name='pistil-host-responses',daemon=True)
            self.reader.start()
            if not self.ready.wait(45) or self.error:
                raise RuntimeError(self.error or 'Pistil host startup timed out')
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                try:result=json.loads(line)
                except ValueError:continue
                if result.get('event')=='host_ready':self.ready.set()
                if result.get('event')=='host_error':
                    self.error=result.get('error');self.ready.set()
                with self.lock:
                    waiter=self.pending.get(result.get('id'))
                if waiter:waiter.put(result)
                elif result.get('status')=='error':self.error=result.get('error')
        finally:
            code=self.process.wait()
            self.error=self.error or f'Pistil host exited (code {code}); restart audio to restore the saved sounds'
            self.ready.set()
            with self.lock:
                for waiter in self.pending.values():
                    waiter.put({'status':'error','error':self.error})

    def call(self, command, *, wait=True, **values):
        waiter=queue.Queue()
        with self.lock:
            if self.error or self.process.poll() is not None:
                raise RuntimeError(self.error or 'Pistil host is not running')
            payload={'command':command,**values}
            if command in ('midi','drum-hit'):
                payload.setdefault('at',time.monotonic()+.04)
            self.counter+=1;request_id=self.counter
            if wait:
                payload['id']=request_id;self.pending[request_id]=waiter
            try:
                self.process.stdin.write(json.dumps(payload,separators=(',',':'))+'\n')
                self.process.stdin.flush()
            except (BrokenPipeError,OSError):
                self.pending.pop(request_id,None)
                raise RuntimeError('Pistil host connection closed')
        if not wait:return None
        try:
            result=waiter.get(timeout=15)
            if result.get('status')=='error':raise RuntimeError(result.get('error','Pistil host error'))
            return result
        except queue.Empty:
            raise RuntimeError('Pistil host did not respond')
        finally:
            with self.lock:self.pending.pop(request_id,None)

    def close(self):
        if self.process:
            if self.process.poll() is None:
                try:self.call('quit')
                except (RuntimeError,OSError):pass
                try:self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.terminate();self.process.wait(timeout=3)
            for stream in (self.process.stdin,self.process.stdout):
                if stream:stream.close()
        self.log.close()


def validate_states(states):
    if not isinstance(states,list) or len(states) not in (4,5,6):
        raise ValueError('four to six Pistil states required')
    for value in states:
        if not isinstance(value,str) or len(value)>6*1024*1024:
            raise ValueError('invalid Pistil state size')
        try:
            state=plistlib.loads(base64.b64decode(value,validate=True))
            if not isinstance(state,dict) or state.get('manufacturer')!=int.from_bytes(b'Tptp','big') or state.get('subtype')!=int.from_bytes(b'Pitl','big'):
                raise ValueError('state is not a Pistil Audio Unit')
        except Exception as exc:
            raise ValueError('invalid Pistil AU state') from exc
    return copy.deepcopy(states)


class SoundRouter:
    def __init__(self,fallback):
        self.fallback=fallback
        self.host=None
        self.selected=1
        self.labels=['Pistil']*6
        self.mix={name:{'volume':.3 if name=='drums' else 1.,'pan':0.} for name in ['layer-1','layer-2','layer-3','layer-4','drums','live','play-along']}
        self.pending_sound=None
        self.route_lock=threading.RLock()
        self.checkpoint=None
        self.recovery_path=data_dir()/"pistil-recovery.json"

    def snapshot(self):
        return {'enabled':self.host is not None,'selected_slot':self.selected,'labels':list(self.labels),
                'error':self.host.error if self.host else None,
                'engine':'Pistil AU · macOS' if self.host else 'Pistil standalone · shared sound'}

    def enable(self,path):
        if self.host and not self.host.error and self.host.process.poll() is None:return False
        if self.host:
            self.host.close();self.host=None
        host=NativeHost(path)
        try:host.call('enable',enabled=True)
        except Exception:host.close();raise
        self.host=host
        try:
            saved=self.checkpoint
            if saved is None and self.recovery_path.is_file():
                saved=json.loads(self.recovery_path.read_text())
            if saved:self.restore(saved)
        except Exception:
            self.host.close();self.host=None;raise
        return True

    def healthy(self):
        return self.host is not None and not self.host.error and self.host.process.poll() is None

    def send(self,message):
        with self.route_lock:
            if self.host:self.send_layer(self.selected,message)
            else:self.fallback(message)

    def send_live(self,message):
        self.send_layer(5,message)

    @staticmethod
    def validate_mix(mix):
        if not isinstance(mix,dict):raise ValueError('mixer must be an object')
        for target,values in mix.items():
            if target not in ('layer-1','layer-2','layer-3','layer-4','live','drums','play-along') or not isinstance(values,dict):raise ValueError('unknown mixer channel')
            if set(values)-{'volume','pan'}:raise ValueError('unknown mixer setting')
            if 'volume' in values:number(values['volume'],0,1.5,'volume')
            if 'pan' in values:number(values['pan'],-1,1,'pan')

    def set_mix(self,target,values):
        self.validate_mix({target:values})
        update={**self.mix[target],**values}
        if self.host:
            self.host.call('mix',target=target,slot=6 if target=='play-along' else 5 if target in ('live','drums') else int(target[-1]),**update)
        self.mix[target]=update

    def send_layer(self,slot,message):
        integer(slot,1,6,'slot')
        if self.host:
            if not self.healthy() and len(message)==3 and (message[0]&0xF0==0x80 or
                    (message[0]&0xF0==0x90 and message[2]==0) or
                    (message[0]&0xF0==0xB0 and message[1] in (64,66,120,123) and message[2]==0)):
                return # The process is gone; cleanup must still stop the surviving transports.
            self.host.call('midi',slot=slot,message=list(message),wait=False)
        else:self.fallback(message)

    def sound(self,message):
        decoded=sound_report(message)
        if not decoded:raise ValueError('unsupported Sound report')
        with self.route_lock:
            if self.host:
                slot=self.selected
                if decoded['kind']=='preset':
                    self.pending_sound=(slot,decoded['preset'],time.monotonic())
                elif self.pending_sound:
                    pending_slot,preset,stamp=self.pending_sound
                    if preset==decoded['preset'] and time.monotonic()-stamp<.25:
                        slot=pending_slot
                    self.pending_sound=None
                self.host.call('sound',slot=slot,message=list(message),wait=False)
                if slot!=6:self.host.call('sound',slot=6,message=list(message),wait=False)
                self.labels[5]=f"Sound {decoded['preset']:03d}"
                self.labels[slot-1]=f"Sound {decoded['preset']:03d}"
            else:self.fallback(message)

    def select(self,slot):
        with self.route_lock:self.selected=integer(slot,1,6,'slot')

    def preset(self,slot,preset):
        integer(slot,1,6,'slot');integer(preset,1,100,'preset')
        if not self.host:raise ValueError('enable independent Pistil sounds first')
        with self.route_lock:
            self.host.call('sound',slot=slot,message=[176,102,preset-1])
            self.labels[slot-1]=f'Sound {preset:03d}'

    def capture(self):
        if not self.host:return None
        with self.route_lock:
            result=self.host.call('capture')
            document={'format':{4:'pistil-au-v1',5:'pistil-au-v2',6:'pistil-au-v3'}[len(result['states'])],'selected_slot':self.selected,'labels':list(self.labels[:len(result['states'])]),
                      'states':validate_states(result['states']), 'mixer':copy.deepcopy(self.mix)}
            self.remember(document)
            return document

    def remember(self,document):
        self.checkpoint=copy.deepcopy(document)
        self.recovery_path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.recovery_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(document))
        temporary.replace(self.recovery_path)

    @staticmethod
    def validate(document):
        if not isinstance(document,dict) or document.get('format') not in ('pistil-au-v1','pistil-au-v2','pistil-au-v3'):
            raise ValueError('unsupported instrument state format')
        integer(document.get('selected_slot'),1,6,'selected_slot')
        labels=document.get('labels')
        if not isinstance(labels,list) or len(labels) not in (4,5,6) or any(not isinstance(s,str) or len(s)>100 for s in labels):
            raise ValueError('four to six short sound labels required')
        states=validate_states(document.get('states'))
        if len(labels)!=len(states):raise ValueError('sound labels must match states')
        if 'mixer' in document:SoundRouter.validate_mix(document['mixer'])

    def restore(self,document):
        self.validate(document)
        if not self.host:raise ValueError('enable independent Pistil sounds before importing saved sound states')
        with self.route_lock:
            self.host.call('restore',states=document['states'])
            self.labels=list(document['labels'])
            while len(self.labels)<6:self.labels.append(self.labels[-1])
            self.select(document['selected_slot'])
            for target,values in document.get('mixer',self.mix).items():self.set_mix(target,values)
            self.remember(document)

    def panic(self):
        if self.healthy():self.host.call('panic')

    def close(self):
        if self.host:
            self.host.close();self.host=None
