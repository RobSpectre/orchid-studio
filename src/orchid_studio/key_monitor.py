"""Read-only record of Orchid key presses and voicing-dial clicks, for clients that check physical playing.

Observed on this Orchid (listening check, 2026-10-08): a key alone sends one note on the raw Chord
channel; a held chord button adds the rest of its chord at the same instant with one shared velocity,
and sends nothing itself. Velocity follows the strike (8-104 seen). Channel 1 mirrors the notes and is
ignored here. The voicing dial sends channel-1 CC115 whose value is the dial position, one step per
click; turning it can move the octave a key sounds in, so clients compare note names, not numbers.

Times are time.monotonic() at arrival, the same system clock other local processes read on macOS and
Linux. Opens an input only; never sends MIDI.
"""
from collections import deque
import threading
import time

from .midi import VIRTUAL_PORT, backend, exact_port

NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
CHORD_WINDOW_S = .008  # note-ons this close together are one press (Studio's chord_window_ms)
VOICING_CC = 115
HISTORY = 512


class KeyDecoder:
    """Turns raw MIDI into press, release and voicing events. Pure: the caller supplies arrival times."""

    def __init__(self, chord_channel=3):
        if type(chord_channel) is not int or not 1 <= chord_channel <= 16:
            raise ValueError("chord_channel must be 1-16")
        self.channel = chord_channel - 1
        self.pending = None  # a press still collecting notes inside the chord window
        self.held = {}  # sounding note -> its press
        self.voicing = None

    def feed(self, message, t):
        events = self.flush(t)
        if len(message) != 3 or not all(type(b) is int for b in message):
            return events
        status, data, value = message
        kind, channel = status & 0xF0, status & 0x0F
        if kind == 0x90 and value and channel == self.channel:
            if self.pending is None:
                self.pending = {"type": "press", "t": t, "notes": [], "velocity": value}
            self.pending["notes"].append(data)
        elif kind in (0x80, 0x90) and channel == self.channel:
            events += self.flush(t, force=True)
            events += self._silence(data, t)  # Orchid repeats note-offs; only the first counts
        elif kind == 0xB0 and channel == 0 and data == VOICING_CC:
            events.append({"type": "voicing", "t": t, "value": value,
                           "delta": None if self.voicing is None else value - self.voicing})
            self.voicing = value
        return events

    def flush(self, t, force=False):
        """Close the pending press once its chord window has passed."""
        press = self.pending
        if press is None or (not force and t - press["t"] <= CHORD_WINDOW_S):
            return []
        self.pending = None
        notes = sorted(set(press["notes"]))
        root = notes[0]
        event = {"type": "press", "t": press["t"], "root": root, "name": NAMES[root % 12], "octave": root // 12 - 1,
                 "notes": notes, "intervals": [n - root for n in notes], "velocity": press["velocity"]}
        events = [e for note in notes for e in self._silence(note, press["t"])]  # struck again while held
        record = {**event, "sounding": set(notes)}
        for note in notes:
            self.held[note] = record
        return events + [event]

    def _silence(self, note, t):
        """A held note stopped; its press is released once all of its notes have."""
        press = self.held.pop(note, None)
        if press is None:
            return []
        press["sounding"].discard(note)
        if press["sounding"]:
            return []
        return [{"type": "release", "t": t, "press_t": press["t"], "root": press["root"],
                 "name": press["name"], "held_s": round(t - press["t"], 4)}]


class KeyMonitor:
    def __init__(self, report, input_name, chord_channel=3, beat_at=None, clock=time.monotonic):
        if not isinstance(input_name, str) or not input_name.strip() or input_name == VIRTUAL_PORT:
            raise ValueError("key-monitor needs an exact physical input name")
        self.decoder = KeyDecoder(chord_channel)
        self.report, self.input_name, self.beat_at, self.clock = report, input_name, beat_at, clock
        self.lock = threading.Lock()
        self.history = deque(maxlen=HISTORY)
        self.last_id = 0
        self.stop_event = threading.Event()
        self.state = {"enabled": True, "input": input_name, "chord_channel": chord_channel, "status": "starting",
                      "presses": 0, "last_voicing": None, "error": None}
        self.thread = threading.Thread(target=self.run, name="orchid-key-monitor")

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join()
        self.state = {**self.state, "enabled": False, "status": "stopped"}

    def receive(self, message, t):
        with self.lock:
            self._record(self.decoder.feed(list(message), t))

    def _record(self, events):
        for event in events:
            beat = self.beat_at(event["t"]) if self.beat_at else None
            self.last_id += 1
            rounded = {k: round(event[k], 6) for k in ("t", "press_t") if k in event}  # a release names its press exactly
            self.history.append({**event, "id": self.last_id, **rounded, "beat": None if beat is None else round(beat, 4)})
            if event["type"] == "press":
                self.state = {**self.state, "presses": self.state["presses"] + 1}
            elif event["type"] == "voicing":
                self.state = {**self.state, "last_voicing": event["value"]}

    def events(self, after=0):
        with self.lock:
            self._record(self.decoder.flush(self.clock()))
            return {"events": [e for e in self.history if e["id"] > after], "last_key_event_id": self.last_id,
                    "truncated": bool(self.history and after < self.history[0]["id"] - 1), "now": round(self.clock(), 6)}

    def run(self):
        source = None
        try:
            source = backend().MidiIn()
            source.open_port(exact_port(source.get_ports(), self.input_name))
            source.ignore_types(sysex=True, timing=True, active_sense=True)
            source.set_callback(lambda packet, _: self.receive(packet[0], self.clock()))
            self.state = {**self.state, "status": "ready"}
            self.report({"event": "key_monitor_ready", "input": self.input_name,
                         "chord_channel": self.state["chord_channel"]})
            next_check = self.clock() + 1
            while not self.stop_event.is_set():
                with self.lock:
                    self._record(self.decoder.flush(self.clock()))
                if self.clock() >= next_check:
                    exact_port(source.get_ports(), self.input_name)
                    next_check = self.clock() + 1
                self.stop_event.wait(.005)
        except Exception as exc:
            self.state = {**self.state, "status": "error", "error": str(exc)}
            self.report({"event": "key_monitor_error", "error": str(exc)})
        finally:
            if source is not None:
                source.cancel_callback()
                source.close_port()
                source.delete()
