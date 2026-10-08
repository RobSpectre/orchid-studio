"""Convert recorded performance notes to beats using incoming MIDI clock.

This module never opens an output. Clock, transport, CC and SysEx cannot become
playback events. Only the explicitly selected performed-note channel is imported.
"""
from bisect import bisect_right

from .sequencer import compile_session, integer, number


def session_from_capture(packets, *, channel, loop_beats, length_beats=None):
    integer(channel, 1, 16, "channel")
    number(loop_beats, .01, 4096, "loop_beats")
    length = loop_beats if length_beats is None else length_beats
    if not isinstance(packets, list):
        raise ValueError("capture must be a list of timestamped MIDI packets")
    for packet in packets:
        if not isinstance(packet, dict) or "time" not in packet or "message" not in packet:
            raise ValueError("each captured packet needs time and message")
        message = packet["message"]
        if not isinstance(message, list) or not message or any(type(v) is not int or not 0 <= v <= 255 for v in message):
            raise ValueError("captured messages must contain MIDI bytes")
    times = [number(p["time"], 0, 86400, "packet time") for p in packets]
    if times != sorted(times):
        raise ValueError("capture packets must be chronological")
    ticks = [p["time"] for p in packets if p["message"] == [0xF8]]
    if len(ticks) < 25:
        raise ValueError("capture needs at least one beat of incoming MIDI clock")
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    if min(gaps) <= 0 or max(gaps) > .25:
        raise ValueError("capture has duplicate or missing clock timestamps")

    def beat_at(stamp):
        if not ticks[0] <= stamp <= ticks[-1]:
            raise ValueError("clock must bracket the captured notes")
        i = min(bisect_right(ticks, stamp) - 1, len(ticks) - 2)
        return (i + (stamp - ticks[i]) / (ticks[i + 1] - ticks[i])) / 24

    active, notes, origin = {}, [], None
    clipped = 0

    def finish(pitch, end):
        start, velocity = active.pop(pitch)
        end = min(end, loop_beats)
        if end - start >= .001:
            notes.append({"beat": start, "duration": end - start,
                          "note": pitch, "velocity": velocity})

    for packet in packets:
        msg, stamp = packet["message"], packet["time"]
        if len(msg) != 3 or msg[0] & 15 != channel - 1 or msg[0] & 0xF0 not in (0x80, 0x90):
            continue
        pitch = integer(msg[1], 0, 127, "note")
        velocity = integer(msg[2], 0, 127, "velocity")
        on = msg[0] & 0xF0 == 0x90 and velocity > 0
        if origin is None:
            if not on:
                continue  # A key held before recording has no captured onset.
            origin = beat_at(stamp)
        position = beat_at(stamp) - origin
        if position >= loop_beats:
            break
        if pitch in active:
            finish(pitch, position)  # Release/retrigger the same pitch safely.
        if on:
            active[pitch] = (position, velocity)
    if origin is None or beat_at(ticks[-1]) - origin < loop_beats:
        raise ValueError("capture does not cover the requested note loop")
    for pitch in list(active):
        clipped += 1
        finish(pitch, loop_beats)
    bpm = round(60 * (len(ticks) - 1) / (24 * (ticks[-1] - ticks[0])), 3)
    session = {"version": 1, "bpm": bpm, "length_beats": length,
               "tracks": [{"name": "captured-performed", "channel": channel,
                           "loop_beats": loop_beats,
                           "notes": sorted(notes, key=lambda note: note["beat"])}],
               "capture": {"clock": "incoming MIDI clock, 24 PPQN",
                           "origin": "first selected note; not an inferred bar downbeat",
                           "source_channel": channel, "boundary_note_releases": clipped,
                           "controllers_recorded": False}}
    compile_session(session)
    return session
