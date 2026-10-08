"""Publish Studio transport via a dedicated software MIDI source, never Orchid."""
import math
import threading
import time
from .midi import backend
from .sequencer import number

PORT = 'Orchid Studio Clock'


class ClockOutput:
    def __init__(self, factory=None, clock=time.monotonic):
        self.factory=factory or (lambda:backend().MidiOut())
        self.clock=clock
        self.lock=threading.RLock()
        self.output=None
        self.started=False
        self.paused=False
        self.next_tick=0
        self.pulses=0
        self.error=None
        self.offset_ms=40
        self.queue=[]
        self.wake=threading.Event()
        self.shutdown=threading.Event()
        self.worker=None

    def configure(self, enabled, offset_ms=40):
        if type(enabled) is not bool:raise ValueError('enabled must be boolean')
        number(offset_ms,-200,500,'offset_ms')
        if offset_ms<0:raise ValueError('offset_ms must be 0–500; Studio cannot send into the past')
        if enabled and self.output is not None:
            with self.lock:
                self.offset_ms=offset_ms;self.error=None
            return self.snapshot()
        self.close()
        self.offset_ms=offset_ms
        self.error=None
        if enabled:
            output=self.factory()
            try:output.open_virtual_port(PORT)
            except Exception:
                output.delete();raise
            self.output=output
            self.shutdown.clear()
            self.worker=threading.Thread(target=self._run,name='studio-midi-clock',daemon=True)
            self.worker.start()
        return self.snapshot()

    def begin(self):
        with self.lock:
            self.stop()
            self.started=False;self.next_tick=0;self.pulses=0;self.error=None

    def advance(self, beat, bpm):
        with self.lock:
            if not self.output or self.error or self.paused or beat<0:return
            now=self.clock()
            if not self.started:
                self.started=True
                self.queue.append((now-beat*60/bpm+self.offset_ms/1000,[0xFA]))
            last=math.floor(beat*24+1e-8)
            if last-self.next_tick>6:
                # Never burst a backlog of clock pulses and silently lose musical position.
                self.error='clock stalled; transport stopped for external followers; restart playback'
                self.stop();return
            while self.next_tick<=last:
                deadline=now+(self.next_tick/24-beat)*60/bpm+self.offset_ms/1000
                self.queue.append((deadline,[0xF8]));self.next_tick+=1
            self.wake.set()

    def flush(self, now=None):
        with self.lock:
            now=self.clock() if now is None else now
            if self.queue and now-self.queue[0][0]>.05:
                self.error='clock output missed its deadline; restart playback'
                self.stop();return
            while self.output and self.queue and self.queue[0][0]<=now:
                _,message=self.queue.pop(0)
                self.output.send_message(message)
                if message==[0xF8]:self.pulses+=1

    def _run(self):
        while not self.shutdown.is_set():
            try:self.flush()
            except Exception as exc:
                with self.lock:
                    self.error=str(exc);self.queue.clear()
                    try:self.stop()
                    except Exception:pass
                return
            with self.lock:
                delay=max(0,self.queue[0][0]-self.clock()) if self.queue else .1
            self.wake.wait(min(delay,.1));self.wake.clear()

    def pause(self, paused):
        with self.lock:
            if paused==self.paused:return
            self.paused=paused
            if self.output and self.started:
                # Drain already scheduled pulses before Stop; Continue retains that phase.
                self.queue.append((self.clock()+self.offset_ms/1000,[0xFC if paused else 0xFB]))
                self.wake.set()

    def stop(self):
        with self.lock:
            self.queue.clear()
            if self.output and self.started:
                self.output.send_message([0xFC])
            self.started=False;self.paused=False

    def close(self):
        self.shutdown.set();self.wake.set()
        if self.worker and self.worker is not threading.current_thread():self.worker.join()
        self.worker=None
        with self.lock:
            try:self.stop()
            finally:
                if self.output:
                    self.output.close_port();self.output.delete();self.output=None

    def snapshot(self):
        with self.lock:
            return {'enabled':self.output is not None,'port':PORT,'ppqn':24,'running':self.started and not self.paused,'paused':self.paused,
                    'pulses_sent':self.pulses,'offset_ms':self.offset_ms,'error':self.error,
                    'idle_clock':False,'count_in':'Start and clock begin at musical beat zero'}
