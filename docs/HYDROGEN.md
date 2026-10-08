> Superseded for live macOS playback: Studio now imports these samples and plays
> them in its native host alongside Pistil. See [Studio drums](DRUM_STUDIO.md).
> This document retains the optional Hydrogen setup and earlier validation history.

# Hydrogen drum machine

Orchid Studio uses Pistil standalone for pitched notes and Hydrogen for drums. The CLI/API sends local OSC to Hydrogen; no drum transport, clock or maintenance messages are sent to Orchid. No DAW is required. Live Orchid capture/overdub and independent Pistil patches are separate, unfinished milestones.

## Current electronic bank

The user requested synthesized drum-machine sounds suitable for D&B, house and
trance. The current bank is `local/electronic-12x12.h2song`: 12 original arrangements,
12 bars each, using installed **TR808EmulationKit** samples. The earlier GMRockKit
demo below remains an optional historical setup example. See [API.md](API.md) for
the catalog, suggested tempos, named selection, control page and generator.

The current arrangements use kicks, snares, claps and hats only. Tuned cowbell,
clave, conga and tom accents were removed after listening feedback, along with
extra shaker/crash layers. Fills are two quiet, grid-aligned snare taps; the
D&B breaks and house/trance offbeat hats retain their groove. Names, API IDs,
suggested tempos and 12-bar lengths are unchanged.

The 1.2.7 GUI size spinner displays no more than four bars; its loader/audio engine
retains the 12-bar bank entries. Full-bank export verified all 576 quarter-note
beats plus sample tails. Use Studio's catalog for lengths and avoid resizing the
bank through that spinner.

## macOS build and setup

The official Hydrogen 1.2.7 Mac download tested here is x86_64 and lacks compiled OSC support, even though its preferences show OSC controls. Enabling those preferences alone does not enable remote control. The project's native arm64 build uses unmodified official 1.2.7 source with `WANT_OSC=ON` and supported CoreAudio/PortAudio backends. All source, build products and local songs stay in Git-ignored `local/`; nothing is bundled with Orchid Studio.

Prerequisites are Apple's command-line developer tools and Homebrew. On the development Mac:

```sh
brew install cmake qt@5 liblo libsndfile libarchive pkgconf portaudio
scripts/build-hydrogen-macos.sh
mkdir -p local
.venv/bin/orchid-studio drums-song local/first-drums.h2song \
  --kit-directory local/hydrogen-runtime/hydrogen-1.2.7/data/drumkits/GMRockKit
scripts/run-hydrogen-macos.sh
```

The build script verifies the pinned source archive's SHA-256. The song generator refuses to overwrite a file; choose another name and pass it to the runner if the demo already exists. It creates two original four-beat patterns, `Studio Groove` and `Studio Variation`, using installed GMRockKit metadata. Samples remain in Hydrogen's data directory and retain their original license. Generated instruments disable MIDI output.

The runner selects PortAudio, which produced listener-confirmed live drums on the development Mac. Hydrogen's direct CoreAudio backend was silent on this machine even though its mixer moved; rendered WAV audio was audible. PortAudio uses the default output unless configured in Hydrogen's Audio System preferences. Enable OSC and OSC feedback at port 9000. The runner uses a project-local config and data directory and preserves existing settings. Only one Hydrogen instance should listen on this port. A project-local build is tied to the installed Homebrew libraries; it is not a distributable app bundle.

Sources: [official release](https://github.com/hydrogen-music/hydrogen/releases/tag/1.2.7), [build options](https://github.com/hydrogen-music/hydrogen/blob/1.2.7/CMakeLists.txt), [OSC registrations](https://github.com/hydrogen-music/hydrogen/blob/1.2.7/src/core/OscServer.cpp), [Hydrogen manual](https://hydrogen-music.org/documentation/manual/manual_en.html).

## CLI and agent API

Start `.venv/bin/orchid-studio serve --hydrogen` and select its persistent `Orchid Studio Playback` MIDI input in Pistil. Enter one JSON object per line, as separate actions:

```json
{"command":"drums","action":"bpm","value":96}
{"command":"drums","action":"pattern","value":0}
{"command":"drums","action":"volume","value":0.3}
{"command":"drums","action":"play"}
{"command":"drums","action":"pattern","value":1}
{"command":"drums","action":"strip-volume","strip":1,"value":0.6}
{"command":"drums","action":"strip-pan","strip":3,"value":-0.2}
{"command":"drums","action":"feedback"}
{"command":"stop"}
{"command":"panic"}
```

Patterns use zero-based indexes. Mixer strips use one-based indexes (GMRockKit: kick 1, snare 3, closed hat 7). Volume is 0–1.5; pan is -1–1; supported drum tempo is 30–300 BPM. Further actions: `pause`, `mute`, `unmute`, `mode` (`song`/`pattern`), `loop` (boolean), `kit` (installed kit name/directory), `open-song` (existing `.h2song` path), `strip-mute-toggle`, and `strip-solo-toggle`. Toggles are not idempotent. Kit/song changes and drum tempo/transport changes are rejected while a coordinated MIDI session is running; stop it first. Pattern and mixer changes remain available.

Without a running service, individual controls need no MIDI access:

```sh
.venv/bin/orchid-studio drums bpm 108
.venv/bin/orchid-studio drums strip-volume 0.6 --strip 1
.venv/bin/orchid-studio drums pattern 1 --dry-run
.venv/bin/orchid-studio drums panic
```

The adapter targets `127.0.0.1:9000` and binds a stable client port `127.0.0.1:9001`. Use the running service for controls when it owns 9001. Override ports with the CLI flags if needed. Hydrogen's own OSC listener may bind all interfaces; keep it on a trusted local setup and do not expose it through port forwarding. Commands return `sent` with `confirmed:false`; UDP has no delivery guarantee. Feedback is an observation, not a per-command acknowledgement or evidence of audible output.

## Layered sessions

`examples/layered-groove.json` has a four-beat performed clip, an eight-beat bass clip, and a sixteen-beat overall duration. The `drums` object selects the already-loaded Hydrogen pattern:

```json
{"engine":"hydrogen","pattern":0,"volume":0.3}
```

Send the complete example object in a service `play` request's `session` field, or use:

```sh
.venv/bin/orchid-studio play examples/layered-groove.json --hydrogen --wait 30
```

A session sets both engines' BPM and starts them together. End, stop, interruption and service EOF attempt cleanup on both. Panic additionally releases MIDI pedals/notes on all 16 software channels and mutes Hydrogen to silence sample tails. Starting the next drum session unmutes Hydrogen. MIDI semitone transpose does not transpose drum samples.

The MIDI scheduler and Hydrogen use separate clocks. OSC start latency and drift are not compensated; this is not phase-locked or sample-accurate synchronization. Shared-clock synchronization, quantized launches and captured Orchid overdubs remain future work. Pattern contents and kit/sample assignments are saved in `.h2song`, not embedded in the MIDI session. Reopen the same drum song before replaying a saved session.

## Validation scope

See [VALIDATION.md](VALIDATION.md) for actual listening results. Unit tests cover OSC encoding/index conventions, validation, cleanup, original song generation and independent clip repetition. Passing tests and moving meters do not establish audible audio or Linux support. Pistil on Linux remains unverified.
