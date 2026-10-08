"""Forward fresh Orchid Sound-dial reports to the software destination only.

Observed on this Orchid: channel-1 CC102 plus a 142-byte vendor sound-state report.
No raw MIDI API, hardware output, archived replay, or generic SysEx passthrough.
"""
import threading
import time

from .midi import VIRTUAL_PORT, backend, exact_port


def sound_report(message):
    if (len(message) == 3 and message[:2] == [0xB0, 102] and
            type(message[2]) is int and 0 <= message[2] < 100):
        return {"kind": "preset", "preset": message[2] + 1}
    if (len(message) == 142 and message[:5] == [0xF0, 0, 0x22, 0x0C, 0x34] and
            message[-1] == 0xF7 and all(type(b) is int and 0 <= b < 128 for b in message[5:-1]) and
            message[5] < 100):
        return {"kind": "sound-state", "preset": message[5] + 1}
    return None


class SoundFollower:
    def __init__(self, send, report, input_name):
        if not isinstance(input_name, str) or not input_name.strip() or input_name == VIRTUAL_PORT:
            raise ValueError("sound-follow needs an exact physical input name")
        self.send, self.report, self.input_name = send, report, input_name
        self.stop_event = threading.Event()
        self.state = {"enabled": True, "input": input_name, "status": "starting", "last_preset": None}
        self.thread = threading.Thread(target=self.run, name="orchid-sound-follow")

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join()
        self.state = {**self.state, "enabled": False, "status": "stopped"}

    def run(self):
        source = None
        try:
            source = backend().MidiIn()
            source.open_port(exact_port(source.get_ports(), self.input_name))
            source.ignore_types(sysex=False, timing=True, active_sense=True)
            self.state = {**self.state, "status": "ready"}
            self.report({"event": "sound_follow_ready", "input": self.input_name})
            next_check = time.monotonic() + 1
            while not self.stop_event.is_set():
                for _ in range(256):
                    packet = source.get_message()
                    if packet is None:
                        break
                    message = list(packet[0])
                    decoded = sound_report(message)
                    if decoded:
                        self.send(message)
                        self.state = {**self.state, "last_preset": decoded["preset"]}
                        self.report({"event": "sound_forwarded", **decoded, "destination": VIRTUAL_PORT})
                if time.monotonic() >= next_check:
                    exact_port(source.get_ports(), self.input_name)
                    next_check = time.monotonic() + 1
                self.stop_event.wait(.002)
        except Exception as exc:
            self.state = {**self.state, "status": "error", "error": str(exc)}
            self.report({"event": "sound_follow_error", "error": str(exc)})
        finally:
            if source is not None:
                source.close_port()
                source.delete()
