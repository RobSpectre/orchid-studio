# Studio drum machine

Studio now sequences and plays drum samples itself on macOS. Hydrogen is a source
of kits, not a live playback dependency when the native host is enabled.

```sh
scripts/build-pistil-host-macos.sh
.venv/bin/orchid-studio serve --api-port 8765 --api-only --sound-input Orchid --pistil-host
```

The six Pistil AUs and the sample player feed the same AVAudioEngine
and laptop output. Loops, live Perform and clip playback drive drums from their
own beat positions; the sample player has no independent BPM clock. MIDI and
sample attacks receive a 40 ms scheduling allowance on the host clock. The
sample callback places attacks within its audio buffer. This is internal
scheduling, not MIDI-clock synchronization with Orchid hardware. Python/IPC
jitter and plugin latency still need real listening/measurement; do not infer
heard audio from a render counter. Stop clears sample tails and drains scheduled
MIDI while the output is silent before releasing all notes.

## Make a beat

1. Choose **New beat**, or **Edit a copy** of a library beat. Originals remain
   available. New beats default to 12 bars; 1–64 bars are supported.
2. Click a sixteenth-note step to add/remove a hit. Shift-click gives an accent.
   New-hit strength/chance controls apply to newly added hits. Imported offset
   timing remains intact until that hit is removed.
3. Choose a sound independently for every lane, across any installed kits. Lane
   volume and mute, swing, additional lanes, Undo, clear-bar, copy-next-bar and
   repeat-bar-throughout are available.
4. **Save beat** writes it to the local library. Select it in Electronic beats
   for standalone drums, live Perform or loops. Edits to a currently selected
   playing beat apply on the next bar, as does selecting another beat.
5. **Export beat JSON** shares the rhythm and sound references. **Import beat
   JSON** validates and saves it. Install the referenced sounds on the destination
   computer first; samples are not embedded in beat JSON.

Saved beats persist under `local/drums/beats/`. Unsaved editor drafts do not
survive reload. Loop exports also include the selected beat document and drum
volume, in addition to notes and Pistil states. Imports validate sound references.

## Sound library

This Mac has 87 imported sounds across four kits:

| Kit | Sounds | Source metadata |
| --- | ---: | --- |
| TR808EmulationKit | 16 | ArtemioLabs, GPL; installed with Hydrogen |
| ElectricEmpireKit | 32 | ArtemioLabs, GPL |
| VariBreaks | 16 | Sineshine, GPL |
| Orchid Circuitry | 23 | Frequency 303 / Allan Legemaate, CC0; Studio edits |

Electronic kits come from Hydrogen's [official catalog](https://github.com/hydrogen-music/hydrogen-music/blob/main/feeds/drumkit_list.php).
Downloaded archives live in `local/drum-downloads/`; extracted samples, metadata
and author/license fields remain in the gitignored local library. The current
12 arrangements use the new Circuitry kit with distinct indie breaks, micro-house
and electro-pop grooves. See [Circuitry Vol. 2](INDIE_BEATS.md) for the source
packs, reproducible import and each groove’s suggested tempo. The original 808
arrangements remain the fallback when the new kit is absent.

**Add WAV sound…** imports a one-shot mono/stereo PCM WAV (up to 8 MB and 30 s).
Use **Installed kits & import** for a local Hydrogen kit directory or `.h2drumkit`
archive. Stop playback to import. Archive traversal, links and oversized archives
are rejected. Sound decoding is transactional: an unsupported kit leaves the
old native bank intact. The current sampler supports single-sample instruments
without Hydrogen-only pitch/FX processing, 92 loaded sounds, 128 simultaneous
voices and five minutes of decoded sample material. It decodes WAV and FLAC
through Apple's audio libraries and converts into the engine sample rate.
Samples retain their source licenses; a kit import does not change those terms.

## API

Use `capabilities`, `beats-list`, `kits-list`, and `status` for discovery.

```json
{"command":"beat-get","beat":"glass-house"}
{"command":"beat-save","document":{"kind":"orchid-beat","version":1,"id":"my-house","name":"My House","bars":12,"suggested_bpm":124,"swing":0.12,"lanes":[{"id":"kick","name":"Kick","sound":"tr808emulationkit-kick-short","gain":1,"muted":false}],"hits":[{"lane":"kick","beat":0,"velocity":0.7,"probability":1}]}}
{"command":"beats-select","beat":"my-house"}
{"command":"beats-play","beat":"my-house","bpm":124,"volume":0.5}
{"command":"loop-start","input":"Orchid","chord_channel":3,"settings":{"bpm":124},"drums":{"engine":"studio","beat":"my-house","volume":0.5}}
{"command":"kits-import","path":"/absolute/path/kit.h2drumkit"}
{"command":"sample-upload","name":"My hit","data":"BASE64_PCM_WAV","license":"User supplied"}
{"command":"sound-preview","sound":"tr808emulationkit-kick-short","velocity":0.5}
{"command":"drums","action":"volume","value":0.5}
{"command":"stop"}
```

`beat-save` supports up to 32 lanes and 8192 hits, unique lane/position pairs,
0–0.45 swing, 0.01–1 hit velocity, 0–1 hit probability and 0–1.5 lane gain. Hit
positions are quarter-note beats, so `.25` is a sixteenth note. All twelve source
beats remain 48 beats long. Engine `hydrogen` is accepted as a legacy alias;
`status.drums.sequencer.renderer` identifies the actual renderer.

`pistil-status.host.drums` reports loaded sounds, rendered attacks, late attacks,
maximum render lateness and signal peak. Lateness measures the drum callback
against requested host-clock deadlines, not perceived timing between instruments.
`status.drums.sequencer` reports active/pending beat, switch boundary, sent hits
and skipped stale hits. No late-hit burst is emitted after a stalled scheduler.

Native drums require the macOS host. The optional `--hydrogen` adapter remains
available for standalone fallback and source-kit diagnostics; its new Studio
sequencer triggers individual OSC notes with Hydrogen's transport stopped.
That fallback still has separate audio output and is not the preferred path.
Linux native sample-host support is not implemented.

## MIDI clock for other software and gear

Studio can publish a separate virtual MIDI source, **Orchid Studio Clock**:

```json
{"command":"clock-configure","enabled":true,"offset_ms":40}
{"command":"status"}
{"command":"clock-configure","enabled":false}
```

The browser has these controls under **Routing & MIDI clock**.
Connect another application's clock input to that source; for hardware, route
this source through your MIDI interface. Studio does not open a physical output
or send clock into Orchid. Enable clock receive/external sync on the follower.

Clock is 24 pulses per quarter note (`F8`), with Start (`FA`) on beat zero and
Stop (`FC`) on completion, Stop, panic or playback failure. It follows loops,
live Perform (including BPM changes), clip sessions and drums-only playback.
Count-in is excluded. Every launch starts at position zero. Pause sends Stop; resume sends Continue
and retains the frozen beat. No SPP or free-running idle clock is implemented. Output is opt-in each service launch.

Default delay is 40 ms, matching the native audio scheduling allowance. Change
`offset_ms` (0–500) while stopped to account for another device's latency. This
is a software-clock MIDI stream with OS scheduling jitter, not a sample-accurate
hardware clock. If the publisher stalls, it sends Stop and reports an error
instead of bursting a backlog; restart playback to establish a fresh downbeat.
Status includes enabled/running/error, pulse count, port, and delay.

## Audio host recovery

Before playback Studio checkpoints the five AU states locally. If the audio
child has exited, starting playback or **Restart audio** recreates it, restores
the last checkpoint and reloads samples. Notes remain in the main service.
`pistil-enable` is idempotent while healthy and a recovery command when dead.
Status now records the process exit code. Stop still stops surviving transports
when audio is gone. Recovery cannot reconstruct unsaved edits made after the
last sound checkpoint. Checkpoints live in gitignored `local/pistil-recovery.json`.


## More vibes

[Many Rooms](BEAT_VIBES.md) adds 12 contrasting electronic arrangements alongside
Circuitry: ambient, hip-hop, trip-hop, dub, disco house, garage, broken beat,
electro, D&B, half-time bass, progressive trance and footwork. Their API metadata
exposes vibe, tags, energy, density and suggested musical uses. The existing
samples are reused; no new download or sample-bank reload is necessary.
