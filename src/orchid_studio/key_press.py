"""Cancellable software keys with orchid-robot score duration notation."""
import threading
import time

from .note_duration import DEFAULT_DURATION, duration_beats
from .sequencer import integer, Player


KEYS = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
# A separate MIDI channel keeps generated releases apart from physical channel-1 notes.
CHANNEL = 15


def parse_press(request):
    allowed = {'command', 'id', 'key', 'duration', 'octave', 'velocity', 'slot'}
    if set(request) - allowed:
        raise ValueError('key-press fields: key, duration, octave, velocity, slot')
    key = request.get('key')
    if not isinstance(key, str) or key not in KEYS:
        raise ValueError('key must be one of ' + ', '.join(KEYS))
    octave = integer(request.get('octave', 4), -1, 9, 'octave')
    note = integer((octave + 1) * 12 + KEYS.index(key), 0, 127, 'MIDI note')
    duration = request.get('duration', DEFAULT_DURATION)
    return {'key': key, 'octave': octave, 'note': note, 'duration': duration,
            'beats': duration_beats(duration),
            'velocity': integer(request.get('velocity', 64), 1, 127, 'velocity'),
            'slot': integer(request.get('slot', 6), 1, 6, 'slot'), 'channel': CHANNEL + 1}


class KeyPress:
    """One API key at a time; independent of loops and physical input listeners.

    While transport runs, measure elapsed beats on its integrated timeline. Idle
    keys use the current Studio BPM. A pause cancels the key rather than holding
    a synth note indefinitely. The API never waits for the musical duration.
    """
    def __init__(self, send, timeline, report, clock=time.monotonic):
        self.send, self.timeline, self.report, self.clock = send, timeline, report, clock
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.worker = None
        self.state = {'status': 'idle', 'press_id': 0}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def start(self, spec):
        if self.worker and self.worker.is_alive():
            if self.snapshot()['status'] in ('queued', 'held'):
                raise ValueError('an API key is already held; use key-release or wait for key_released')
            self.worker.join()  # a client may react before the final event's reporter returns
        if self.timeline.paused:
            raise ValueError('resume transport before key-press')
        self.cancel.clear()
        with self.lock:
            self.state = {**spec, 'press_id': self.state['press_id'] + 1, 'status': 'queued', 'remaining_beats': spec['beats']}
            accepted = dict(self.state)
        self.worker = threading.Thread(target=self.run, args=(accepted,), name='orchid-api-key', daemon=True)
        self.worker.start()
        return accepted

    def stop(self):
        self.cancel.set()
        if self.worker:
            self.worker.join()
            self.worker = None

    def run(self, spec):
        player = Player(lambda message: self.send(spec['slot'], message), {CHANNEL})
        reason, error = 'duration', None
        previous = self.timeline.snapshot()
        last_time = self.clock()
        remaining = spec['beats']
        try:
            if self.cancel.is_set():
                reason = 'cancelled'
                return
            player.active.add((CHANNEL, spec['note']))
            player.send([0x90 | CHANNEL, spec['note'], spec['velocity']])
            with self.lock:
                self.state = {**self.state, 'status': 'held'}
            self.report({'event': 'key_pressed', **spec, 'status': 'sent', 'audibility': 'requires listener confirmation'})
            while remaining > 0:
                if self.cancel.wait(.002):
                    reason = 'cancelled'
                    break
                current = self.timeline.snapshot()
                now = self.clock()
                if current['paused']:
                    reason = 'paused'
                    break
                if previous['running'] and current['running']:
                    elapsed = current['beat'] - previous['beat']
                    if elapsed < 0:  # transport was replaced/reset
                        reason = 'transport_changed'
                        break
                else:
                    elapsed = (now - last_time) * current['bpm'] / 60
                remaining = max(0, remaining - elapsed)
                previous, last_time = current, now
                with self.lock:
                    self.state = {**self.state, 'remaining_beats': remaining}
        except Exception as exc:
            reason, error = 'error', str(exc)
        finally:
            try:
                player.panic()
            except Exception as exc:
                reason, error = 'error', str(exc)
            with self.lock:
                self.state = {**self.state, 'status': 'error' if error else 'released',
                              'remaining_beats': remaining, 'reason': reason, 'error': error}
            self.report({'event': 'key_press_error' if error else 'key_released',
                         'press_id': spec['press_id'], 'reason': reason, 'error': error})
