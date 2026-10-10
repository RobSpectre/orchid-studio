> Current drum API: see [Studio drum machine](DRUM_STUDIO.md). Native macOS
> playback uses `drums.engine: "studio"`; `hydrogen` remains a legacy alias.
> Beats are editable documents, kit sounds can be mixed, and drum hits are
> scheduled on the same timeline as loop notes. The native host plays both.

# Orchid Studio control API

API v1 exposes Studio transport, mixer, six independent Pistil voices, Perform,
loops, editable drum beats, samples and MIDI clock. See the generated
[complete control map](CONTROL_MAP.md) for every command and UI equivalent, and
[Sounds and Perform map](SOUND_PERFORM_MAP.md) for descriptions. Individual synth/FX
parameters inside the vendor Pistil editor still use Computer Use.

## Run and connect

```sh
.venv/bin/orchid-studio serve --api-port 8765 --api-only \
  --sound-input Orchid --pistil-host
```

Open <http://127.0.0.1:8765/> for the control page. The same process owns the MIDI
routing, six native Pistil AUs and drum sampler. No separate DAW is required for
this macOS route. Preserve the existing licensed plugin and patches.

`--api-only` runs until API `quit` or a signal; stdin is not used. Without it,
JSON lines on stdin continue to work alongside HTTP; stdin EOF shuts down the
service. Use API-only mode for the skill or detached operation. Existing JSON-only
`serve` remains available when `--api-port` is omitted.

HTTP binds **127.0.0.1 only**, accepts same-origin browser requests or local API
clients, and rejects other Origins/Host values. There is no remote authentication
or cross-origin access. Do not expose the port to a network. POST bodies are JSON,
limited to 1 MiB. No new Python runtime dependencies are required.

- `GET /status`: current applied performance settings, routing, pending update
  count, configured defaults, requested drum state and latest event ID.
- `GET /capabilities`: command names, complete settings schema, enum choices,
  numeric bounds, defaults, drum actions and beat catalog.
- `GET /beats`: the 12 named arrangements, zero-based indexes and suggested BPMs.
- `POST /command`: the same JSON objects used by the CLI and JSON-line service.

```sh
.venv/bin/orchid-studio request '{"command":"status"}'
.venv/bin/orchid-studio request '{"command":"capabilities"}'
curl -s http://127.0.0.1:8765/command \
  -H 'Content-Type: application/json' \
  -d '{"command":"perform-update","settings":{"bpm":124,"mode":"harp"}}'
```

The CLI accepts `request -` to read a JSON object from stdin; `--port` overrides
8765. Python clients can call `orchid_studio.api_client.request(payload, port)`.
No MIDI or OSC port is opened by the request client. An optional `id` is echoed in
the reply. HTTP validation errors return 400 and `status:error`; CLI errors return
exit code 1. A failed request does not imply a stopped performance.

## Performance

`perform-configure` merges validated defaults for the next live start without
changing the running performance. `perform` validates a replacement before
stopping the current performance. It opens only the named physical input and
consumes only its specified raw Chord channel. `perform-update` changes any subset
of settings while running. Route changes require `perform` again.

```json
{"command":"perform-configure","settings":{"bpm":124,"mode":"strum","velocity_limit":72}}
{"command":"perform","input":"Orchid","chord_channel":3,"output_channel":1}
{"command":"perform-update","settings":{"mode":"strum2","spread_beats":0.4}}
{"command":"perform-update","settings":{"mode":"pattern","pattern":"shuffle","gate":0.6}}
{"command":"perform-update","settings":{"mode":"harp","harp_octaves":4,"step_beats":0.5}}
{"command":"perform-update","settings":{"mode":"slop","slop":0.7,"seed":12,"chord_window_ms":8}}
```

All 11 settings are listed by `capabilities.settings_schema`: `bpm`, `mode`,
`pattern`, `step_beats`, `gate`, `velocity_limit`, `spread_beats`, `harp_octaves`,
`slop`, `seed`, `chord_window_ms`. Their musical meaning and ranges are in
[LIVE_PERFORM.md](LIVE_PERFORM.md). These are original software implementations.

Live updates return `queued`. Poll `status` for applied values, or
`{"command":"events","after":123}` for `perform_updated`. Startup returns before
input setup completes; `perform_ready` establishes readiness and `playback_error`
reports failure. Events have increasing `event_id` values. The last 256 are kept;
`truncated:true` means a requested history predates that buffer. A service restart
resets history, defaults and requested drum state. Defaults are not saved presets.

## Follow the hardware Sound dial

The raw-chord route deliberately disables direct Orchid MIDI input in Pistil.
That also removes its usual Sound-dial reports. A separate, narrow forwarding
route now passes fresh Sound changes to the virtual software source:

```json
{"command":"sound-follow","input":"Orchid","enabled":true}
{"command":"sound-follow","enabled":false}
```

Use `--sound-input Orchid` at startup to enable it automatically, or the control
page's **Orchid input & routing → Follow Sound dial** button. **Keep Pistil sound**
disables it. `status.sound_follow` reports readiness, the exact input and last
forwarded one-based preset. `sound_follow_ready`, `sound_forwarded` and
`sound_follow_error` events distinguish startup, transmission and failure.

Only channel-1 CC102 (slots 1–100) and the observed 142-byte Telepathic 0x34 Sound
state report are forwarded. Notes, bass, pedals, clock, Perform reports, unrelated
SysEx and maintenance messages are excluded. This opens a MIDI input only and
sends only to Studio Playback; nothing is sent back into Orchid. Sound changes
follow even while note playback is stopped. `quit` closes the follower.

This intentionally changes Pistil's current patch when the physical dial moves.
It neither saves presets nor restores prior edits. It starts with the next dial
movement; there is no stale-state replay or initial hardware query. Pistil's desync
switch must be off to accept the reports. The route is separate from the software
Perform mode/BPM, which remains controlled by Studio.

## Record physical key presses (key monitor)

A read-only listener reports what the Orchid keyboard actually sent, for clients
that check physical playing (for example a robot arm pressing keys):

```json
{"command":"key-monitor","input":"Orchid","chord_channel":3,"enabled":true}
{"command":"key-events","after":0}
{"command":"key-monitor","enabled":false}
```

`--sound-input Orchid` enables it at startup with the `--chord-channel` value.
`status.key_monitor` reports readiness, input, channel, the press count and the last
voicing-dial value. `key-events` returns events after an `id` cursor, plus
`last_key_event_id`, `truncated` (only the last 512 are kept) and `now`:

- `press`: `t`, `root`, `name` (C…B), `octave`, `notes`, `intervals`, `velocity`, `beat`.
- `release`: `t`, `press_t`, `root`, `name`, `held_s` (when the press's last note stopped).
- `voicing`: `t`, `value` (dial position), `delta` (clicks since the previous report).

Observed on this Orchid: a key alone sends one note on the raw Chord channel; a held
chord button adds its chord at the same instant with one velocity, and sends nothing
itself. Note-ons within 8 ms are one press; its lowest note is the key. Velocity
follows the strike (8–104 seen). The voicing dial sends channel-1 CC115 with an
absolute position and can move the octave a key sounds in, so compare `name`, not
note numbers. Channel 1's mirrored notes and Orchid's repeated note-offs are ignored.

`t` is `time.monotonic()` at arrival, which other local processes on macOS and Linux
read from the same clock. `beat` is Studio's timeline position at that instant, or
null while the timeline is stopped. This opens a MIDI input only and sends nothing
anywhere; it does not depend on any note route or Play Along.

`{"command":"fx","slot":5,"delay":{"mix":25,"beats":0.5,"feedback":40},"reverb":{"mix":30,"room":"cathedral"}}` sets
one voice's effects in the native audio host (slot 5, the Live Perform voice, unless given). Each voice runs
Pistil → delay → reverb. Both are off (mix 0, bypassed) until set, so nothing changes until asked. Updates are partial.
`delay.time` is in seconds, or `delay.beats` at the current tempo. `reverb.room` is small, medium, large, chamber, hall,
large-hall, plate or cathedral. `status.fx` reports every voice. Needs independent Pistil sounds (`pistil-enable`), and
rebuild the host once (`orchid-studio build-host`) so it has the effects.

`{"command":"loop-compose","slot":2,"chords":[{"beat":0,"duration":8,"notes":[48,52,55],"velocity":70}]}` replaces
one loop layer with a whole composition (chords at beats, 1–512, each 1–16 MIDI pitches). While the loops play it
takes over on the **next loop boundary** (`composed.applies_at_beat`; event `loop_composed`), so the pass in progress
plays on. orchid-robot uses this to loop what its arms just played, each chord moved onto its written beat. Stopped, it applies at once.
Optional `settings` are the layer's Perform settings, as for `loop-step`.

`{"command":"clock"}` reads the beat timeline on its own, cheaply: `bpm`, `beat`,
`running`, `paused`, tempo-transition fields and `t`, the `time.monotonic()` the
reading is for. While it runs, the beat at time `x` is `beat + (x - t) * bpm / 60`
(outside a tempo transition). The virtual MIDI clock output follows this timeline, so
a local client can land physical playing on Studio's beat without opening MIDI.

## Named Hydrogen beats

Generate the bank once from an installed TR808EmulationKit; the generator refuses to
overwrite existing songs and does not copy samples:

```sh
.venv/bin/orchid-studio drums-song local/electronic-12x12.h2song --bank electronic --bpm 124 \
  --kit-directory local/hydrogen-runtime/hydrogen-1.2.7/data/drumkits/TR808EmulationKit
```

The bank uses the installed **TR808EmulationKit**, whose metadata describes its
sounds as synthesized from basic waveforms. It contains four drum-and-bass grooves
(170–176 BPM), four house grooves (122–128 BPM), and four trance grooves (132–140
BPM). No acoustic drum samples are referenced.

Every arrangement is **12 bars in 4/4 = 48 quarter-note beats**, with a sparse
opening, core groove, variation, lift/fill, drop and turnaround. All are original
pattern data; the installed samples retain their original licensing.

| Beat ID | Name | Genre | Suggested BPM |
| --- | --- | --- | ---: |
| `liquid-circuit` | Liquid Circuit | drum-and-bass | 172 |
| `neon-breaks` | Neon Breaks | drum-and-bass | 174 |
| `subway-steps` | Subway Steps | drum-and-bass | 170 |
| `night-runner` | Night Runner | drum-and-bass | 176 |
| `velvet-floor` | Velvet Floor | house | 122 |
| `glass-house` | Glass House | house | 124 |
| `after-hours` | After Hours | house | 126 |
| `warehouse-glow` | Warehouse Glow | house | 128 |
| `aurora-drive` | Aurora Drive | trance | 132 |
| `prism-lift` | Prism Lift | trance | 136 |
| `orbital-pulse` | Orbital Pulse | trance | 138 |
| `daybreak-rush` | Daybreak Rush | trance | 140 |

```json
{"command":"beats-list"}
{"command":"beats-load"}
{"command":"beats-select","beat":"glass-house"}
{"command":"beats-play","beat":"glass-house","bpm":124,"volume":0.3}
{"command":"stop"}
{"command":"perform","input":"Orchid","chord_channel":3,"settings":{"bpm":124,"mode":"strum"},"drums":{"engine":"hydrogen","beat":"glass-house","volume":0.3}}
{"command":"beats-select","beat":"prism-lift"}
```

`beats-load` uses the configured path or an explicit `path`, checks the ordered
catalog and 12-bar sizes, and requires playback stopped. It sends OPEN_SONG;
verify Hydrogen's loaded song before playback. A sent load is not an acknowledgment.
Selecting a name requires a bank-load request in the current service. If you
change songs directly in Hydrogen, reload the bank before using named selectors.

`beats-select` sends a pattern selection without changing tempo. Hydrogen's
selected-only-next-pattern action can wait until the full 12-bar boundary while
playing. For immediate selection, stop and restart the desired beat. `beats-play`
is drums-only; for coordinated live playback use `perform` with `drums.beat`.
Named beats also work in the API `play` request's `session.drums` object. Standalone
`play FILE` still uses numeric `drums.pattern` and requires the correct song loaded.
Never combine `drums.beat` and `drums.pattern`.

The Hydrogen 1.2.7 editor's pattern-size spinner caps its display at four bars,
though its song loader and audio engine retain/render these longer patterns. The
bank stores 2304 ticks (48 PPQN × 48 beats) per pattern, verified by full-bank WAV
export. Do not resize these patterns using that spinner; regenerate through Studio
if their length is changed. The Studio catalog displays the full 12 bars.

## Transport, mixer and evidence

`demo` and `play` retain the version-1 clip API, with optional `bpm`, `transpose`
and `repeats`. `drums` retains the existing mixer, pattern, kit and transport
commands described in [HYDROGEN.md](HYDROGEN.md). `stop` stops managed MIDI and
Hydrogen; `panic` also releases notes/pedals on all software channels and mutes
Hydrogen tails. `quit` cleans up and closes API-only service operation.

Hydrogen state fields are **requested** state, not a live engine mirror.
`sent`/`confirmed:false` establishes transmission only. `drums` action `feedback`
returns observed OSC messages, not a per-request acknowledgment. Audio requires
listener confirmation. A direct Hydrogen UI change can invalidate requested state.

Studio and Hydrogen currently use separate clocks with common BPM and coordinated
start/stop. Live BPM changes propagate to Hydrogen when `perform` was started with
`drums`; phase-locked synchronization remains unimplemented. Pistil patch editing,
live overdub and independent multiple synth instances remain separate work.

## Loop sequencer

Four layers share a Studio-owned clock. With `pistil-enable`, each owns a separate
Pistil AU patch; the standalone fallback shares one patch. Record the raw
chord channel (confirmed as 3 on this Orchid), never the performed and chord
streams together. Incoming hardware clock is ignored. Notes are snapped before
software Perform is rendered; arpeggio/strum spacing is retained. Default grid:
**0.5 beat (eighth notes)**. Chord arrivals within 0.12 beat group together, short
taps last at least one grid step, and held notes close at the loop boundary.

```json
{"command":"loop-configure","settings":{"bars":4,"grid":0.5,"count_in":4}}
{"command":"loop-start","input":"Orchid","chord_channel":3,"output_channel":1,"slot":1,"settings":{"bpm":124,"mode":"arp"},"drums":{"engine":"hydrogen","beat":"glass-house","volume":0.3}}
{"command":"loop-record","slot":2,"settings":{"mode":"strum"}}
{"command":"loop-cancel"}
{"command":"loop-mute","slot":1,"muted":true}
{"command":"stop"}
{"command":"loop-undo"}
{"command":"loop-export"}
```

- `loop-start` stops existing managed performance, opens the exact input, counts
  in, then loops until stopped. Omit `slot` for playback without a take. Count-in
  is visual; drums start on the first musical downbeat. The page shows a moving
  beat marker and recording state. HTTP status also exposes `looper`.
- `loop-record` arms the selected slot for the next whole loop boundary. It uses
  the running BPM and supplied Perform settings. Recording replaces that slot;
  its previous clip is silenced during the take while other layers continue.
  An empty or cancelled take leaves the previous clip intact. The finished take
  automatically plays, with one undo available. Stop cancels an unfinished take.
- Loop lengths: 1–16 bars of 4/4; grid: 0 (free), .25, .5 or 1 beat; count-in:
  0–16 beats. Change these while stopped. Clear all layers before resizing.
- `loop-clear` clears `slot` 1–4, or all layers if omitted. `loop-undo` toggles the
  previous take/edit. Clear, undo, import and step entry require stopped loops.
  Muting is immediate; unmuting resumes at upcoming note attacks.
- Stop/panic release all owned notes and sustain. Shared pitches are held until
  the last owning layer releases them. With independent sounds enabled, each layer routes to its own AU and the Sound
  dial affects only the selected layer. Standalone fallback shares one patch. Recording stores
  note presses/releases, not pedal, preset or controller automation.
- Tempo and monitor Perform settings are chosen on loop start. Completed layers
  retain their recorded Perform pattern, scaled to the current playback BPM.
  Use `tempo` to change the shared BPM during playback without resetting phase. Native drums use the same beat timeline and audio engine as the loop layers.

For robotic/API entry without physical timing, insert explicit chords while
stopped. `beat` is zero-based; MIDI 60 is middle C. `duration` is in beats.
Successive steps within a layer use the same Perform settings (tempo may differ).

```json
{"command":"loop-step","slot":1,"beat":0,"duration":4,"notes":[60,64,67],"velocity":64,"settings":{"mode":"arp","bpm":124}}
{"command":"loop-step","slot":1,"beat":4,"duration":4,"notes":[57,60,64],"settings":{"mode":"arp","bpm":124}}
{"command":"loop-export"}
```

The export response's `document` is an `orchid-loops` version 1 JSON document.
Save it and restore with `{"command":"loop-import","document":{...}}`. The
web page provides Save/Open. Import validates all four layers before replacing
anything and regenerates performed notes from chord data. Clips survive Stop
in memory, but **save before quitting/restarting the service**. No samples or plugin binaries are embedded. When the independent AU host is
enabled, the document also includes all five Pistil patch states and the six-channel mixer. See
[Independent Pistil sounds](PISTIL_HOST.md) for startup, `layer-select`,
`layer-preset`, `layer-editor` and save/restore details.

### MIDI clock output and audio recovery

`clock-configure` takes boolean `enabled` and optional `offset_ms` (0–500,
default 40), while stopped. It publishes only the virtual `Orchid Studio Clock`
source: 24 PPQN/F8, Start/FA after count-in, Stop/FC on stop/completion/failure.
`status.midi_clock` exposes state, pulse count and errors. Enable is per service
launch; no physical MIDI output is selected. See [clock and recovery](DRUM_STUDIO.md).

`pistil-enable` now restarts an exited audio child and restores the last local
sound checkpoint. Playback also performs this recovery while stopped. Healthy
hosts are reused. Loop export remains available with checkpoint sounds if audio
has exited; it cannot recover later unsaved AU edits.


## Global tempo, mixer and pause

The interface uses one shared musical timeline for software Perform, loops,
clips, native drum samples and the outgoing MIDI clock. Global BPM is 30–300.
Changing tempo preserves the current beat, including during count-in or pause.
`status.tempo` reports `bpm`, `beat`, `paused` and `running`.

```json
{"command":"tempo","bpm":110}
{"command":"mixer-set","channel":"layer-1","volume":0.7,"pan":-0.3}
{"command":"mixer-set","channel":"drums","volume":0.3,"pan":0}
{"command":"mixer-set","channel":"live","volume":0.8,"pan":0.2}
{"command":"pause"}
{"command":"resume"}
```

Mixer channels are `layer-1` through `layer-4`, `drums`, `live`, and `play-along`.
Volume is linear gain 0–1.5; pan is -1 (left) to +1 (right). Omitted fields retain
their values. These controls require the native host and work while playing.

`mixer-get` returns current `mixer` values and `mixer_automation` (active channels,
start/target values, duration, curve, applied progress and last error). Both are
also in `status`; `capabilities.mixer_schema` exposes channels, ranges and timing.
`mixer-set` retains its single-channel syntax and also accepts a `channels` map:

```json
{"command":"mixer-set","channels":{"layer-1":{"volume":0},"layer-2":{"volume":0.7}},"transition_seconds":8,"curve":"smoothstep"}
{"command":"mixer-cancel","channels":["layer-1","layer-2"]}
```

Supply either `channel` with volume/pan, or `channels`, never both. The complete
request is validated before any channel changes. Omitted volume/pan fields retain
their current values. `transition_seconds` is 0–120 (default 0, immediate), and
`curve` is `linear` (default) or `smoothstep`. Fades return `queued`, run without
client polling, and share one start time across the group. Updates are attempted
at 50 Hz in monotonic seconds, including while stopped or paused; these are
control-rate changes, not sample-accurate or beat-quantized automation. Sequential
host writes are not an atomic audio transaction; a host failure may leave some
channels updated. Failure cancels active fades and reports `mixer_error` plus the
last error in `mixer_automation`. Completion emits `mixer_transition_completed`.

A new command or UI fader move replaces the fade on each affected channel, starting
from the latest applied values; other channel fades continue. `mixer-cancel`
omits `channels` to cancel all and leaves the current balance in place. Stop,
panic, session import, host recovery and shutdown cancel fades; pause/resume does
not. Session exports store the applied mix, not unfinished fades. Save the
`mixer-get.mixer` object and pass it back as `mixer-set.channels` to recall a mix.

Live uses a fifth independent Pistil AU. `layer-select`, `layer-editor` and
`layer-preset` accept slot 5 for Live. While recording, monitoring uses the take's
layer; otherwise it uses Live. Select Live in the mixer to direct the Orchid
Sound dial to it. Loop sound-selection buttons still target their own layer.

Pause freezes the timeline and releases voices; resume revoices sustained loop
notes at that beat. Physical live chords should be pressed again after pausing.
Pause is rejected during an armed or recording take. MIDI clock emits Stop on
pause and Continue on resume; a fresh launch emits Start. No SPP or idle clock.
Stop resets the transport and discards unfinished takes as before.

Exports preserve global BPM, five AU states and mixer values. Older four-AU
sessions still import, seeding Live from their last patch. `status.looper.layers`
now includes rendered `notes` for the note/time graph and each layer preview.


## Drum loop length and interface shortcuts

`{"command":"drums-length","bars":8}` sets an even playback length from 2 to
64 bars. `bars:null` uses each beat's original arrangement. Shortening uses its
opening bars; lengthening repeats the source to fill the requested length.
The library document stays unchanged. During playback a change queues for the
next bar, including a change requested while paused. `status.drums.sequencer`
includes `loop_bars` (requested override), `bars` (active length), `pending_bars`,
`anchor` and the active `document` for the drum hit/time display. `beat-get`
returns both the saved `document` and an arranged `playback_document`. Loop export
stores the override in `drums.loop_bars`. Editable beat documents now allow up to
64 bars; the editor offers even lengths and repeats content when growing.

The BPM rotary dial supports vertical dragging, Shift-drag for fine control,
arrows for 1 BPM and Page Up/Down for 10 BPM; the numeric readout remains editable.
The Pistil selector applies Sound 001–100 to its explicit loop/Live destination.
Opening a sound editor or selecting the hardware dial destination is allowed
during playback, except while a take has another sound destination locked.

Play buttons become Pause for the active mode and Resume when paused. Pause is
global so coordinated parts remain together. Space pauses/resumes the current
transport or starts the loaded loop session after Stop. It works from selectors,
sliders, dials and buttons, while preserving text entry and ignoring modified
keys and repeated keydown events. Recording must finish or
be canceled before pausing. The browser must have keyboard focus.


## Smooth tempo changes

While running, tempo changes default to a two-second cubic Bézier ease-in/out
with controls (1/3, 0) and (2/3, 1). Studio integrates this curve to obtain beat
position, so notes, drums and published MIDI clock follow one changing timeline.
The native AU tempo context follows the current rate at up to 20 Hz. A new target
starts from the instantaneous BPM; repeated requests for the same target do not
restart the transition. Pause freezes the curve as well as the beat. Stop settles
to the requested tempo, and tempo changes while stopped apply immediately.

`tempo` optionally accepts `transition_seconds` (0–10); 0 applies immediately.
`status.tempo.bpm` is the current rate, `target_bpm` is the requested rate, and
`transitioning`, `transition_progress`, `transition_seconds` and `curve` describe
the transition. Performance settings retain the requested target BPM. The UI
keeps the requested value in its numeric field, shows the current→target rate
underneath, and moves the dial needle with the current rate. UI bounds are 60–200.

## Single-key melodic Perform modes

`mode` also accepts `bloom`, `orbit`, `drift`, `spark` and `tide`. The capabilities
response's `melodic_modes` includes descriptions, harmonic progressions and phrase
lengths. These use explicit major/minor variants, extended harmony, chromatic
approaches and voice leading; see [Live Perform](LIVE_PERFORM.md#five-single-key-melody-modes).
Hold one note or chord to repeat, release to stop (or use sustain). Note Division
scales their 32-unit phrases, and normal gate/velocity settings apply. Existing
`perform-configure`, `perform-update`, recording and `loop-step` support them.

The Hooks bank adds `sunline`, `sidekick`, `electric`, `bluehour` and `anthem`:
five original recurring motifs with contrasting answers. Electric and Anthem
use minor for a single held key; the other hooks use major. A held major/minor
third overrides that default. `capabilities.mode_banks` groups all 18 modes into
`classic`, `melodies` and `hooks`; each `melodic_modes` entry exposes `bank` and
`default_quality`. Selecting a UI bank selects its first mode; API callers set
`settings.mode` directly. See [original hooks](LIVE_PERFORM.md#five-original-hooks).


User-supplied MIDI adds an optional `songs` bank. `song-africa`,
`song-buddy-holly`, `song-kissed-a-girl`, `song-porgy` and `song-prayer` are installed
on this machine. C4 preserves original pitches; other held keys transpose. Use
`step_beats:0.5, gate:1` for source timings. Phrase lengths vary; inspect metadata
in `melodic_modes` and optional-library failures in `song_import_errors`. File
tempo never overrides global BPM. See [MIDI song phrases](LIVE_PERFORM.md#user-supplied-midi-song-phrases).


## Dedicated Play Along voice

The macOS host now has six independent Pistil AUs: loops 1–4, Live Perform 5,
and direct Play Along 6. The seventh mixer strip (including drums) gives Play
Along its own volume, pan and enable toggle. The sound selector also offers
Play Along. The new AU initially inherits the saved Live sound when restoring
older four/five-voice sessions; six-voice exports use `pistil-au-v3`.

Play Along listens only to the configured raw Chord channel (confirmed 3 on this
Orchid). It sends unpatterned notes and sustain/sostenuto to slot 6. It excludes
the performed/bass streams, clock, program changes and SysEx. Whenever enabled,
it plays independently of transport, including immediately after launch and while
stopped or paused. Pause/resume leaves held Play Along notes alone. Stop/panic
releases its notes and pedals without disabling the route; fresh keys still play.
Disable its toggle or turn its mixer down when you want only the generated
Perform voice. It is not recorded
into loop takes. Hardware Perform is bypassed by consuming raw Chord notes.

Fresh Sound-dial reports update Play Along as well as the explicitly selected
sound destination; they never broadcast to every loop. Select slot 6 to make
hardware sound changes affect Play Along alone. The existing selected-layer
behavior still applies if you deliberately select a loop. Current hardware sound
cannot be queried reliably: before the first fresh Sound report, the new voice
uses the restored Live patch. No firmware commands or archived reports are sent.

```json
{"command":"play-along","enabled":true,"input":"Orchid","chord_channel":3,"velocity_limit":80}
{"command":"mixer-set","channel":"play-along","volume":0.7,"pan":0}
{"command":"layer-select","slot":6}
```

Inspect `status.play_along` for route, enable state and errors. The native service
launch with `--sound-input Orchid --pistil-host` enables this confirmed channel-3
route by default; explicit API configuration can change it. Enable state is per
service launch; six sounds and all mixer values are saved in loop exports.


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


## Discover every control and sound

`command-help` returns descriptions, parameters and constraints for every command,
plus the UI control map and drum draft actions. Filter with `name` for one command.
`capabilities` also includes `command_reference`, `ui_map` and `beat_editor`.

```json
{"command":"command-help","name":"layer-preset"}
{"command":"sounds-list"}
{"command":"perform-options"}
{"command":"layer-preset","slot":2,"preset":49}
```

`sounds-list.sounds` maps all 100 Pistil slots, including factory names and
configuration-derived descriptions. User slots and edited patches vary.
`perform-options.mode_map` describes every installed Perform mode;
`pattern_descriptions` explains its eight rhythm choices.

Each loop card has a sound dropdown using `layer-preset` with that card's slot.
Changing a sound while stopped, playing or paused preserves the recorded notes,
other voices, and selected recording destination. Session export captures the new
patch. Slots 1–4 are loop layers, 5 is Live Perform, and 6 is Play Along.

`beat-edit` makes unsaved drum drafts available programmatically. Pass either a
saved `beat` ID or a `document`, and an action from `capabilities.beat_editor`.
The response includes `document` and `undo_document`. Save explicitly with
`beat-save`. Browser drafts and their undo stacks remain local to each tab; API
clients maintain their own history. See [CONTROL_MAP.md](CONTROL_MAP.md) for
clone/new, steps, accents, bars, length, swing and lane editing examples.


## Start on key

```json
{"command":"key-start","enabled":true,"input":"Orchid","chord_channel":3,"drums":{"engine":"studio","beat":"subway-steps","volume":0.34}}
{"command":"key-start","enabled":false}
```

When stopped, this arms the loaded loop session silently at beat zero, bypassing
the recording count-in. A fresh positive-velocity Note On on the specified raw
Chord channel starts loops, their drums and outgoing MIDI clock; the same attack
is delivered once to Live Perform. When paused it resumes at the existing cursor.
While playing, enabling the switch makes future pauses wakeable; notes do not
restart a running session. Held-note repeats, other channels, note-offs and CCs
never trigger playback. Stop/panic disarm; re-enable to wait again. Active takes
reject changes. Disabling the switch leaves the current transport state intact.

The checkbox is in the loop sequencer footer. Status exposes
`looper.start_on_key` and `looper.waiting_for_key`; events include `loop_key_started`.
It controls the loop/Live Perform route, not standalone MIDI file/Perform playback.
No key presses are sent back to Orchid. `loop-start` also accepts the boolean
`wait_for_key` flag directly (without a recording slot).


## Beat vibes / Many Rooms bank

The 12 additional Many Rooms arrangements are selectable with `beats-select`,
`beats-play` or a transport start's `drums.beat`. See [BEAT_VIBES.md](BEAT_VIBES.md)
for all IDs, suggested BPMs and musical descriptions.

`beats-list` and `capabilities.beats` include `bank`, `vibe`, `tags`, `energy`
(low/medium/high), `density` (sparse/medium/busy), `best_for` and `arrangement`.
`beat-get.document` includes the same metadata plus lanes/hits. Older/custom beats
may return null energy/density and empty tags. These describe intended character,
not audio measurements or listener approval. `beat-save` preserves these fields.

```json
{"command":"beats-select","beat":"black-velvet"}
{"command":"tempo","bpm":92}
```

Selecting does not change global tempo. Use `tempo` only when desired; every
sequencer then follows it. New source beats are 12 bars each and support the
existing even 2–64-bar runtime override. No existing beat IDs are replaced.


### Studio-wide Space shortcut

While the Studio page has keyboard focus, Space toggles the shared transport:
loops, drum playback, Live Perform and outgoing clock pause/resume together.
Enabled Play Along remains available independently of transport. From stopped, it starts the loaded loop session with its configured
Start drums with loops accompaniment and live input; it does not replay whichever
section button was last used. Text-entry fields retain normal spaces. Selectors,
checkboxes, mixer sliders, number inputs, dials and buttons all use global Space.
Held-key repeats are suppressed and rapid complete presses are serialized against
fresh API status. Active takes still require finishing/canceling before pause.
This is an in-Studio shortcut, not an OS-wide hotkey when another app has focus.


### Key-response timing and count-in

Existing loop playback now starts immediately; `count_in` applies only when
`loop-start` arms a recording `slot`. Key-start also starts at beat zero.
While paused, drum stop/voice cleanup happens once on entry rather than on every
input poll. Raw-chord input is polled every 2 ms while waiting.

`status.looper.key_start_timing` reports `midi_to_loop_send_ms` and
`midi_to_live_send_ms`, with corresponding `key_loop_dispatched` and
`key_live_dispatched` events. These measure from receiving the waking MIDI attack
to dispatching the first loop/live note. They exclude hardware scanning, the
40 ms audio scheduling allowance, synth envelope attack and output buffering;
they are not a measurement of physical-key-to-heard-sound latency. Null values
mean no applicable note has yet been dispatched. A paused cursor between loop
notes can legitimately wait until the next note for the loop metric.


### Orchid connection indicator

`status.orchid_connection` reports actual MIDI input port presence separately from
transport and Sound-follow state: `input`, `connected` (true/false/null), `state`
(connected/disconnected/unknown), `stale` and `error`. Inventory is read-only,
polled about once per second off the transport thread. Results older than three
seconds become unknown. It does not prove key events are arriving or audio is audible.
The top bar shows green **Orchid connected**, red **Orchid disconnected**, or amber
while checking/unavailable. Losing the Studio API clears the connected indication.
