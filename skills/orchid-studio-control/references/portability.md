# Installation, portability and private transfers

## Supported scope

| Component | macOS Apple Silicon | macOS Intel | Windows / Linux |
| --- | --- | --- | --- |
| Python API, file formats, sequencing logic | Tested | Platform-neutral tests | Platform-neutral tests; OS MIDI differs |
| Six independent Pistil AUs + sample engine | Tested on development Mac | Builds locally for Intel; real-device playback pending | Not implemented |
| Installed Pistil | User installs/activates AU | Requires Intel-compatible AU and matching host architecture | Installing VST3 alone does not add a Studio host |
| Session transfer | Relocation round-trip tested | AU state compatibility needs confirmation | AU state is not a VST3 interchange format |

No second-Mac listening test has been completed. Use the checklist below before
relying on another machine for a performance. Linux/Wine/yabridge remains research,
not an installation dependency. macOS uses the installed AU identified as
`aumu / Pitl / Tptp`, found through the OS registry (system or user installation).

## Runtime data

`orchid-studio doctor` reports `data_dir`, plugin candidates and the host path.
`status.storage` exposes the running service's paths. The command never activates
or loads a plugin; presence alone does not confirm licensing or compatibility.

Resolution order:

1. `orchid-studio --data-dir /absolute/path COMMAND`, or `ORCHID_STUDIO_DATA_DIR`.
2. Existing source checkouts with a `local/` directory keep that directory.
3. New installs on macOS use `~/Library/Application Support/Orchid Studio`.
   The platform-neutral Python layer uses XDG data on Linux or LocalAppData on Windows.

Always use the same directory for build, backup and serve. `ORCHID_STUDIO_HOST`
can override the executable path for development. Logs, recovery state, sample
assets, beat edits, song MIDI and locally compiled host files live in the data
folder. Installed Python code is never the writable data location. Spaces in paths
are supported. A moved raw data directory still has absolute sample paths: use
**backup/restore** to relocate it rather than dragging the directory alone.

## Package installation (without editable source)

From a checkout, `python -m pip wheel --no-deps . --wheel-dir dist` builds a wheel.
Install that wheel with the MIDI extra, then build the bundled Swift source:

```sh
python3 -m venv studio-env
studio-env/bin/python -m pip install '/path/to/orchid_studio-0.1.0-py3-none-any.whl[midi]'
studio-env/bin/orchid-studio build-host
studio-env/bin/orchid-studio doctor --midi
studio-env/bin/orchid-studio serve --api-port 8765 --api-only --pistil-host \
  --sound-input Orchid --chord-channel 3
```

The wheel is platform-neutral Python/source; it does not contain a universal Mac
binary. Build on the destination architecture using its Apple tools. Use a native
Python/terminal and matching Pistil AU architecture. Do not copy a compiled ARM
host to an Intel Mac. Update Pistil through its licensed vendor installer.

## What moves

`backup FILE.zip --port 8765` asks the running API for a full `loop-export` and
packages the selected data folder. Finish/cancel recording first; it does not
stop an existing performance. For a consistent library snapshot, avoid editing
samples or beats during the backup. Existing backup files are never overwritten.

Included: loop notes and settings, six AU states and mixer values, selected drum
beat/length, all saved/current beat documents, referenced sample audio and source
license metadata, optional `perform-midi/songs.json` and its referenced MIDI files.
The archive uses relative sample paths with SHA-256 checksums. Source recordings,
plugin installers, binaries, logs and licensing/activation files are excluded.

Not included: unsaved browser beat drafts, UI focus/selection, API port, OS audio
route, MIDI port names, key-start/transport state, Play Along enable state or clock
publication setting. Reconfigure hardware-specific routing on the destination.
Saving a beat draft and exporting before shutting down prevents losing edits.
The application does not autosave the whole loop session at exit.

`restore ARCHIVE --to NEW_DIRECTORY` verifies checksums, validates notes and saved
beats, rejects unsafe paths/links, and reconstructs sample paths for the new Mac.
It refuses any existing destination, leaving other sessions untouched. Rebuild the
host in that directory, then pass `--session NEW_DIRECTORY/session.json` to serve.
Restore/launch does not start playback or arm a robot trigger automatically.

Transfer files are private user content. Copy only between devices you control
and for which your plugin/sample licenses permit use. The public source release
contains no supplied songs, sample audio, user patch states or Pistil binary.

## Fresh drum library

The host loads successfully with zero samples, so Pistil is usable before kit
installation. Import one-shot PCM WAVs through Sound library or Hydrogen kit
folders/`.h2drumkit` files through `kits-import`. Stop transport first. No running
Hydrogen process is needed. Native playback supports one sample per instrument;
bake pitch offsets into the sample before import. See [DRUM_STUDIO.md](drum-studio.md).

The original TR808-based beat documents require TR808EmulationKit. Circuitry and
Many Rooms use the installed sound IDs documented in their guides. A private
transfer preserves the development arrangement and all its sounds exactly;
a fresh public checkout cannot provide third-party samples automatically.

## Destination-Mac verification

1. `doctor --midi`: check native architecture, built host, AU candidate and exact input name.
2. Launch with the transferred session. Confirm `pistil-status.host.audio.running`
   and the desired output device; confirm no host error and expected sample count.
3. Check four loop voices, Live Perform and Play Along have the saved sounds and mixer values.
4. Listen to loops and drums together for several repeats; check tempo changes,
   pause/resume, independent patches and clean stop. Meters alone are insufficient.
5. Confirm Orchid's actual Performed/Bass/Chord channels and USB MIDI setting.
   Configure the exact input/raw Chord channel in Studio's MIDI settings. Press a
   fresh key with Start on key enabled; verify response and no doubled notes.
6. Save, quit, reopen with `--session`, and repeat playback. Test published clock
   with your external device if used; re-enable clock explicitly on this machine.

Use wired audio for the lowest live latency. Keep Bluetooth when preferred, with
its device buffering in mind; it does not change the shared musical timeline.
