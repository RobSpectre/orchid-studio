"""JSON CLI for diagnostics and software-only MIDI playback."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import signal
import time
import threading
from pathlib import Path
from contextlib import nullcontext

from . import __version__


def tool_version(name):
    path = shutil.which(name)
    if not path:
        return {"available": False}
    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=5,
            check=False,
        )
        return {
            "available": True, "path": path, "exit_code": result.returncode,
            "version": (result.stdout or result.stderr).strip()[:1000],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "path": path, "error": str(exc)}


def _midi_inventory_local():
    try:
        import rtmidi
    except ImportError:
        return {"available": False, "hint": "Install orchid-studio[midi]."}
    result = {"available": True}
    for label, constructor in (("inputs", rtmidi.MidiIn), ("outputs", rtmidi.MidiOut)):
        endpoint = None
        try:
            endpoint = constructor()
            result[label] = endpoint.get_ports()
        except Exception as exc:
            result[label] = []
            result[label + "_error"] = str(exc)
        finally:
            if endpoint is not None:
                endpoint.delete()
    return result


def midi_inventory():
    # Some native backends abort instead of raising Python exceptions when OS
    # services are unavailable (including CoreMIDI in a sandbox).
    try:
        child = subprocess.run(
            [sys.executable, "-c", "import json; from orchid_studio.cli import _midi_inventory_local; print(json.dumps(_midi_inventory_local()))"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if child.returncode:
            return {"available": False, "error": "MIDI backend could not initialize",
                    "exit_code": child.returncode,
                    "detail": child.stderr.strip()[:1000],
                    "hint": "Run in a local terminal with access to the OS MIDI service."}
        return json.loads(child.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"available": False, "error": str(exc)}


def diagnose(include_midi=False):
    from .hydrogen import diagnostics as hydrogen_diagnostics
    system = platform.system()
    home = Path.home()
    from .paths import data_dir, host_path
    report = {
        "orchid_studio": __version__, "system": system,
        "data_dir": str(data_dir()), "native_host": {"supported": system == "Darwin",
            "path": str(host_path()), "built": host_path().is_file()},
        "release": platform.release(), "architecture": platform.machine(),
        "python": platform.python_version(), "python_executable": sys.executable,
        "pistil_linux_status": "unverified; no official native Linux release listed",
        "hydrogen": hydrogen_diagnostics(),
    }
    if system == "Linux":
        os_release = Path("/etc/os-release")
        report["os_release"] = os_release.read_text() if os_release.exists() else None
        report["session_type"] = os.environ.get("XDG_SESSION_TYPE")
        report["tools"] = {name: tool_version(name) for name in ("wine", "yabridgectl")}
        roots = [home / ".vst3", home / ".local/share/orchid-studio/wine-pistil/drive_c/Program Files/Common Files/VST3"]
    elif system == "Darwin":
        report["macos"] = platform.mac_ver()[0]
        roots = [Path("/Library/Audio/Plug-Ins/VST3"), Path("/Library/Audio/Plug-Ins/Components"), home / "Library/Audio/Plug-Ins/VST3", home / "Library/Audio/Plug-Ins/Components"]
        report["pistil_standalone_present"] = Path("/Applications/Pistil.app").exists()
    elif system == "Windows":
        roots = [Path(os.environ.get("COMMONPROGRAMFILES", "C:/Program Files/Common Files")) / "VST3"]
    else:
        roots = []
    report["plugin_search_roots"] = [str(root) for root in roots]
    report["pistil_candidates"] = []
    for root in roots:
        if root.is_dir():
            # Only inspect names; never load third-party plugins in the diagnostic.
            report["pistil_candidates"].extend(str(path) for path in root.glob("*Pistil*"))
            report["pistil_candidates"].extend(str(path) for path in root.glob("*/*Pistil*"))
    if include_midi:
        report["midi"] = midi_inventory()
    return report


_output_lock = threading.Lock()


def emit(value):
    with _output_lock:
        print(json.dumps(value), flush=True)


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(description="Orchid Studio software MIDI tools")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--data-dir", type=Path, help="Writable state directory (or ORCHID_STUDIO_DATA_DIR)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build-host", help="Build the native macOS Pistil host with Apple Command Line Tools")
    backup = commands.add_parser("backup", help="Export a PRIVATE session, samples and supplied MIDI transfer bundle")
    backup.add_argument("output", type=Path)
    backup.add_argument("--port", type=int, default=8765)
    restore = commands.add_parser("restore", help="Restore a transfer bundle into a new data directory; never overwrite")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--to", type=Path, required=True)
    commands.add_parser("beats-list", help="List the 12 original electronic drum arrangements; send no MIDI")
    api_request = commands.add_parser("request", help="Send a JSON command to the running local HTTP API")
    api_request.add_argument("json", help="JSON object, or - to read stdin")
    api_request.add_argument("--port", type=int, default=8765)
    commands.add_parser("perform-options", help="List software Perform modes, patterns and defaults; send no MIDI")
    doctor = commands.add_parser("doctor", help="Read platform and plugin setup; send no MIDI")
    doctor.add_argument("--midi", action="store_true", help="Also enumerate MIDI endpoint names")
    demo = commands.add_parser("demo", help="Play an original four-bar phrase through a software host")
    play = commands.add_parser("play", help="Play a version-1 JSON note session")
    play.add_argument("session", type=Path)
    for command in (demo, play):
        command.add_argument("--bpm", type=float, help="Software playback tempo (20–300)")
        command.add_argument("--transpose", type=int, default=0, help="Semitone shift (-48–48); not Orchid's chord key")
        command.add_argument("--repeats", type=int, default=1)
        command.add_argument("--wait", type=float, default=0, help="Seconds to connect the host before playback (0–120)")
        command.add_argument("--dry-run", action="store_true", help="Print scheduled MIDI without opening ports")
    demo.add_argument("--write-session", type=Path, help="Write an editable JSON demo instead of playing")
    server = commands.add_parser("serve", help="Keep the virtual port open; accept JSON lines on stdin")
    server.add_argument("--api-port", type=int, help="Enable the HTTP API on 127.0.0.1 at this port")
    server.add_argument("--api-only", action="store_true", help="Run until API quit or signal, without reading stdin")
    server.add_argument("--pistil-host", action="store_true", help="Load six instances of the installed Pistil AU (macOS only)")
    server.add_argument("--sound-input", help="Follow fresh Sound-dial reports from this exact physical input")
    server.add_argument("--chord-channel", type=int, default=3, choices=range(1,17), help="Confirmed raw Chord MIDI channel for Play Along")
    server.add_argument("--session", type=Path, help="Restore saved loop JSON after host startup; does not play automatically")
    server.add_argument("--drum-bank", type=Path, help="Generated electronic .h2song path for beats-load")
    for command in (server, demo, play):
        command.add_argument("--hydrogen", action="store_true", help="Enable local Hydrogen OSC control")
        command.add_argument("--hydrogen-port", type=int, default=9000)
        command.add_argument("--hydrogen-client-port", type=int, default=9001)
    drums_cmd = commands.add_parser("drums", help="Control Hydrogen using local OSC (no MIDI required)")
    drums_cmd.add_argument("action", choices=["play", "stop", "pause", "mute", "unmute", "panic",
        "bpm", "volume", "pattern", "mode", "loop", "kit", "open-song", "strip-volume",
        "strip-pan", "strip-mute-toggle", "strip-solo-toggle"])
    drums_cmd.add_argument("value", nargs="?")
    drums_cmd.add_argument("--strip", type=int)
    drums_cmd.add_argument("--port", type=int, default=9000)
    drums_cmd.add_argument("--client-port", type=int, default=9001)
    drums_cmd.add_argument("--dry-run", action="store_true")
    drum_song = commands.add_parser("drums-song", help="Write original Hydrogen patterns using an installed kit")
    drum_song.add_argument("output", type=Path)
    drum_song.add_argument("--kit-directory", type=Path, required=True)
    drum_song.add_argument("--bpm", type=float, default=96)
    drum_song.add_argument("--bank", choices=("demo", "electronic"), default="demo")
    watch = commands.add_parser("monitor", help="Read channel activity from an exact input; sends no MIDI")
    capture = commands.add_parser("import-capture", help="Convert timestamped received notes/clock into a software loop; sends nothing")
    capture.add_argument("capture", type=Path)
    capture.add_argument("output", type=Path)
    capture.add_argument("--channel", type=int, required=True)
    capture.add_argument("--loop-beats", type=float, required=True)
    capture.add_argument("--length-beats", type=float)
    watch.add_argument("--input", required=True)
    watch.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args(argv)
    if args.data_dir:
        os.environ['ORCHID_STUDIO_DATA_DIR'] = str(args.data_dir.expanduser().resolve())
    try:
        if args.command == "build-host":
            from .build_host import build_host
            emit(build_host())
            return 0
        if args.command == "backup":
            from .api_client import request as api_call
            from .transfer import export_bundle
            from .paths import data_dir
            current = api_call({'command':'status'}, args.port)
            if current.get('status') == 'error':raise RuntimeError(current['error'])
            if current['looper']['record_slot']:raise ValueError('Finish or cancel the active take before backing up')
            paths = current.get('storage')
            if paths and Path(paths['data_dir']).resolve() != data_dir().resolve():
                raise ValueError('Use --data-dir matching the running server: ' + paths['data_dir'])
            result = api_call({'command':'loop-export'}, args.port)
            if result.get('status') == 'error':raise RuntimeError(result['error'])
            emit(export_bundle(args.output, result['document']))
            return 0
        if args.command == "restore":
            from .transfer import import_bundle
            emit(import_bundle(args.archive, args.to))
            return 0
        if args.command == "request":
            from .api_client import request as api_call
            payload = json.loads(sys.stdin.read() if args.json == "-" else args.json)
            result = api_call(payload, args.port)
            emit(result)
            return 1 if result.get("status") == "error" else 0
        if args.command == "beats-list":
            from .beats import BANK_NAME, catalog
            emit({"bank": BANK_NAME, "beats": catalog()})
            return 0
        if args.command == "perform-options":
            from .perform import options
            emit(options())
            return 0
        if args.command == "doctor":
            emit(diagnose(args.midi))
            return 0
        if args.command == "import-capture":
            from .capture import session_from_capture
            data = json.loads(args.capture.read_text())
            if not isinstance(data, dict) or not isinstance(data.get("received"), list):
                raise ValueError("capture file must contain a received packet list")
            session = session_from_capture(data["received"], channel=args.channel,
                                           loop_beats=args.loop_beats, length_beats=args.length_beats)
            with args.output.open("x") as handle:
                json.dump(session, handle, indent=2)
                handle.write("\n")
            emit({"status": "written", "path": str(args.output.resolve()),
                  "source_bpm": session["bpm"], "notes": len(session["tracks"][0]["notes"]), "sent_midi": False})
            return 0
        if args.command == "drums-song":
            from .drum_song import write_demo_song, write_electronic_song
            writer = write_electronic_song if args.bank == "electronic" else write_demo_song
            emit(writer(args.output, args.kit_directory, args.bpm))
            return 0
        if args.command == "serve" and args.pistil_host and platform.system() != "Darwin":
            raise ValueError('The full Pistil host supports macOS only; Windows/Linux hosting is not implemented.')
        from .midi import VIRTUAL_PORT, monitor, software_output
        from .sequencer import Player, compile_session, demo_session, number
        from .hydrogen import HydrogenClient, command_message, session_drums
        if args.command == "drums":
            value = args.value
            if value is not None and args.action not in {"kit", "open-song", "mode"}:
                value = json.loads(value)
            if args.action == "panic":
                if value is not None or args.strip is not None:
                    raise ValueError("panic takes no value or strip")
                address, arguments = "/Hydrogen/STOP + /Hydrogen/MUTE", ()
            else:
                address, arguments = command_message(args.action, value, args.strip)
            if args.dry_run:
                emit({"status": "dry_run", "address": address, "arguments": arguments})
                return 0
            with HydrogenClient(args.port, args.client_port) as drums:
                if args.action == "panic":
                    drums.panic()
                    result = {"status": "sent", "action": "panic", "confirmed": False}
                else:
                    result = drums.command(args.action, value, args.strip)
                emit({**result, "feedback": drums.feedback()})
            return 0
        if args.command == "monitor":
            number(args.seconds, 0.1, 120, "seconds")
            emit(monitor(args.input, args.seconds))
            return 0
        if args.command == "serve":
            from .service import serve
            if args.api_only and args.api_port is None:
                raise ValueError("--api-only requires --api-port")
            if args.api_port is not None:
                from .sequencer import integer
                integer(args.api_port, 1024, 65535, "API port")
            previous = signal.signal(signal.SIGTERM, interrupted)
            try:
                with (HydrogenClient(args.hydrogen_port, args.hydrogen_client_port) if args.hydrogen else nullcontext()) as drums, software_output() as output:
                    emit({"status": "ready", "output": VIRTUAL_PORT})
                    serve(output.send_message, sys.stdin, emit, drums=drums, api_port=args.api_port,
                          api_only=args.api_only, drum_bank=args.drum_bank, sound_input=args.sound_input, pistil_host=args.pistil_host,
                          chord_channel=args.chord_channel, session=args.session)
            finally:
                signal.signal(signal.SIGTERM, previous)
            emit({"status": "closed", "cleanup": "sent"})
            return 0
        session = demo_session() if args.command == "demo" else json.loads(args.session.read_text())
        events, bpm, length, channels = compile_session(
            session, transpose=args.transpose, repeats=args.repeats, bpm=args.bpm,
        )
        number(args.wait, 0, 120, "wait")
        drum_config = session_drums(session)
        if drum_config is not None:
            command_message("bpm", bpm)
            if not args.hydrogen and not args.dry_run:
                raise ValueError("session uses Hydrogen; add --hydrogen")
        if args.command == "demo" and args.write_session:
            # Never overwrite an existing composition implicitly.
            with args.write_session.open("x") as handle:
                json.dump(session, handle, indent=2)
                handle.write("\n")
            emit({"status": "written", "path": str(args.write_session.resolve())})
            return 0
        summary = {"bpm": bpm, "transpose": args.transpose, "length_beats": length,
                   "duration_seconds": length * 60 / bpm, "note_events": len(events),
                   "output": VIRTUAL_PORT, "channels": [c + 1 for c in sorted(channels)], "drums": drum_config}
        if args.dry_run:
            emit({"status": "dry_run", **summary, "events": [
                {"beat": e.beat, "message": list(e.message), "track": e.track} for e in events]})
            return 0
        previous = signal.signal(signal.SIGTERM, interrupted)
        try:
            with (HydrogenClient(args.hydrogen_port, args.hydrogen_client_port) if args.hydrogen else nullcontext()) as drums, software_output() as output:
                emit({"status": "ready", **summary, "wait_seconds": args.wait})
                player = Player(output.send_message, channels)
                # The wait occurs before any MIDI is sent.
                time.sleep(args.wait)
                try:
                    if drum_config is not None:
                        drums.start(bpm, drum_config)
                    player.play(events, bpm, length)
                finally:
                    if drum_config is not None:
                        drums.stop()
        finally:
            signal.signal(signal.SIGTERM, previous)
        emit({"status": "completed", **summary, "cleanup": "sent", "audibility": "requires listener confirmation"})
    except KeyboardInterrupt:
        emit({"status": "stopped"})
        return 130
    except (ValueError, OSError, RuntimeError) as exc:
        emit({"status": "error", "error": str(exc)})
        return 1
    return 0
