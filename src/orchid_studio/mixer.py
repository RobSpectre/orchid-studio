"""Bounded mixer fades, serialized with API commands rather than musical transport."""
import copy
import threading
import time

from .pistil_host import SoundRouter
from .sequencer import number


CHANNELS = ('layer-1', 'layer-2', 'layer-3', 'layer-4', 'drums', 'live', 'play-along')
SCHEMA = {
    'channels': list(CHANNELS),
    'volume': {'min': 0, 'max': 1.5, 'unit': 'linear gain', 'unity': 1},
    'pan': {'min': -1, 'max': 1, 'center': 0},
    'transition_seconds': {'min': 0, 'max': 120, 'default': 0},
    'curves': ['linear', 'smoothstep'],
    'clock': 'monotonic seconds; continues while stopped or paused',
    'update_hz': 50,
}


def parse_set(request):
    allowed = {'command', 'id', 'channel', 'volume', 'pan', 'channels', 'transition_seconds', 'curve'}
    if set(request) - allowed:
        raise ValueError('unknown mixer request field')
    if 'channels' in request:
        if any(key in request for key in ('channel', 'volume', 'pan')):
            raise ValueError('use channels or channel/volume/pan, not both')
        changes = request['channels']
    else:
        channel = request.get('channel')
        if not isinstance(channel, str):
            raise ValueError('supply a mixer channel or channels object')
        changes = {channel: {key: request[key] for key in ('volume', 'pan') if key in request}}
    SoundRouter.validate_mix(changes)
    if not changes or any(not values for values in changes.values()):
        raise ValueError('supply volume or pan for each mixer channel')
    seconds = number(request.get('transition_seconds', 0), 0, 120, 'transition_seconds')
    curve = request.get('curve', 'linear')
    if curve not in ('linear', 'smoothstep'):
        raise ValueError('curve must be linear or smoothstep')
    return copy.deepcopy(changes), seconds, curve


class MixerAutomation:
    """Call set/cancel/advance/snapshot with the controller lock held."""
    def __init__(self, values, apply, report, lock, *, clock=time.monotonic):
        self.values, self.apply, self.report, self.lock = values, apply, report, lock
        self.clock = clock
        self.jobs = {}
        self.error = None
        self.stopping = threading.Event()
        self.worker = None

    def snapshot(self):
        return {'active': bool(self.jobs), 'channels': {
            channel: {key: copy.deepcopy(value) for key, value in job.items() if key != 'started'}
            for channel, job in self.jobs.items()}, 'error': self.error,
            'clock': 'monotonic', 'update_hz': 50}

    def set(self, changes, seconds, curve):
        self.cancel(list(changes))
        self.error = None
        if seconds == 0:
            for channel, values in changes.items():
                self.apply(channel, values)
            return
        started = self.clock()
        for channel, target in changes.items():
            self.jobs[channel] = {
                'from': {key: self.values[channel][key] for key in target},
                'target': dict(target), 'transition_seconds': seconds,
                'curve': curve, 'started': started, 'progress': 0,
            }
        if self.worker is None:
            self.worker = threading.Thread(target=self.run, name='orchid-mixer', daemon=True)
            self.worker.start()

    def cancel(self, channels=None):
        if channels is None:
            channels = list(self.jobs)
        if not isinstance(channels, list) or any(not isinstance(c, str) or c not in CHANNELS for c in channels):
            raise ValueError('channels must be a list of mixer channel names')
        cancelled = [c for c in channels if c in self.jobs]
        for channel in cancelled:
            self.jobs.pop(channel, None)
        return cancelled

    def advance(self):
        now = self.clock()
        completed = []
        try:
            for channel, job in list(self.jobs.items()):
                progress = min(1, max(0, (now - job['started']) / job['transition_seconds']))
                t = progress if job['curve'] == 'linear' else progress * progress * (3 - 2 * progress)
                values = {key: value if progress == 1 else job['from'][key] + (value - job['from'][key]) * t
                          for key, value in job['target'].items()}
                self.apply(channel, values)
                job['progress'] = progress
                if progress == 1:
                    del self.jobs[channel]
                    completed.append(channel)
        except Exception as exc:
            self.error = str(exc)
            self.jobs.clear()
            self.report({'event': 'mixer_error', 'error': self.error})
        if completed:
            self.report({'event': 'mixer_transition_completed', 'channels': completed})

    def run(self):
        while not self.stopping.wait(.02):
            with self.lock:
                if self.stopping.is_set():
                    return
                self.advance()

    def close(self):
        # Join outside the controller lock: the worker may be waiting for it.
        self.stopping.set()
        if self.worker:
            self.worker.join()
