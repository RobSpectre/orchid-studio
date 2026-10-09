"""Read-only port inventory, polled off the transport/API threads."""
import threading
import time


class MidiConnection:
    def __init__(self, inventory=None, clock=time.monotonic):
        if inventory is None:
            from .cli import midi_inventory
            inventory = midi_inventory
        self.inventory = inventory
        self.clock = clock
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.worker = None
        self.checked_at = None
        self.inputs = []
        self.error = None

    def refresh(self):
        try:
            result = self.inventory()
            if not result.get('available') or result.get('inputs_error'):
                raise RuntimeError(result.get('inputs_error') or result.get('error') or 'MIDI inventory unavailable')
            inputs = result.get('inputs')
            if not isinstance(inputs, list) or any(not isinstance(p, str) for p in inputs):
                raise RuntimeError('MIDI inventory unavailable')
            error = None
        except Exception as exc:
            inputs, error = [], str(exc)
        with self.lock:
            self.inputs, self.error, self.checked_at = inputs, error, self.clock()

    def snapshot(self, input_name='Orchid'):
        with self.lock:
            stale = self.checked_at is None or self.clock() - self.checked_at > 3
            known = not stale and self.error is None
            connected = input_name in self.inputs if known else None
            return {'input': input_name, 'connected': connected,
                    'state': 'connected' if connected else 'disconnected' if known else 'unknown',
                    'error': self.error, 'stale': stale,
                    'meaning': 'MIDI input port presence; not proof of key messages or audible output'}

    def start(self):
        def run():
            while not self.stop_event.is_set():
                self.refresh()
                self.stop_event.wait(1)
        self.worker = threading.Thread(target=run, name='orchid-midi-connection', daemon=True)
        self.worker.start()

    def close(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=.2)
