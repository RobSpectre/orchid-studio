"""Independent raw-chord monitoring; never consumes performed/bass streams."""
import threading
import time
from .midi import backend, exact_port, VIRTUAL_PORT
from .sequencer import integer, Player


class DirectVoice:
    def __init__(self,send,channel,velocity_limit=80):
        self.channel=integer(channel,1,16,'chord_channel')-1
        self.limit=integer(velocity_limit,1,127,'velocity_limit')
        self.player=Player(send,{0})

    def receive(self,message):
        if len(message)!=3 or message[0]&15!=self.channel:return
        kind=message[0]&0xF0
        if kind in (0x80,0x90):
            note,velocity=message[1:]
            attack=kind==0x90 and velocity>0
            self.player.send([0x90 if attack else 0x80,note,min(velocity,self.limit) if attack else 0])
            if attack:self.player.active.add((0,note))
            else:self.player.active.discard((0,note))
        elif kind==0xB0 and message[1] in (64,66):
            self.player.send([0xB0,message[1],message[2]])

    def panic(self):self.player.panic()


class PlayAlong:
    def __init__(self,send,report):
        self.send,self.report=send,report
        self.voice_lock=threading.RLock();self.voice=None
        self.stop_event=threading.Event();self.worker=None
        self.state={'enabled':False,'input':None,'chord_channel':3,'velocity_limit':80,'status':'off','slot':6}

    def configure(self,enabled,input_name=None,chord_channel=3,velocity_limit=80):
        if type(enabled) is not bool:raise ValueError('enabled must be boolean')
        integer(chord_channel,1,16,'chord_channel');integer(velocity_limit,1,127,'velocity_limit')
        if enabled and (not isinstance(input_name,str) or not input_name.strip() or input_name==VIRTUAL_PORT):
            raise ValueError('play-along needs an exact physical input')
        source=None
        if enabled:
            source=backend().MidiIn()
            try:
                source.open_port(exact_port(source.get_ports(),input_name))
                source.ignore_types(sysex=True,timing=True,active_sense=True)
            except Exception:
                source.close_port();source.delete();raise
        self.stop()
        self.state={'enabled':enabled,'input':input_name,'chord_channel':chord_channel,
                    'velocity_limit':velocity_limit,'status':'ready' if enabled else 'off','slot':6}
        if enabled:
            self.stop_event.clear()
            self.worker=threading.Thread(target=self.run,args=(source,),name='orchid-play-along')
            self.worker.start()

    def stop(self):
        self.stop_event.set()
        if self.worker:self.worker.join();self.worker=None
        self.state={**self.state,'enabled':False,'status':'off'}

    def panic(self):
        """Release held notes/pedals without disabling incoming keys."""
        with self.voice_lock:
            if self.voice:self.voice.panic()

    def run(self,source):
        voice=DirectVoice(self.send,self.state['chord_channel'],self.state['velocity_limit'])
        with self.voice_lock:self.voice=voice
        next_check=time.monotonic()+1
        try:
            while not self.stop_event.is_set():
                for _ in range(256):
                    with self.voice_lock:
                        if self.stop_event.is_set():break
                        packet=source.get_message()
                        if packet is None:break
                        voice.receive(packet[0])
                if time.monotonic()>=next_check:
                    exact_port(source.get_ports(),self.state['input']);next_check=time.monotonic()+1
                self.stop_event.wait(.002)
        except Exception as exc:
            self.state={**self.state,'status':'error','error':str(exc)}
            self.report({'event':'play_along_error','error':str(exc)})
        finally:
            try:
                with self.voice_lock:
                    try:voice.panic()
                    finally:self.voice=None
            finally:source.close_port();source.delete()
