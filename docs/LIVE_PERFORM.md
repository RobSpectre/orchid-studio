# Live software Perform

The eight original Perform categories and ten single-key melody modes are implemented in software. The user
confirmed live raw-chord → software Arp → Pistil playback on 2026-10-07. The user also confirmed hearing the synthetic mode tour. The new modes have
automated timing and cleanup coverage; exact audible comparison with Orchid
is still needed. These are original software arrangements, not verified copies
of Orchid's factory algorithms or Pattern bank.

Orchid Studio owns BPM. Only the explicitly selected raw Chord input channel feeds
this engine; Performed, Bass and hardware clock/transport are ignored. Generated
notes go exclusively through `Orchid Studio Playback` to Pistil. No notes are sent
back into Orchid. Hydrogen still has an independent clock (see below).

## Setup and API

Enable USB MIDI on Orchid. This device's confirmed channel assignments are
Performed 1, Bass 2, Chord 3. Check those assignments again on other devices or
when configuration changes. Raw chord note-ons were observed together on channel
3 in a fresh passive capture. Keep Orchid's physical volume down to avoid hearing
its local synth alongside Pistil; software routing does not mute its speaker.

Start `orchid-studio serve --hydrogen`. In Pistil's Audio/MIDI Settings select only
`Orchid Studio Playback` for this route. Preserve the current patch and laptop
output. Reconnect that input after restarting the service. Send separate JSON lines:

```json
{"command":"perform","input":"Orchid","chord_channel":3,"output_channel":1,"settings":{"bpm":96,"mode":"arp","velocity_limit":72}}
{"command":"perform-update","settings":{"mode":"strum2","spread_beats":0.25}}
{"command":"perform-update","settings":{"mode":"pattern","pattern":"tresillo"}}
{"command":"perform-update","settings":{"bpm":120}}
{"command":"perform-options"}
{"command":"stop"}
{"command":"panic"}
```

The standalone `orchid-studio perform-options` lists modes, bank IDs and defaults
without opening MIDI. `perform_ready` confirms input setup, not audible sound.
Watch for `playback_error`. Updates are queued; `perform_updated` confirms that the
worker applied them. Stop, panic, EOF and input disconnect release notes and
pedals and close the input. Disconnect is checked once per second.

## Modes

| ID | Behavior |
| --- | --- |
| `off` | Play the entire chord together; hold until release. |
| `strum` | Ascending one-shot sweep; each note holds until release. |
| `strum2` | Strum the chord plus one octave above. |
| `slop` | One-shot strum with seeded timing variation, maintaining pitch order. |
| `arp` | Repeat ascending held pitches on the software step grid. |
| `arp2` | Repeat ascending pitches across the chord plus one octave above. |
| `pattern` | Repeat a selected four-beat software rhythm, independent of chord size. |
| `harp` | One-shot ascending multi-octave sweep with gated note tails. |

Octave expansion deduplicates pitches and stays within MIDI range. One-shot modes
retrigger on a new chord attack, not on a held chord's every beat. Releasing notes
cancels their pending attacks and releases their sounding voices immediately.
Sustain CC64 retains pitches until pedal-up; CC120/123 clears the chord. Other
controllers are ignored. Mode changes release old voices and cancel pending
sweeps. Repeating modes join the next grid event; one-shot modes replay held notes.

The implementations follow the broad categories in the vendor's
[Perform guide](https://support.telepathicinstruments.com/hc/en-us/articles/15280943220367-Exploring-Performance-Modes-Arp-Strum-Pattern-and-More).
Exact ordering, retrigger rules, timing, modulation and factory Pattern contents
require fresh hardware comparisons. Hardware Perform controls do not automatically
select these software modes; use `perform-update`.

## Original Pattern bank

All loops are four quarter-note beats. Integer note selectors wrap through the
sorted held chord, so changing chord size changes pitches without changing rhythm.

| ID | Rhythm / voicing |
| --- | --- |
| `pulse` | Whole chord on each quarter note. |
| `offbeat` | Whole chord on each eighth-note offbeat. |
| `backbeat` | Lowest note on beats 1/3, whole chord on 2/4. |
| `tresillo` | Whole chord at beat offsets 0, 1.5, 3 (3+3+2 eighth notes). |
| `shuffle` | Ascending note selections with a 2:1 long/short rhythm. |
| `rising` | Eight ascending note selections, one per eighth note. |
| `falling` | Eight descending note selections, one per eighth note. |
| `pendulum` | Note ranks 0,1,2,1,0,1,2,1 on eighth notes. |

## Controls and timing

| Setting | Default | Range / purpose |
| --- | --- | --- |
| `bpm` | 96 | 30–300; software tempo, quarter-note beats. |
| `step_beats` | 0.5 | 0.125–4; arp spacing and harp tail length before gate scaling. |
| `gate` | 0.75 | 0.05–1; arp step, pattern cell or harp tail fraction. |
| `spread_beats` | 0.25 | 0–4; total duration from first to last one-shot attack. |
| `harp_octaves` | 3 | 1–4; number of chord octaves in Harp. |
| `slop` | 0.35 | 0–1; timing variation, up to ±45% of note spacing. |
| `seed` | 0 | Integer 0–4294967295; reproducible Slop random sequence. |
| `pattern` | `pulse` | Bank ID above. |
| `velocity_limit` | 80 | 1–127; cap, preserving quieter input velocities. |
| `chord_window_ms` | 8 | 0–50; wait after chord mutations to group incoming packets. |

Tempo-only changes preserve accumulated beat position, held voices and pending
beat-based sweep timing. Most other musical setting changes retrigger/rejoin as
for a mode change. Velocity-limit changes apply to future attacks. Missed arp
steps are skipped; sweep/pattern attacks over 50 ms late are dropped to avoid a
burst after a scheduler stall. Python/OS scheduling is not sample-accurate.

Optional top-level `"drums":{"engine":"hydrogen","pattern":0,"volume":0.3}`
starts the loaded Hydrogen pattern at the same BPM; live BPM updates also send its
new tempo. This is coordinated tempo/transport over OSC, not phase-locked shared
transport. Shared clock integration with Hydrogen and simultaneous live looping
remain separate work.

## Reproducible listening tour

Generate a synthetic chord tour from the actual engine (no hardware recording or
MIDI output during generation):

```sh
.venv/bin/python scripts/make-perform-tour.py > local/perform-tour.json
orchid-studio play local/perform-tour.json --dry-run
orchid-studio play local/perform-tour.json --wait 10
```

Stop any existing live service before standalone playback, then select the newly
created `Orchid Studio Playback` input in Pistil during the wait. The tour contains
15 four-beat sections: Off, Strum, Strum 2, Slop, Arp, Arp 2, Harp, then Tresillo,
Pulse, Offbeat, Backbeat, Shuffle, Rising, Falling and Pendulum. Playback lasts
37.5 seconds at 96 BPM. Its `sections` metadata records each section's beat offset.

## Sound dial

Direct Orchid note input stays disabled in Pistil. Use API `sound-follow` or start
with `--sound-input Orchid` to forward fresh Sound-dial preset/state reports through
Studio Playback. This keeps the chosen timbre synchronized without duplicating
notes or changing the software Perform settings. It is active even with playback
stopped; disable it to keep an independent Pistil patch. The physical 49 → 50 → 49
check was verified in Pistil as **049 — FM BONGO**. See [API.md](API.md).

## Five single-key melody modes

These original software phrases expand one held note into a melody. Releasing
all notes stops generated pitches immediately (sustain holds until pedal-up).
They also accept Orchid's raw chord stream on its configured Chord channel.
They use the lowest held note as root. Explicit major/minor voicings are selected
from the held chord's third; a single note defaults to major, except Orbit, which
uses Dorian minor. Inversions follow the lowest supplied note. These are composed
harmonic studies, not a full chord-recognition or generative-composition engine.

| Mode | Harmonic / melodic design |
| --- | --- |
| `bloom` | Imaj9(#11)–vi9–ii9–V13, with a rising motif and guide-tone answer. Minor uses i9–VImaj9–iv9–V7(b9). |
| `orbit` | Dorian i9–IV13–i11–V7sus, 3–3–2 accents and octave turns. Major chords select a major variant. |
| `drift` | Sparse thirds, sevenths, ninths and anticipations over I–iii–vi–ii/V. |
| `spark` | Chromatic upper/lower enclosures resolving to chord tones through ii–V–I; altered dominant tension resolves to tonic. |
| `tide` | I6/9–IVmaj9–borrowed ivm6–Imaj9, with an ascending arc and descending resolution. |

Chromatic pitches are intentional passing/approach tones; explicit minor variants
preserve dominant leading tones instead of snapping all notes into a fixed scale.
The harmony is implied by a monophonic melody, not additional chord accompaniment.

Each phrase lasts 32 note divisions: four bars at the default eighth-note
setting. Changing Note Division stretches/compresses the phrase; Gate controls
note length and Velocity Limit caps its accented dynamics. Rhythm selection is
unused for these melodic modes and disabled in the UI. The phrases are deterministic,
so recording and step-entry bake the same generated melody into loop layers.
A fresh key/chord joins the nearby/next division boundary and starts the phrase;
stalls drop missed attacks rather than bursting them. No key is latched by default.
They share the tempo/Bézier clock and keep existing recorded layers unchanged.

```json
{"command":"perform-configure","settings":{"mode":"bloom","step_beats":0.5,"gate":0.75}}
{"command":"perform-update","settings":{"mode":"tide"}}
```

`capabilities.melodic_modes` describes each new mode and trigger behavior. The
Perform dial has Classic, Melodies and Hooks banks; the eight original modes and
Pattern rhythms remain in Classic.


## Five original hooks

Select **Hooks** in the Perform Bank menu. These are original four-bar melodies
inspired by the broad musical directions in the user's song references, not
transcriptions, covers or reproductions of those songs. Each has a recurring
opening cell and a contrasting final answer, using space and repetition to make
the phrase memorable. Harmony is implied by a single melodic line.

| Mode | Direction and composition |
| --- | --- |
| `sunline` | Warm synth-pop: syncopation, add9/suspended colors, a rising answer. |
| `sidekick` | Bright power-pop: repeated-note refrain, clipped attacks, borrowed minor iv. |
| `electric` | Minor dance-pop: a compact hook, chromatic fifth approach, altered-dominant resolution. |
| `bluehour` | Lyrical jazz ballad: longer breath-shaped notes, delayed resolutions and a chromatic turnaround. |
| `anthem` | Arena rock: strong rhythmic call, octave lift and a sustained high tonic answer. |

Electric and Anthem default to minor for a single key; Sunline, Sidekick and
Bluehour default to major. A held chord's third selects the major/minor variant,
just as with the earlier melodies. Hold/release, sustain, transposition from the
lowest note, note division, gate, recording and shared clock behavior are identical.
No original recording or sample from a referenced song is used. API mode IDs are
independent of the browser's dial bank:

```json
{"command":"perform-configure","settings":{"mode":"sunline","step_beats":0.5,"gate":0.75}}
```

`capabilities.mode_banks` lists all modes by bank; `melodic_modes` adds `bank`
and `default_quality` so agents can discover them without relying on UI labels.


## User-supplied MIDI song phrases

The **Songs** Perform bank reads the user's local MIDI snippets at service startup
from `local/perform-midi/songs.json`. Each entry has `id` (prefixed `song-`),
`label`, `title` and a MIDI `file` in that same directory. These source files stay
in ignored local storage and are separate from bundled original compositions.
Only monophonic format 0/1 PPQN files up to 64 bars are accepted. Polyphonic,
percussion and unterminated-note imports fail explicitly. Controllers, program
changes and SysEx are never forwarded. A malformed optional library is skipped;
`capabilities.song_import_errors` reports why, without disabling existing modes.

Installed from the five supplied files:

| API mode | Dial label | Source notes | Phrase / loop beats |
| --- | --- | --- | --- |
| `song-africa` | AFRICA | 7 | 6 / 8 |
| `song-buddy-holly` | BUDDY | 9 | 6 / 8 |
| `song-kissed-a-girl` | KISSED | 7 | 7 / 8 |
| `song-porgy` | PORGY | 8 | 9 / 12 |
| `song-prayer` | PRAYER | 8 | 4 / 4 |

Hold C4 (MIDI 60) to hear the supplied register, or another key to transpose by
its distance from C4. A chord uses its lowest note; major/minor quality does not
rewrite imported intervals. Hold repeats; release stops; sustain applies.
Set Note Division to 1/8 and Gate to 1 for source durations. Other settings scale
timing/gates deliberately. Source velocity ratios are preserved under the held
key's velocity and velocity limit. Studio BPM overrides file tempo; source BPM
is exposed as metadata only. Initial rests are preserved, and trailing silence
pads each phrase to whole 4/4 bars. Porgy's three-bar cycle will rotate against a
four-bar loop, while still sharing the same clock. These are the supplied short
snippets, not complete song arrangements or independently verified transcriptions.

```json
{"command":"perform-configure","settings":{"mode":"song-africa","step_beats":0.5,"gate":1}}
```

`melodic_modes` exposes `label`, `title`, `reference_note`, `source_file`,
`source_beats`, `suggested_bpm`, `phrase_units` and `bars_at_eighth_notes`.
The same modes work with `perform-update`, `loop-step` and live recording.
Loop exports contain rendered notes and instrument sounds, but do not bundle the
MIDI library. Copy `local/perform-midi` as well to use these Perform modes on a
second Studio installation.


## Clearing loop layers

Each loop card has a trash button. `loop-clear` uses the same operation:

```json
{"command":"loop-clear","slot":2}
```

Slots 1–4 clear one layer; omitting `slot` clears all four. Clear is available
while stopped, paused or playing. It releases only the affected loop's active
notes and empties its recorded notes/Perform data; the layer's Pistil sound,
other layers, drum beat, Live Perform and Play Along remain intact. Clearing is
blocked while a take is armed/recording. Clearing an empty layer does not discard
the previous undo history. Stop the looper, then use `loop-undo` to undo/redo the
latest edit. The UI disables clear for empty layers and during takes.

The looper checkbox is now **Start drums with loops**. It chooses whether the
selected drum beat starts with the next new looper run. It does not record drums
into a layer or toggle already-running drums, and is disabled while the looper
runs (including pause). Stop before changing it. Drum volume remains adjustable
live in the Mixer.
