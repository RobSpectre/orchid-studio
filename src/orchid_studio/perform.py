"""Software-clocked Perform modes fed by one explicit raw-chord MIDI channel.

These are original software arrangements, not verified Orchid factory clones.
"""
import heapq
import math
import queue
import random
import time

from .melodies import MELODIES, PHRASE_UNITS, SONG_IMPORT_ERRORS, melodic_pitch
from .midi import VIRTUAL_PORT, backend, exact_port
from .sequencer import Player, integer, number

MODES = ("off", "strum", "strum2", "slop", "arp", "arp2", "pattern", "harp", *MELODIES)
# Four-beat loops: (onset, chord-note selector, gate length before gate scaling).
PATTERNS = {
    "pulse": tuple((b, "all", 1) for b in range(4)),
    "offbeat": tuple((b + .5, "all", .5) for b in range(4)),
    "backbeat": tuple((b, "all" if b % 2 else 0, 1) for b in range(4)),
    "tresillo": ((0, "all", 1.5), (1.5, "all", 1.5), (3, "all", 1)),
    "shuffle": tuple((b + t, b * 2 + i, d) for b in range(4)
                     for i, (t, d) in enumerate(((0, 2 / 3), (2 / 3, 1 / 3)))),
    "rising": tuple((i / 2, i, .5) for i in range(8)),
    "falling": tuple((i / 2, -i - 1, .5) for i in range(8)),
    "pendulum": tuple((i / 2, p, .5) for i, p in enumerate((0, 1, 2, 1, 0, 1, 2, 1))),
}
DEFAULTS = {"bpm": 96, "mode": "arp", "step_beats": .5, "gate": .75,
            "velocity_limit": 80, "spread_beats": .25, "harp_octaves": 3,
            "slop": .35, "seed": 0, "pattern": "pulse", "chord_window_ms": 8}


def settings(values):
    if not isinstance(values, dict) or set(values) - set(DEFAULTS):
        raise ValueError("perform settings: " + ", ".join(DEFAULTS))
    result = {**DEFAULTS, **values}
    number(result["bpm"], 30, 300, "bpm")
    if result["mode"] not in MODES:
        raise ValueError("mode must be " + ", ".join(MODES))
    if not isinstance(result["pattern"], str) or result["pattern"] not in PATTERNS:
        raise ValueError("pattern must be " + ", ".join(PATTERNS))
    number(result["step_beats"], .125, 4, "step_beats")
    number(result["gate"], .05, 1, "gate")
    integer(result["velocity_limit"], 1, 127, "velocity_limit")
    number(result["spread_beats"], 0, 4, "spread_beats")
    integer(result["harp_octaves"], 1, 4, "harp_octaves")
    number(result["slop"], 0, 1, "slop")
    integer(result["seed"], 0, 2**32 - 1, "seed")
    number(result["chord_window_ms"], 0, 50, "chord_window_ms")
    return result


def options():
    fields = {
        "bpm": ("number", 30, 300), "step_beats": ("number", .125, 4),
        "gate": ("number", .05, 1), "velocity_limit": ("integer", 1, 127),
        "spread_beats": ("number", 0, 4), "harp_octaves": ("integer", 1, 4),
        "slop": ("number", 0, 1), "seed": ("integer", 0, 2**32 - 1),
        "chord_window_ms": ("number", 0, 50),
    }
    schema = {key: {"type": kind, "minimum": low, "maximum": high,
                    "default": DEFAULTS[key]} for key, (kind, low, high) in fields.items()}
    schema.update({"mode": {"type": "string", "enum": list(MODES), "default": "arp"},
                   "pattern": {"type": "string", "enum": list(PATTERNS), "default": "pulse"}})
    from .catalog import perform_map, PATTERN_DESCRIPTIONS
    return {"mode_map":perform_map(MODES,MELODIES),"pattern_descriptions":dict(PATTERN_DESCRIPTIONS),"modes": list(MODES), "patterns": list(PATTERNS), "defaults": dict(DEFAULTS),
            "mode_banks": {"classic":[m for m in MODES if m not in MELODIES],
                           "melodies":[m for m in MELODIES if MELODIES[m].get("bank","melodies")=="melodies"],
                           "hooks":[m for m in MELODIES if MELODIES[m].get("bank")=="hooks"],
                           **({"songs":[m for m in MELODIES if MELODIES[m].get("bank")=="songs"]} if any(m.get("bank")=="songs" for m in MELODIES.values()) else {})},
            "song_import_errors":list(SONG_IMPORT_ERRORS),
            "settings_schema": {"type": "object", "properties": schema, "additionalProperties": False},
            "routing": {"input": "exact physical MIDI input name", "chord_channel": [1, 16],
                        "output_channel": [1, 16], "updates": "restart with perform to change routing"},
            "pattern_bank": "original software patterns; not Orchid factory patterns",
            "melodic_modes": {name:{"description":m["description"],"harmony":m["harmony"],"phrase_units":m.get("phrase_units",PHRASE_UNITS),
                             "label":m.get("label",name.upper()),"title":m.get("title",name.title()),
                             **({k:m[k] for k in ("source_file","source_beats","suggested_bpm","reference_note")} if "source_file" in m else {}),
                             "bank":m.get("bank","melodies"),"default_quality":"source" if "source_file" in m else "minor" if m.get("default_minor") else "major",
                             "bars_at_eighth_notes":m.get("phrase_units",PHRASE_UNITS)/8,"trigger":"hold a note or chord; release stops"}
                              for name,m in MELODIES.items()}}


class PerformanceEngine:
    def __init__(self, send, input_channel, output_channel, config, now=0):
        self.input_channel = integer(input_channel, 1, 16, "chord_channel") - 1
        self.output_channel = integer(output_channel, 1, 16, "output_channel") - 1
        self.config = settings(config)
        self.timeline=None
        self.player = Player(send, {self.output_channel})
        self.pressed, self.held, self.voices = {}, {}, {}
        self.sustain = False
        self.beat, self.last_time, self.last_tick = 0., now, -1
        self.index, self.pattern_tick = 0, -1
        self.pending = []
        self.melody_anchor = None
        self.melody_tick = -1
        self.dirty, self.retrigger, self.settle_until = False, False, now
        self.rng = random.Random(self.config["seed"])

    def _off(self, pitch):
        self.player.send([0x80 | self.output_channel, pitch, 0])
        self.player.active.discard((self.output_channel, pitch))
        self.voices.pop(pitch, None)

    def _all_off(self):
        for pitch in list(self.voices):
            self._off(pitch)
        self.pending.clear()

    def _on(self, pitch, velocity, end):
        if pitch in self.voices:
            self._off(pitch)
        self.voices[pitch] = end
        # Register before sending so panic can recover from a partial send failure.
        self.player.active.add((self.output_channel, pitch))
        self.player.send([0x90 | self.output_channel, pitch,
                          min(velocity, self.config["velocity_limit"])])

    def pitches(self):
        mode = self.config["mode"]
        if mode in MELODIES:
            if not self.held:return []
            velocity=min(self.held.values())
            return sorted({melodic_pitch(self.held,d,mode):velocity for _,d,_,_ in MELODIES[mode]["events"]}.items())
        octaves = self.config["harp_octaves"] if mode == "harp" else 2 if mode in ("arp2", "strum2") else 1
        result = dict(self.held)
        for octave in range(1, octaves):
            for pitch, velocity in self.held.items():
                if pitch + 12 * octave <= 127:
                    result.setdefault(pitch + 12 * octave, velocity)
        return sorted(result.items())

    def receive(self, message, now=None):
        if len(message) != 3 or message[0] & 15 != self.input_channel:
            return
        kind, pitch, value = message[0] & 0xF0, message[1], message[2]
        before = dict(self.held)
        attack = kind == 0x90 and value != 0
        if attack:
            self.pressed[pitch] = self.held[pitch] = value
        elif kind == 0x80 or (kind == 0x90 and not value):
            self.pressed.pop(pitch, None)
            if not self.sustain:
                self.held.pop(pitch, None)
        elif kind == 0xB0 and pitch == 64:
            self.sustain = value >= 64
            if not self.sustain:
                self.held = dict(self.pressed)
        elif kind == 0xB0 and pitch in (120, 123):
            self.pressed.clear()
            self.held.clear()
            self.sustain = False
        if before != self.held or attack:
            self.dirty = True
            self.retrigger |= attack
            self.settle_until = (self.last_time if now is None else now) + self.config["chord_window_ms"] / 1000
        allowed = dict(self.pitches())
        for sounding in list(self.voices):
            if sounding not in allowed:
                self._off(sounding)
        self.pending = [event for event in self.pending if event[1] in allowed]
        heapq.heapify(self.pending)
        if not self.held:
            self.melody_anchor=None
            self.melody_tick=-1
            self.index = 0
            self.retrigger = False

    def _clock(self, now):
        if self.timeline:
            self.beat=self.timeline.position(now);self.config["bpm"]=self.timeline.bpm
        else:self.beat += max(0, now - self.last_time) * self.config["bpm"] / 60
        self.last_time = max(self.last_time, now)
        for pitch, end in list(self.voices.items()):
            if end is not None and self.beat + 1e-9 >= end:
                self._off(pitch)

    def _sweep(self, pitches):
        self._all_off()
        mode = self.config["mode"]
        spacing = self.config["spread_beats"] / max(1, len(pitches) - 1)
        for i, (pitch, velocity) in enumerate(pitches):
            offset = 0 if mode == "off" else i * spacing
            if mode == "slop" and i:
                offset += self.rng.uniform(-.45, .45) * spacing * self.config["slop"]
                offset = min(self.config["spread_beats"], max(0, offset))
            end = self.beat + offset + self.config["step_beats"] * self.config["gate"] if mode == "harp" else None
            heapq.heappush(self.pending, (self.beat + offset, pitch, velocity, end))

    def advance(self, now):
        self._clock(now)
        if self.dirty and now + 1e-9 < self.settle_until:
            return
        pitches = self.pitches()
        mode = self.config["mode"]
        if self.dirty:
            if self.retrigger and mode in MELODIES:
                step=self.config['step_beats']
                tolerance=.05*self.config['bpm']/60
                self.melody_anchor=math.ceil((self.beat-tolerance)/step-1e-9)*step
                self.melody_tick=-1
            if self.retrigger and mode in ("off", "strum", "strum2", "slop", "harp"):
                self._sweep(pitches)
            self.dirty = self.retrigger = False
        # Stalled workers drop overdue sweep attacks, never flush a stale burst.
        tolerance = .05 * self.config["bpm"] / 60
        while self.pending and self.pending[0][0] <= self.beat + 1e-9:
            onset, pitch, velocity, end = heapq.heappop(self.pending)
            if self.beat - onset <= tolerance + 1e-9 and (end is None or end > self.beat):
                self._on(pitch, velocity, end)
        if mode in MELODIES:
            self._melody(mode,tolerance)
        elif mode in ("arp", "arp2"):
            step = self.config["step_beats"]
            tick = math.floor((self.beat + 1e-9) / step)
            if tick <= self.last_tick:
                return
            self.last_tick = tick
            if pitches:
                self._all_off()
                pitch, velocity = pitches[self.index % len(pitches)]
                self.index += 1
                self._on(pitch, velocity, self.beat + step * self.config["gate"])
        elif mode == "pattern":
            pattern = PATTERNS[self.config["pattern"]]
            cycle = math.floor((self.beat + 1e-9) / 4)
            due = [(i, event) for i, event in enumerate(pattern) if cycle * 4 + event[0] <= self.beat + 1e-9]
            if not due:
                return
            i, (offset, selector, duration) = due[-1]
            tick = cycle * len(pattern) + i
            if tick <= self.pattern_tick:
                return
            self.pattern_tick = tick
            onset = cycle * 4 + offset
            end = onset + duration * self.config["gate"]
            if pitches and self.beat - onset <= tolerance + 1e-9 and end > self.beat:
                self._all_off()
                selected = pitches if selector == "all" else [pitches[selector % len(pitches)]]
                for pitch, velocity in selected:
                    self._on(pitch, velocity, end)

    def _melody(self, mode, tolerance):
        if not self.held or self.melody_anchor is None or self.beat<self.melody_anchor-1e-9:
            return
        step=self.config['step_beats']
        phrase=MELODIES[mode]['events']
        length=MELODIES[mode].get("phrase_units",PHRASE_UNITS)*step
        cycle=math.floor((self.beat-self.melody_anchor+1e-9)/length)
        origin=self.melody_anchor+cycle*length
        due=[(i,event) for i,event in enumerate(phrase) if origin+event[0]*step<=self.beat+1e-9]
        if not due:return
        i,(offset,degree,duration,accent)=due[-1]
        tick=cycle*len(phrase)+i
        if tick<=self.melody_tick:return
        self.melody_tick=tick
        onset=origin+offset*step
        end=onset+duration*step*self.config['gate']
        if self.beat-onset>tolerance+1e-9 or end<=self.beat:return
        self._all_off()
        velocity=max(1,round(min(min(self.held.values()),self.config['velocity_limit'])*accent))
        self._on(melodic_pitch(self.held,degree,mode),velocity,end)

    def update(self, changes, now):
        config = settings({**self.config, **changes})
        self._clock(now)  # Integrate elapsed time using the old tempo.
        changed = {key for key in config if config[key] != self.config[key]}
        self.config = config
        if "seed" in changed:
            self.rng.seed(config["seed"])
        if changed - {"bpm", "velocity_limit"}:
            self._all_off()
            self.index = 0
            self.last_tick = math.floor((self.beat + 1e-9) / config["step_beats"])
            pattern = PATTERNS[config["pattern"]]
            cycle = math.floor((self.beat + 1e-9) / 4)
            self.pattern_tick = cycle * len(pattern) + sum(cycle * 4 + p[0] <= self.beat + 1e-9 for p in pattern) - 1
            self.dirty = self.retrigger = bool(self.held)
            self.settle_until = now

    def panic(self):
        self.pressed.clear()
        self.held.clear()
        self.pending.clear()
        self.sustain = self.dirty = self.retrigger = False
        self.melody_anchor=None
        self.melody_tick=-1
        try:
            self.player.panic()
        finally:
            self.voices.clear()


# Compatibility for clients using the initial arpeggiator API.
Arpeggiator = PerformanceEngine


class LivePerformance:
    def __init__(self, send, report, stop_event, *, input_name, chord_channel,
                 output_channel=1, config=None, drums=None, drum_config=None):
        if not isinstance(input_name, str) or not input_name.strip() or input_name == VIRTUAL_PORT:
            raise ValueError("perform requires an exact physical input, not the playback source")
        self.input_name = input_name
        self.chord_channel = integer(chord_channel, 1, 16, "chord_channel")
        self.output_channel = integer(output_channel, 1, 16, "output_channel")
        self.config = settings({} if config is None else config)
        self.send, self.report, self.stop_event = send, report, stop_event
        self.updates = queue.Queue(maxsize=64)
        self.drums, self.drum_config = drums, drum_config
        self.clock_output=None
        self.tempo_tick=None
        self.timeline=None

    def update(self, changes):
        settings({**self.config, **changes})
        try:
            self.updates.put_nowait(changes)
        except queue.Full:
            raise ValueError("too many pending performance updates")

    def run(self):
        source = backend().MidiIn()
        engine = None
        try:
            source.open_port(exact_port(source.get_ports(), self.input_name))
            source.ignore_types(sysex=True, timing=True, active_sense=True)
            if self.drum_config is not None:
                self.drums.start(self.config["bpm"], self.drum_config)
            if self.clock_output:self.clock_output.begin()
            engine = PerformanceEngine(self.send, self.chord_channel, self.output_channel,
                                self.config, time.monotonic())
            engine.timeline=self.timeline
            was_paused=False
            self.report({"event": "perform_ready", "input": self.input_name,
                         "chord_channel": self.chord_channel, "output_channel": self.output_channel,
                         "settings": self.config})
            next_check = time.monotonic() + 1
            while not self.stop_event.is_set():
                if self.timeline and self.timeline.paused:
                    if not was_paused:engine.panic();was_paused=True
                    if self.drums:self.drums.client.command('stop')
                    for _ in range(256):
                        if source.get_message() is None:break
                    self.stop_event.wait(.01);continue
                was_paused=False
                while not self.updates.empty():
                    changes = self.updates.get_nowait()
                    engine.update(changes, time.monotonic())
                    self.config = engine.config
                    if self.drum_config is not None and "bpm" in changes:
                        self.drums.command("bpm", self.config["bpm"])
                    self.report({"event": "perform_updated", "settings": self.config})
                # Drain a chord's note messages before producing the next tick.
                for _ in range(256):
                    packet = source.get_message()
                    if packet is None:
                        break
                    engine.receive(packet[0], time.monotonic())
                now = time.monotonic()
                if self.tempo_tick:self.tempo_tick()
                engine.advance(now)
                if self.clock_output:self.clock_output.advance(engine.beat,self.config["bpm"])
                if self.drum_config is not None:
                    self.drums.advance(engine.beat)
                if now >= next_check:
                    exact_port(source.get_ports(), self.input_name)
                    next_check = now + 1
                self.stop_event.wait(.002)
        finally:
            if self.clock_output:self.clock_output.stop()
            try:
                if engine is not None:
                    engine.panic()
            finally:
                try:
                    if self.drum_config is not None:
                        self.drums.stop()
                finally:
                    source.close_port()
                    source.delete()
