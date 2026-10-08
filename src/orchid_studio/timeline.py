"""One musical timeline, integrating cubic Bézier tempo changes exactly."""
import threading
import time
from .sequencer import number


class Timeline:
    def __init__(self, bpm=96, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.start_bpm = self.target_bpm = bpm
        self.anchor = clock()
        self.beat = 0.
        self.elapsed_at_anchor = 0.
        self.ramp_seconds = 0.
        self.running = self.paused = False
        self.revision = 0

    def _elapsed(self, now):
        return self.elapsed_at_anchor + (max(0, now-self.anchor) if self.running and not self.paused else 0)

    def _bpm_at(self, elapsed):
        if not self.ramp_seconds or elapsed >= self.ramp_seconds:
            return self.target_bpm
        u = max(0, elapsed/self.ramp_seconds)
        # Cubic Bézier controls (1/3, 0), (2/3, 1): x=u, y=3u²-2u³.
        return self.start_bpm + (self.target_bpm-self.start_bpm)*(3*u*u-2*u*u*u)

    def _integral(self, elapsed):
        """BPM-seconds since the ramp began, including time after its endpoint."""
        if not self.ramp_seconds:
            return self.target_bpm*elapsed
        t = min(elapsed, self.ramp_seconds)
        u = t/self.ramp_seconds
        eased_area = self.ramp_seconds*(u**3-u**4/2)
        return (self.start_bpm*t + (self.target_bpm-self.start_bpm)*eased_area
                + self.target_bpm*max(0, elapsed-self.ramp_seconds))

    @property
    def bpm(self):
        with self.lock:
            return self._bpm_at(self._elapsed(self.clock()))

    def position(self, now=None):
        with self.lock:
            elapsed = self._elapsed(self.clock() if now is None else now)
            return self.beat + (self._integral(elapsed)-self._integral(self.elapsed_at_anchor))/60

    def reset(self, bpm, start=0):
        value = number(bpm,20,300,'bpm')
        with self.lock:
            self.start_bpm = self.target_bpm = value
            self.beat = start
            self.anchor = self.clock()
            self.elapsed_at_anchor = self.ramp_seconds = 0.
            self.running = True
            self.paused = False
            self.revision += 1

    def tempo(self, bpm, transition_seconds=2):
        value = number(bpm,20,300,'bpm')
        duration = number(transition_seconds,0,10,'transition_seconds')
        with self.lock:
            # Repeating a request must not postpone an in-progress transition.
            if value == self.target_bpm and duration != 0:
                return
            now = self.clock()
            current = self._bpm_at(self._elapsed(now))
            self.beat = self.position(now)
            self.anchor = now
            self.elapsed_at_anchor = 0.
            self.start_bpm = current
            self.target_bpm = value
            self.ramp_seconds = duration if self.running and current != value else 0.

    def pause(self, paused):
        with self.lock:
            now = self.clock()
            self.beat = self.position(now)
            self.elapsed_at_anchor = self._elapsed(now)
            self.anchor = now
            self.paused = paused
            self.revision += 1

    def stop(self):
        with self.lock:
            self.beat = 0.
            self.anchor = self.clock()
            self.start_bpm = self.target_bpm
            self.elapsed_at_anchor = self.ramp_seconds = 0.
            self.running = self.paused = False

    def snapshot(self):
        with self.lock:
            now = self.clock()
            elapsed = self._elapsed(now)
            return {'bpm':round(self._bpm_at(elapsed),3), 'target_bpm':self.target_bpm,
                    'transitioning':bool(self.ramp_seconds and elapsed < self.ramp_seconds),
                    'transition_seconds':self.ramp_seconds,
                    'transition_progress':min(1,elapsed/self.ramp_seconds) if self.ramp_seconds else 1,
                    'curve':'cubic-bezier(0.333333, 0, 0.666667, 1)',
                    'beat':round(self.position(now),4), 'paused':self.paused, 'running':self.running}
