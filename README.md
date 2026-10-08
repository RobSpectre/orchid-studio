# Orchid Studio

A software performance studio for **Telepathic Orchid + Pistil**: four loop layers,
two live voices, an editable sample drum machine, and one shared tempo and clock.
No GarageBand, DAW or running Hydrogen instance is required.

```text
Orchid USB MIDI (raw Chord channel)
  → Studio Perform / loop recording / direct Play Along
  → six independent installed Pistil Audio Units + sample drums
  → one native macOS audio engine → selected system output

Studio tempo → Perform + loops + drums + optional MIDI clock output
```

## Run on a Mac

Install and activate your own **Pistil Audio Unit**, Python **3.10+**, and Apple
Command Line Tools (`xcode-select --install`). The full host targets macOS 13+.
Apple Silicon has been tested locally. Intel builds from the same source but
needs a real Intel Mac playback check; Windows/Linux hosting is not implemented.

```sh
git clone https://github.com/RobSpectre/orchid-studio.git
cd orchid-studio
scripts/setup-macos.sh
scripts/start-macos.sh --sound-input Orchid --chord-channel 3
```

Open **http://127.0.0.1:8765/**. `setup-macos.sh` installs the Python MIDI dependency
and compiles only Studio's own Swift host for this Mac. It does not install or
activate Pistil. Run `orchid-studio doctor --midi` from `.venv/bin/` to check the
actual MIDI input name. Confirm Orchid's **raw Chord** channel on the instrument;
3 is an example, not a guaranteed device setting. Enable USB MIDI and avoid
monitoring the same notes through Pistil standalone at the same time.

A fresh install has no licensed samples or supplied song MIDI. Pistil can start
with an empty sample rack. Import your own WAVs/Hydrogen kits in **Sound library**,
or restore a private transfer bundle to bring over your existing sounds and beats.
Turn off **Start drums with loops** until the selected beat's samples are present.
Factory beat JSON is included; samples are not. A Hydrogen installation is not required.

## Move your existing Studio to another Mac

On the old Mac, with Studio running and no unfinished recording:

```sh
.venv/bin/orchid-studio backup ~/Desktop/orchid-studio-private.zip
```

Copy that **private** file to your other Mac. It contains the current loop session,
six AU patch states, mixer, drum library, beat edits and any supplied song MIDI.
It excludes Pistil binaries, activation data, caches, logs and source downloads.
Do not upload it to the public repo.

On the new Mac, after cloning and running setup:

```sh
.venv/bin/orchid-studio restore ~/Downloads/orchid-studio-private.zip \
  --to "$HOME/Music/Orchid Studio"
export ORCHID_STUDIO_DATA_DIR="$HOME/Music/Orchid Studio"
.venv/bin/orchid-studio build-host
scripts/start-macos.sh --sound-input Orchid --chord-channel 3 \
  --session "$ORCHID_STUDIO_DATA_DIR/session.json"
```

Restore refuses to overwrite an existing directory and relocates sample paths.
The session opens stopped. Verify your audio output and MIDI routing, then play
or enable **Start on key**. See [portability and verification](docs/PORTABILITY.md)
for fresh installation, package installation, backups and platform limits.

## Play and control

- Four loop layers retain independent Pistil sounds; select a different sound per layer.
- **Live Perform** generates phrases; **Play Along** plays raw keys directly.
- Global BPM controls all three sequencers. Optional output publishes 24-PPQN MIDI clock.
- **Space** pauses/resumes the whole Studio while the page has focus, except text entry.
- **Start on key**, below the loop layers, waits for a fresh raw Chord note.
  Stop/panic disarms it; pause retains it. Playback has no count-in; recording does.
- The drum editor changes steps, accents, lengths, swing and sounds. The Circuitry
  and Many Rooms arrangements become available as their required samples are installed.

The API is local-only; it binds to `127.0.0.1`, not the network. Agents use JSON:

```sh
.venv/bin/orchid-studio request '{"command":"status"}'
.venv/bin/orchid-studio request '{"command":"capabilities"}'
.venv/bin/orchid-studio request '{"command":"command-help","name":"key-start"}'
.venv/bin/orchid-studio request '{"command":"stop"}'
```

Use the [agent skill](skills/orchid-studio-control/SKILL.md),
[complete control map](docs/CONTROL_MAP.md), [API reference](docs/API.md),
[sounds and Perform map](docs/SOUND_PERFORM_MAP.md), [beat vibes](docs/BEAT_VIBES.md),
and [drum editor guide](docs/DRUM_STUDIO.md).

## Development

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[midi]'
.venv/bin/python -m unittest discover -s tests -v
node --test tests/test_studio_shortcuts.cjs
.venv/bin/orchid-studio build-host
```

Python tests and browser shortcut tests do not require a plugin or attached Orchid.
The native host build requires macOS and Apple's developer tools. The [CI template](scripts/ci-workflow.yml) covers Python, JavaScript, packaging and
native compilation; it is not active until copied to `.github/workflows/ci.yml`
using a GitHub credential with workflow permission. Proprietary plugin audio
cannot run in CI.
The wheel includes web assets and Swift source, so it also works outside a source checkout.
See [contribution notes](CONTRIBUTING.md).

Pistil and Orchid are third-party products. This project does not modify firmware,
query activation secrets, or send hardware maintenance commands. Native Orchid
Perform is not a verified MIDI-clock follower; Studio generates software Perform
from raw chords. Bluetooth output adds delay to live playing. See
[third-party content](THIRD_PARTY.md), [host details](docs/PISTIL_HOST.md), and
[Linux research status](docs/LINUX_PISTIL.md).
