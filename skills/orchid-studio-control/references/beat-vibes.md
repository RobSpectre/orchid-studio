# Many Rooms — 12 additional electronic vibes

Twelve original 12-bar (48-beat), 4/4 arrangements. Adds to the existing Circuitry bank; no existing beat IDs are replaced. Descriptions express composition intent, not a claim of listener approval.

| Beat / API ID | BPM | Energy / density | Vibe and best use |
| --- | ---: | --- | --- |
| **Still Water** · `still-water` | 68 | low / sparse | A soft heartbeat surrounded by long silences; tiny clicks mark the horizon. Best for: Sustained pads, sparse robot melodies and slow introductions. |
| **Amber Tape** · `amber-tape` | 82 | low / medium | A lazy, swung pocket with low snares and short, dusty hats. Best for: Warm electric piano, intimate hooks and unhurried bass riffs. |
| **Black Velvet** · `black-velvet` | 92 | low / sparse | A heavy half-time backbeat with sparse kicks and a slow, shadowy sway. Best for: Moody chord beds, breathy lead sounds and lots of negative space. |
| **Dub Lantern** · `dub-lantern` | 118 | medium / sparse | A restrained four-on-the-floor pulse with widely spaced, dotted click answers. Best for: Long evolving chords, dub-style synth echoes and minimal arrangements. |
| **Peach District** · `peach-district` | 122 | medium / medium | A warm dance-floor bounce with steady kicks, a soft clap and answering pocket hats. Best for: Bright piano chords, playful bass and buoyant chorus hooks. |
| **Blue Platform** · `blue-platform` | 132 | medium / medium | A loping two-step kick pattern with swung offbeats and dry, clipped snare responses. Best for: Syncopated bass, vocal-style leads and nimble chord stabs. |
| **Broken Compass** · `broken-compass` | 112 | medium / medium | Interlocking 3–3–2 accents, displaced snares and uneven spaces that resolve every four bars. Best for: Angular bass motifs and call-and-response melodies. |
| **Chrome Messenger** · `chrome-messenger` | 126 | medium / medium | A dry drum-machine conversation: kick syncopation, handclap backbeats and precise ticks. Best for: Sequenced bass lines, robotic leads and clipped analog chords. |
| **Cloud Chaser** · `cloud-chaser` | 170 | high / busy | A rolling break with a firm snare backbeat, restrained ghost notes and soft, fast hats. Best for: Wide pads, flowing bass and spacious melodies over a fast rhythm. |
| **Velvet Gravity** · `velvet-gravity` | 140 | medium / sparse | A broad half-time snare with deep kicks and isolated hat responses; weight without a busy top end. Best for: Sub-heavy riffs and a strong lead that needs room to breathe. |
| **Horizon Engine** · `horizon-engine` | 138 | high / medium | A forward four-on-the-floor drive, soft offbeat hats and a measured lift across three phrases. Best for: Long arpeggios, suspended chords and gradual melodic builds. |
| **Paper Comet** · `paper-comet` | 154 | high / busy | Restless kick/clap exchanges and brief triplet hat answers; compact bursts separated by air. Best for: Short chopped hooks, playful bass phrases and rhythmic experiments. |

## Find and select a vibe

`beats-list` and `capabilities.beats` expose `bank`, `genre`, `feel`, `vibe`, `tags`, `energy`, `density`, `best_for`, `arrangement`, `bars` and `suggested_bpm`. `beat-get.document` returns the full editable arrangement with the same metadata. Older/custom beats may have null energy/density and empty tags; do not infer labels for those.

```json
{"command":"beats-list"}
{"command":"beat-get","beat":"blue-platform"}
{"command":"beats-select","beat":"blue-platform"}
{"command":"tempo","bpm":132}
```

Selecting a beat preserves global BPM and queues a live change to the next bar. Apply `tempo` only when you want to move the entire session. For standalone audition while stopped:

```json
{"command":"beats-play","beat":"still-water","bpm":68,"volume":0.3}
{"command":"stop"}
```

Use IDs, not numeric pattern indexes; user documents can change catalog ordering. `drums-length` still supports even 2–64-bar playback lengths. Sources remain 12 bars. Keep the selected arrangement and performance settings when auditioning alternatives; save `loop-export.document` first.

## Choose around a melody

- Most space: Still Water, Black Velvet, Velvet Gravity. Dub Lantern is a sparse steady pulse.
- Warm movement: Amber Tape, Peach District.
- Syncopated interplay: Blue Platform, Broken Compass, Chrome Messenger.
- More rhythmic activity: Cloud Chaser, Horizon Engine, Paper Comet. Use softer melody parts or lower drum level if these compete.
- Density describes hit activity; energy describes the intended feel at suggested tempo. Neither sets volume automatically.

## Sound palette and installation

The bank uses the installed, softened Orchid Circuitry kit plus selected 808/Electric Empire electronic kick, clap and click samples. No crash, open cymbal, bell, whistle or ringing accent is used. Source licenses and sample paths remain in `kits-list`; no audio binaries are bundled in source or beat JSON.

Factory defaults load from `vibe_beats.py` only when each groove’s required sounds are installed. Saved beat documents override defaults. The existing `local/` sample library and licensed sample metadata are preserved. `scripts/install-vibe-bank.py` adds missing IDs through the API and skips existing beats to preserve edits. It needs no stopped transport because no sample import/reload is performed.

Portable note-only beat documents: `examples/drums/many-rooms/*.json`. Install their referenced samples before importing with `beat-save`. The current Mac already has all required sounds. On another installation, inspect `kits-list`; do not silently substitute missing samples.

## Phrase structure

- **Still Water**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 6, 10.
- **Amber Tape**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 8.
- **Black Velvet**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 7.
- **Dub Lantern**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 8.
- **Peach District**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 9.
- **Blue Platform**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 5.
- **Broken Compass**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 10.
- **Chrome Messenger**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 7.
- **Cloud Chaser**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 9.
- **Velvet Gravity**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 8.
- **Horizon Engine**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 8.
- **Paper Comet**: Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: 6.

## Local preview audio

`local/many-rooms-previews/` contains full 12-bar offline WAV previews and level measurements. `five-vibes.wav` plays four bars each of Amber Tape, Dub Lantern, Blue Platform, Cloud Chaser and Paper Comet, with short gaps. This is sample-based preview mixing, separate from the live native host and listener confirmation.

Regenerate with `scripts/render-vibe-previews.py` in a Python environment with NumPy and the installed samples; FLAC conversion uses macOS `afconvert`.
