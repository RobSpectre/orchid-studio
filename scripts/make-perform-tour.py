#!/usr/bin/env python3
"""Print an original synthetic-chord tour as a version-1 session; send no MIDI.

Usage: python scripts/make-perform-tour.py > local/perform-tour.json
Each named section is four beats. Playback at 96 BPM lasts 37.5 seconds.
"""
import json

from orchid_studio.perform import PerformanceEngine, PATTERNS
from orchid_studio.sequencer import compile_session


def tour():
    sections = [(mode, "tresillo") for mode in
                ("off", "strum", "strum2", "slop", "arp", "arp2", "harp", "pattern")]
    sections += [("pattern", pattern) for pattern in PATTERNS if pattern != "tresillo"]
    notes, labels = [], []
    for section, (mode, pattern) in enumerate(sections):
        active = {}
        tick = 0
        def send(message):
            kind, pitch, velocity = message[0] & 0xF0, message[1], message[2]
            if kind == 0x90 and velocity:
                active[pitch] = (tick, velocity)
            elif kind == 0x80 and pitch in active:
                start, attack_velocity = active.pop(pitch)
                notes.append({"beat": section * 4 + start / 1024,
                              "duration": (tick - start) / 1024,
                              "note": pitch, "velocity": attack_velocity})
        engine = PerformanceEngine(send, 3, 1,
            {"bpm": 60, "mode": mode, "pattern": pattern, "chord_window_ms": 0,
             "spread_beats": .5, "slop": .9, "velocity_limit": 64})
        repeating = mode in ("arp", "arp2", "pattern")
        labels.append({"beat": section * 4, "mode": mode,
                       **({"pattern": pattern} if mode == "pattern" else {})})
        for tick in range(4097):
            if tick == 0 or (not repeating and tick == 2048):
                for pitch in (48, 52, 55):
                    engine.receive([146, pitch, 64], tick / 1024)
            if tick == 3840 or (not repeating and tick == 1536):
                for pitch in (48, 52, 55):
                    engine.receive([130, pitch, 0], tick / 1024)
            engine.advance(tick / 1024)
        engine.panic()
        assert not active
    session = {"version": 1, "bpm": 96, "length_beats": len(sections) * 4,
               "description": "Original synthetic chords through software Perform; not a hardware recording",
               "sections": labels,
               "tracks": [{"name": "software-perform-tour", "channel": 1, "notes": notes}]}
    compile_session(session)
    return session


if __name__ == "__main__":
    print(json.dumps(tour(), indent=2))
