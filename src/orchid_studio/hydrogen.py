"""Hydrogen 1.2.x OSC adapter. Local UDP control, independent of Orchid MIDI.

Paths/types verified against Hydrogen 1.2.7 src/core/OscServer.cpp.
Sending UDP is not an acknowledgement or evidence of audible output.
"""

import math
from pathlib import Path
import select
import socket
import struct
import subprocess
import shutil
import threading
import time

from .sequencer import integer, number


def diagnostics():
    from .paths import data_dir
    project = data_dir()
    paths = [project / "hydrogen-runtime/build/src/gui/hydrogen.app/Contents/MacOS/hydrogen",
             Path("/Applications/Hydrogen.app/Contents/MacOS/hydrogen")]
    if shutil.which("hydrogen"):
        paths.append(Path(shutil.which("hydrogen")))
    builds = []
    for path in dict.fromkeys(paths):
        if not path.is_file():
            continue
        entry = {"path": str(path)}
        try:
            result = subprocess.run([str(path), "--help"], capture_output=True, text=True, timeout=5)
            entry["osc_compiled"] = "--osc-port" in result.stdout
            entry["help_exit_code"] = result.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            entry["error"] = str(exc)
        builds.append(entry)
    return {"builds": builds, "control": "OSC UDP on 127.0.0.1:9000",
            "connection_verified": False}


def osc_string(value):
    if not isinstance(value, str) or "\0" in value:
        raise ValueError("OSC strings must be text without NUL characters")
    data = value.encode("utf-8") + b"\0"
    return data + b"\0" * (-len(data) % 4)


def encode_message(address, arguments=()):
    tags, payload = ",", b""
    for value in arguments:
        if isinstance(value, str):
            tags += "s"
            payload += osc_string(value)
        else:
            # Hydrogen registers even index/boolean controls with OSC float.
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("OSC arguments must be finite numbers or strings")
            tags += "f"
            payload += struct.pack(">f", float(value))
    return osc_string(address) + osc_string(tags) + payload


def decode_message(data):
    offset = 0
    def string():
        nonlocal offset
        end = data.index(b"\0", offset)
        value = data[offset:end].decode("utf-8")
        offset = (end + 4) & ~3
        return value
    address, tags = string(), string()
    if not address.startswith("/") or not tags.startswith(","):
        raise ValueError("invalid OSC message")
    arguments = []
    for tag in tags[1:]:
        if tag == "s":
            arguments.append(string())
        elif tag in "fi":
            arguments.append(struct.unpack_from(">" + tag, data, offset)[0])
            offset += 4
        else:
            raise ValueError(f"unsupported OSC feedback type: {tag}")
    return {"address": address, "arguments": arguments}


def command_message(action, value=None, strip=None):
    """Validate friendly controls and return their exact OSC representation."""
    if not isinstance(action, str):
        raise ValueError("Hydrogen action must be a string")
    simple = {"play": "PLAY", "stop": "STOP", "pause": "PAUSE",
              "mute": "MUTE", "unmute": "UNMUTE"}
    if action in simple:
        if value is not None or strip is not None:
            raise ValueError(f"{action} does not accept value or strip")
        return "/Hydrogen/" + simple[action], ()
    if action == "note-on":
        return "/Hydrogen/NOTE_ON", (integer(strip, 36, 127, "drum note"), number(value, 0, 1, "velocity"))
    if action in ("strip-volume", "strip-pan", "strip-mute-toggle", "strip-solo-toggle"):
        integer(strip, 1, 128, "strip (one-based)")
        if action.endswith("toggle"):
            if value is not None:
                raise ValueError("toggle commands do not accept value")
            name = "STRIP_MUTE_TOGGLE" if action == "strip-mute-toggle" else "STRIP_SOLO_TOGGLE"
            args = ()
        else:
            name = "STRIP_VOLUME_ABSOLUTE" if action == "strip-volume" else "PAN_ABSOLUTE_SYM"
            args = (number(value, 0 if action == "strip-volume" else -1,
                           1.5 if action == "strip-volume" else 1, action),)
        return f"/Hydrogen/{name}/{strip}", args
    if strip is not None:
        raise ValueError(f"{action} does not accept strip")
    if action == "bpm":
        return "/Hydrogen/BPM", (number(value, 30, 300, "Hydrogen bpm"),)
    if action == "volume":
        return "/Hydrogen/MASTER_VOLUME_ABSOLUTE", (number(value, 0, 1.5, "volume"),)
    if action == "pattern":
        return "/Hydrogen/SELECT_ONLY_NEXT_PATTERN", (integer(value, 0, 9999, "pattern (zero-based)"),)
    if action == "mode":
        if value not in ("song", "pattern"):
            raise ValueError("mode must be song or pattern")
        return "/Hydrogen/SONG_MODE_ACTIVATION", (float(value == "song"),)
    if action == "loop":
        if type(value) is not bool:
            raise ValueError("loop must be true or false")
        return "/Hydrogen/LOOP_MODE_ACTIVATION", (float(value),)
    if action == "kit":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("kit must name an installed Hydrogen kit or its directory")
        osc_string(value)
        return "/Hydrogen/LOAD_DRUMKIT", (value,)
    if action == "open-song":
        if not isinstance(value, str):
            raise ValueError("open-song requires a local .h2song path")
        path = Path(value).expanduser().resolve()
        if path.suffix != ".h2song" or not path.is_file():
            raise ValueError("open-song requires an existing .h2song file")
        return "/Hydrogen/OPEN_SONG", (str(path),)
    raise ValueError(f"unknown Hydrogen action: {action}")


def session_drums(session):
    drums = session.get("drums")
    if drums is None:
        return None
    if not isinstance(drums, dict) or set(drums) - {"engine", "pattern", "volume"}:
        raise ValueError("drums must contain engine, pattern and optional volume")
    if drums.get("engine") not in ("hydrogen", "studio"):
        raise ValueError("drums.engine must be studio (hydrogen is a legacy alias)")
    pattern = integer(drums.get("pattern"), 0, 9999, "drums.pattern")
    volume = number(drums.get("volume", 0.3), 0, 1.5, "drums.volume")
    return {"engine": "hydrogen", "pattern": pattern, "volume": volume}


class HydrogenClient:
    """One stable client port avoids growing Hydrogen's feedback registry.

    Only loopback is supported. Poll feedback explicitly; it is observation,
    not a guaranteed acknowledgement of each command.
    """
    def __init__(self, port=9000, client_port=9001):
        integer(port, 1024, 65535, "OSC port")
        integer(client_port, 1024, 65535, "OSC client port")
        if port == client_port:
            raise ValueError("server and client ports must differ")
        self.destination = ("127.0.0.1", port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("127.0.0.1", client_port))
        except OSError:
            self.socket.close()
            raise RuntimeError(f"OSC client port {client_port} is busy; use the running service or a different client port")
        self.lock = threading.Lock()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.socket.close()

    def command(self, action, value=None, strip=None):
        address, arguments = command_message(action, value, strip)
        with self.lock:
            self.socket.sendto(encode_message(address, arguments), self.destination)
        return {"status": "sent", "engine": "hydrogen", "address": address,
                "arguments": list(arguments), "confirmed": False}

    def feedback(self, seconds=0.1):
        number(seconds, 0, 2, "feedback wait")
        deadline = time.monotonic() + seconds
        messages = []
        with self.lock:
            for _ in range(256):
                ready, _, _ = select.select([self.socket], [], [], max(0, deadline - time.monotonic()))
                if not ready:
                    break
                data, sender = self.socket.recvfrom(65535)
                if sender != self.destination:
                    if time.monotonic() >= deadline:
                        break
                    continue
                try:
                    messages.append(decode_message(data))
                except (ValueError, UnicodeError, struct.error):
                    if time.monotonic() >= deadline:
                        break
                    continue
                if time.monotonic() >= deadline:
                    break
        return messages

    def start(self, bpm, drums):
        # Both engines use this tempo, but there is no shared audio clock yet.
        command_message("bpm", bpm)
        self.command("stop")
        self.command("bpm", bpm)
        self.command("mode", "pattern")
        self.command("pattern", drums["pattern"])
        self.command("volume", drums["volume"])
        self.command("unmute")
        self.command("play")

    def stop(self):
        return self.command("stop")

    def panic(self):
        try:
            self.stop()
        finally:
            # STOP may leave sample tails. Explicit mute silences the drum bus.
            self.command("mute")
