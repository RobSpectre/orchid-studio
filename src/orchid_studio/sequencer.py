"""Portable, beat-based note clips. No plugin or hardware dependencies."""

from dataclasses import dataclass
import math
import time


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer from {low} to {high}")
    return value


def number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


@dataclass(frozen=True)
class Event:
    beat: float
    message: tuple
    track: str


def demo_session():
    """An original, quiet four-bar phrase; only one part for host verification."""
    return {
        "version": 1,
        "bpm": 96,
        "length_beats": 16,
        "tracks": [{
            "name": "performed", "channel": 1,
            "notes": [
                {"beat": beat, "duration": 0.65, "note": note, "velocity": 48}
                for beat, note in enumerate([60, 64, 67, 71, 57, 60, 64, 67,
                                             53, 57, 60, 64, 55, 59, 62, 67])
            ],
        }],
    }


def compile_session(session, *, transpose=0, repeats=1, bpm=None):
    """Validate the entire clip before opening any output, then schedule notes.

    Channels are explicit and one-based in JSON. Each track owns its channel;
    raw chord/performed stream merging is deliberately absent.
    """
    if not isinstance(session, dict) or type(session.get("version")) is not int or session["version"] != 1:
        raise ValueError("session must be an object with version 1")
    tempo = number(session.get("bpm") if bpm is None else bpm, 20, 300, "bpm")
    length = number(session.get("length_beats"), 0.01, 4096, "length_beats")
    integer(transpose, -48, 48, "transpose")
    integer(repeats, 1, 128, "repeats")
    tracks = session.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 16:
        raise ValueError("tracks must contain 1 to 16 tracks")
    events, channels, names = [], set(), set()
    for track in tracks:
        if not isinstance(track, dict):
            raise ValueError("each track must be an object")
        name = track.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("track names must be nonempty and unique")
        names.add(name)
        channel = integer(track.get("channel"), 1, 16, "channel") - 1
        if channel in channels:
            raise ValueError("each track must have a distinct output channel")
        channels.add(channel)
        loop_length = number(track.get("loop_beats", length), 0.01, length, "loop_beats")
        cycles = round(length / loop_length)
        if not math.isclose(cycles * loop_length, length, abs_tol=1e-9):
            raise ValueError("length_beats must be an exact multiple of each track's loop_beats")
        notes = track.get("notes")
        if not isinstance(notes, list) or len(notes) > 10000:
            raise ValueError("notes must be a list of at most 10000 notes")
        validated = []
        for note in notes:
            if not isinstance(note, dict):
                raise ValueError("each note must be an object")
            start = number(note.get("beat"), 0, loop_length, "beat")
            duration = number(note.get("duration"), 0.001, loop_length, "duration")
            pitch = integer(note.get("note"), 0, 127, "note") + transpose
            integer(pitch, 0, 127, "transposed note")
            velocity = integer(note.get("velocity", 64), 1, 127, "velocity")
            if start + duration > loop_length:
                raise ValueError("notes must end within their track's loop_beats")
            validated.append((start, duration, pitch, velocity))
        ends = {}
        for start, duration, pitch, velocity in sorted(validated):
            if start < ends.get(pitch, -1):
                raise ValueError("overlapping copies of the same note on one track are ambiguous")
            ends[pitch] = start + duration
            if len(events) + 2 * repeats * cycles > 200000:
                raise ValueError("session exceeds the 200000-event playback limit")
            for repeat in range(repeats * cycles):
                offset = repeat * loop_length
                events.extend([
                    Event(offset + start, (0x90 | channel, pitch, velocity), name),
                    Event(offset + start + duration, (0x80 | channel, pitch, 0), name),
                ])
    # Release before retrigger when two notes meet at the same tick.
    events.sort(key=lambda event: (event.beat, event.message[0] & 0xF0 != 0x80))
    return events, tempo, length * repeats, channels


class Player:
    """Synchronous transport with injected MIDI and clock APIs for testing."""

    def __init__(self, send, channels, *, clock=time.monotonic, sleep=time.sleep):
        self.send = send
        self.channels = set(channels)
        self.active = set()
        self.clock = clock
        self.sleep = sleep

    def panic(self):
        # Attempt every release even if one send fails (e.g. disconnected host).
        messages = [(0x80 | ch, note, 0) for ch, note in sorted(self.active)]
        for channel in sorted(self.channels):
            messages.extend((0xB0 | channel, cc, 0) for cc in (64, 66, 123, 120))
        errors = []
        for message in messages:
            try:
                self.send(list(message))
            except Exception as exc:
                errors.append(exc)
        self.active.clear()
        if errors:
            raise RuntimeError(f"MIDI cleanup failed for {len(errors)} messages") from errors[0]

    def play(self, events, bpm, length_beats, tick=None, timeline=None):
        seconds_per_beat = 60 / bpm
        origin = self.clock()
        def wait_until(beat):
            if timeline is not None:
                paused_notes=None
                while True:
                    if timeline.paused:
                        if paused_notes is None:
                            paused_notes=set(self.active);self.panic()
                        self.sleep(.002);continue
                    if paused_notes is not None:
                        for ch,note in paused_notes:self.send([0x90|ch,note,64])
                        self.active=paused_notes;paused_notes=None
                    current=timeline.position()
                    if tick and current<length_beats:tick(current)
                    if current>=beat:return
                    self.sleep(.002)
            deadline = origin + beat * seconds_per_beat
            if tick is None:
                self.sleep(max(0, deadline-self.clock()))
                return
            while True:
                now = self.clock()
                current = (now-origin)/seconds_per_beat
                if current < length_beats:
                    tick(current)
                if now >= deadline:
                    break
                self.sleep(min(.002, deadline-now))
        try:
            for event in events:
                wait_until(event.beat)
                status, note, velocity = event.message
                key = (status & 15, note)
                if status & 0xF0 == 0x90 and velocity:
                    self.active.add(key)
                self.send(list(event.message))
                if status & 0xF0 == 0x80 or (status & 0xF0 == 0x90 and not velocity):
                    self.active.discard(key)
            wait_until(length_beats)
        finally:
            self.panic()
