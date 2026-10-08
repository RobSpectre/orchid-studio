#!/usr/bin/env python3
"""Opt-in, finite hardware diagnostic; not the product's MIDI output path.

Only sends standard F8 clock, FA start, and FC stop to the exact Orchid port.
Never sends notes, CC, SysEx, firmware commands, or echoes received packets.
Start is tested separately because some clock receivers require transport.
"""
import argparse
import json
from pathlib import Path
import statistics
import threading
import time


PHASES = [("baseline", None, None), ("clock_90", 90, None),
          ("clock_137", 137, None), ("start_clock_90", 90, 0xFA),
          ("running_clock_137", 137, None), ("recovery", None, 0xFC)]
DURATION = 5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Actually run the authorized hardware test")
    parser.add_argument("--log", type=Path, default=Path("local/clock-test/capture.json"))
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({"destination": "Orchid", "seconds": 30,
                          "phases": PHASES, "allowed_status_bytes": [248, 250, 252],
                          "sent_midi": False}))
        return
    import rtmidi
    incoming, outgoing = rtmidi.MidiIn(), rtmidi.MidiOut()
    packets, phases, sent = [], [], []
    first_note = threading.Event()
    capture_lock = threading.Lock()
    origin = time.monotonic()
    started = False

    def receive(event, _):
        message, delta = event
        stamp = time.monotonic() - origin
        with capture_lock:
            packets.append({"time": stamp, "message": list(message)})
        if len(message) == 3 and message[0] & 0xF0 == 0x90 and message[2]:
            first_note.set()

    def send(status):
        if status not in (0xF8, 0xFA, 0xFC):
            raise ValueError("Diagnostic only allows clock/start/stop")
        outgoing.send_message([status])
        sent.append({"time": time.monotonic() - origin, "status": status})

    # Refuse to overwrite evidence before opening either port.
    with args.log.open("x") as log:
        try:
            for endpoint in (incoming, outgoing):
                names = endpoint.get_ports()
                if names.count("Orchid") != 1:
                    raise RuntimeError(f"Expected one exact Orchid port; found {names}")
                endpoint.open_port(names.index("Orchid"))
            incoming.ignore_types(sysex=True, timing=False, active_sense=True)
            incoming.set_callback(receive)
            print(json.dumps({"status": "armed", "instruction": "Hold one arpeggiated chord for 30 seconds; no tempo or Perform changes."}), flush=True)
            if not first_note.wait(120):
                raise RuntimeError("No note-on received within 120 seconds; no clock sent")
            for name, bpm, transport in PHASES:
                phase = {"name": name, "bpm_sent": bpm, "start": time.monotonic() - origin}
                phases.append(phase)
                print(json.dumps({"status": "phase", **phase}), flush=True)
                if transport is not None:
                    if transport == 0xFA:
                        started = True
                    send(transport)
                    if transport == 0xFC:
                        started = False
                deadline = origin + phase["start"] + DURATION
                next_tick = time.monotonic()
                while time.monotonic() < deadline:
                    if bpm is None:
                        time.sleep(min(.02, max(0, deadline - time.monotonic())))
                        continue
                    delay = next_tick - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    if time.monotonic() >= deadline:
                        break
                    send(0xF8)
                    next_tick += 60 / (bpm * 24)
                    # Do not burst a backlog of clocks after a scheduling stall.
                    if next_tick < time.monotonic() - .01:
                        next_tick = time.monotonic() + 60 / (bpm * 24)
                phase["end"] = time.monotonic() - origin
        finally:
            if started:
                send(0xFC)
            incoming.cancel_callback()
            incoming.close_port()
            outgoing.close_port()
            incoming.delete()
            outgoing.delete()
            with capture_lock:
                snapshot = list(packets)
            for phase in phases:
                begin, end = phase["start"] + 1, phase.get("end", time.monotonic() - origin)
                by_channel = {}
                for packet in snapshot:
                    msg, stamp = packet["message"], packet["time"]
                    if begin <= stamp < end and len(msg) == 3 and msg[0] & 0xF0 == 0x90 and msg[2]:
                        onsets = by_channel.setdefault(str((msg[0] & 15) + 1), [])
                        if not onsets or stamp - onsets[-1] > .01:
                            onsets.append(stamp)
                phase["channels"] = {}
                for channel, onsets in by_channel.items():
                    gaps = [b - a for a, b in zip(onsets, onsets[1:])]
                    phase["channels"][channel] = {"distinct_onsets": len(onsets),
                        "median_interval_ms": round(1000 * statistics.median(gaps), 3) if gaps else None}
            json.dump({"phases": phases, "received": snapshot, "sent": sent}, log, indent=2)
            log.write("\n")
            print(json.dumps({"status": "capture_saved", "log": str(args.log.resolve()), "phases": phases}), flush=True)


if __name__ == "__main__":
    main()
