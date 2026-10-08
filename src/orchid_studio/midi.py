"""Minimal MIDI I/O. Outputs are limited to known software destinations."""

from contextlib import contextmanager
import time


VIRTUAL_PORT = "Orchid Studio Playback"


def backend():
    try:
        import rtmidi
    except ImportError as exc:
        raise RuntimeError("Install orchid-studio[midi] to use MIDI I/O") from exc
    return rtmidi


def exact_port(ports, name):
    matches = [i for i, port in enumerate(ports) if port == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one exact MIDI port named {name!r}; found {len(matches)}")
    return matches[0]


@contextmanager
def software_output():
    output = backend().MidiOut()
    try:
        output.open_virtual_port(VIRTUAL_PORT)
        yield output
    finally:
        output.close_port()
        output.delete()


def monitor(name, seconds):
    """Read-only channel counts to establish actual hardware configuration."""
    source = backend().MidiIn()
    counts = {}
    try:
        source.open_port(exact_port(source.get_ports(), name))
        source.ignore_types(sysex=True, timing=True, active_sense=True)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            packet = source.get_message()
            if packet is None:
                time.sleep(0.002)
                continue
            message, _ = packet
            if not message or not 0x80 <= message[0] < 0xF0:
                continue
            channel = str((message[0] & 15) + 1)
            channel_counts = counts.setdefault(channel, {"note_on": 0, "note_off": 0, "controllers": 0, "other": 0})
            kind = message[0] & 0xF0
            if kind == 0x90 and len(message) == 3 and message[2]:
                label = "note_on"
            elif kind == 0x80 or (kind == 0x90 and len(message) == 3 and not message[2]):
                label = "note_off"
            elif kind == 0xB0:
                label = "controllers"
            else:
                label = "other"
            channel_counts[label] += 1
        return {"input": name, "seconds": seconds, "channels": counts, "sent_midi": False}
    finally:
        source.close_port()
        source.delete()
