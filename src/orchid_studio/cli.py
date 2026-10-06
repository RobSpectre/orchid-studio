"""Read-only diagnostics. No MIDI ports are opened and no messages are sent."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

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


def midi_inventory():
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


def diagnose(include_midi=False):
    system = platform.system()
    home = Path.home()
    report = {
        "orchid_studio": __version__, "system": system,
        "release": platform.release(), "architecture": platform.machine(),
        "python": platform.python_version(), "python_executable": sys.executable,
        "pistil_linux_status": "unverified; no official native Linux release listed",
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Orchid Studio setup diagnostics")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Read platform and plugin setup; send no MIDI")
    doctor.add_argument("--midi", action="store_true", help="Also enumerate MIDI endpoint names")
    args = parser.parse_args(argv)
    print(json.dumps(diagnose(args.midi), indent=2))
    return 0
