> Latest drum architecture and validation are in the **Native drums and editable beats — 2026-10-07** section at the end; earlier Hydrogen clock findings are historical.

# Initial validation — 2026-10-06

## Independent loop sounds — 2026-10-07

- Built a native macOS Swift/AppKit/AVAudioEngine host for four instances of the
  installed `aumu/Pitl/Tptp` Pistil AU. No additional runtime package, DAW or
  proprietary plugin copy was added. Standalone remains untouched as fallback.
- The plugin editor opened and rendered Pistil's ORCHID EP panel in the initial
  host. A per-instance note test produced signal only on its addressed output
  meter. This is observed signal, not listener confirmation of the new host.
- Settled AU state comparisons found only the explicitly changed instance changed;
  startup initially exposed deferred preset initialization, so host readiness now
  waits for it. Captures also wait for queued Sound changes before serializing.
  Immediate save-after-preset and save-after-restore checks pass.
- All four AU states match semantically after changing a patch and restoring it.
  A full service AND native-host restart reproduced all four states and retained
  every loop note. Evidence is the user-local
  `local/current-loops-with-sounds.json`; no opaque user patches are tracked.
- The existing three layers were preserved. Layer 1 now uses Sound 001, Layer 2
  Sound 049, Layer 3 retains Sound 051; empty Layer 4 is selected for the next
  sound. The standalone application's edited state was not imported or changed.
- Added selected-layer Sound forwarding, paired-report routing, per-engine voice
  ownership, patch export/import, plugin editor controls and startup
  `--pistil-host`. All 74 tests pass. Invalid note/patch imports leave current
  layers intact. Updated installed control skill passes its validator.
- Browser verified the selected-layer selector, separate sound labels and host
  status. Final native editor inspection, physical Sound-dial isolation and
  listener-confirmed audition remain pending because the Mac is locked. The
  user has been asked to unlock it; no claim of newly heard audio is made.

## Forgiving loop sequencer — 2026-10-07

- Added four software MIDI loop layers with a default eighth-note grid, grouped
  chord attacks, minimum one-grid-step short notes, automatic boundary releases,
  count-in, next-cycle record arming, mute, one-level undo/redo and JSON save/load.
  Quantization precedes the existing Perform renderer. Shared pitch ownership
  prevents one layer's note-off or monitor cleanup cutting another layer.
- Added the loop page controls and explicit chord step entry/API for robotic
  operation without timed key presses. Installed control skill updated and its
  validator passed using the existing temporary PyYAML environment.
- All 69 tests passed, including all eight Perform renderers, snapped short taps,
  chord grouping across a grid midpoint, boundary handling, shared note ownership,
  deterministic count-in/record/replay, wrong-channel exclusion and import/undo.
- Real CoreMIDI verification used separate software-only source/output ports in
  an isolated Controller. Deliberately uneven, short channel-3 chord input became
  three notes at beat 0 with duration 0.5 beat; nine output attacks confirmed
  monitoring and two subsequent loop passes. Channel-1 test pitch was excluded.
  Evidence: `local/looper-live-verification.json`. The long-running service did
  not enumerate the newly created temporary test port; the fresh test controller
  did. Its existing physical Orchid input worked in the deployed service.
- Browser verified step insertion and layer mute/unmute. Preserved Pistil
  **050 — ARCTIC**, reconnecting only Studio Playback after service restart.
  Two demo layers at 124 BPM plus Hydrogen Neon Breaks played for two cycles and
  stopped. User confirmed: “Yes—layers repeat and stop cleanly.”
- Subsequently observed a completed physical-input take in Layer 3: three chord
  notes rendered to 28 arpeggiated notes, without a reported runtime error.
  Saved all current layers to `local/current-loops.json`; portable demo remains
  `examples/forgiving-loops.json`. Screenshot: `local/loop-sequencer.png`.
- Current limits: one shared Pistil patch, note-only recording (no pedal/patch
  automation), visual count-in, fixed running tempo (stop/restart to change), and
  Hydrogen's independent clock. Save loops before service exit; Stop retains them.

## Restrained electronic accents — 2026-10-07

- In response to grating, dissonant accent feedback, removed cowbell, clave,
  conga, tom, shaker and crash/cymbal hits from all 12 arrangements. Core kicks,
  snares, claps and hats remain. Replaced fills with two quiet snare taps on the
  sixteenth grid; trance variations now use hat spacing instead of tuned accents.
- All 61 tests passed, including the allowed voice palette, restrained fills,
  distinct arrangements, 12-bar length and existing API/routing checks.
- Regenerated `local/electronic-12x12.h2song` and preserved the prior song as
  `local/electronic-before-accent-cleanup-1791395879932326000.h2song`.
  Hydrogen loaded the revised bank; Computer Use verified Aurora Drive selected,
  124 BPM, TR808EmulationKit and stopped transport. Preserved master volume 0.3.
- Full-bank Hydrogen export `local/electronic-restrained-validation.wav` lasts
  279.421 seconds, including tails. All twelve final bars contain audio; peaks
  stay below 0.248 full scale. Measurements are in
  `local/electronic-restrained-audio-validation.json`. This checks rendered output;
  the user has not yet reviewed the revised sounds by ear.

## Sound-dial routing fix — 2026-10-07

- Disabling direct Orchid input in Pistil prevented duplicate notes but also
  removed Sound-dial synchronization. A fresh passive input-only capture of the
  user's move to Sound 49 observed channel-1 CC102 value 48 followed by a 142-byte
  vendor 0x34 Sound-state report. Capture:
  `local/sound-dial-1791394835637585000.json`.
- Added an explicit `sound-follow` route, optional `--sound-input` startup flag,
  status/events and UI controls. It forwards only these validated fresh Sound
  report shapes to Studio Playback, never to hardware. It excludes notes, bass,
  pedals, clock, other controllers and unrelated SysEx. No archived packets were
  replayed. The follower continues while musical playback is stopped.
- After enabling the follower and reconnecting Pistil's Studio input, the user
  moved from 49 to 50 and back to 49. API events observed both preset and sound-state
  reports for each. Computer Use verified Pistil displayed **049 — FM BONGO**.
  This intentionally replaced the former edited sound in response to the user's
  requested physical Sound selection; no preset was saved or overwritten.
- All 60 tests passed, including Sound report filtering, input-only forwarding,
  suppression of notes/clock/maintenance-shaped packets and input cleanup.

## Local API, control skill and electronic bank — 2026-10-07

- All 11 software Perform settings now have API discovery (types, ranges, enums,
  defaults), configurable defaults, queued live updates and applied-state/event
  observation. HTTP and JSON lines share one transport. A CLI/Python API client
  controls the existing service without opening competing MIDI/OSC endpoints.
- Added the local control page at `http://127.0.0.1:8765/`; browser interaction
  successfully configured Strum and BPM through the API. The page lists all
  settings and the 12 named electronic arrangements. Origin/Host checks reject
  unrelated browser sites; the API binds only loopback.
- 58 tests passed, including a real loopback HTTP integration test, live update
  application with a mocked MIDI input, catalog/beat selection, error handling,
  event cursors, MIDI-output suppression and 12-bar arrangement variation.
- Installed `orchid-studio-control` in `~/.codex/skills`, with source maintained
  under `skills/`. The skill creator's validator passed using an isolated temporary
  PyYAML installation; application runtime dependencies were not expanded.
- Replaced the initial lo-fi acoustic kit direction at the user's request. The
  final `local/electronic-12x12.h2song` contains four D&B, four house and four trance
  arrangements referencing installed TR808EmulationKit synthesized sounds. Each
  stores 2304 ticks (48 PPQN × 48 quarter notes = 12 bars in 4/4); sample files are
  not copied into the repository. Instrument MIDI output is disabled.
- Hydrogen GUI confirmed the loaded electronic song and TR808EmulationKit. API
  playback changed the selected pattern and BPM; observed Prism Lift at 136 BPM.
  The GUI length spinner caps at four bars, while its loader/audio engine retains
  longer patterns. Do not resize these through that spinner.
- Exported all 12 complete arrangements through native Hydrogen h2cli at 124 BPM.
  `local/electronic-validation.wav` is 279.421 seconds: 278.710 seconds of scored
  music plus tails. Every arrangement, including its final bar, contains audio;
  measured peaks 0.225–0.280 full scale. Evidence:
  `local/electronic-audio-validation.json`. Export logged GUI-event-queue overflow
  notices but completed; this is not a sample-perfect timing comparison.
- Live audition played Liquid Circuit at 172 BPM, Glass House at 124 BPM and Prism
  Lift at 136 BPM, then sent stop. The user first reported silence and later
  confirmed “kk - was able to hear that.” That establishes audible live drums,
  not a separate listening review of all twelve complete arrangements.
- Preserved Pistil `* ORCHID EP`; re-enabled only Studio Playback after the API
  service restart. MacBook Pro Speakers remained at 44.1 kHz / 512 samples.
- Hydrogen and Studio still use independent clocks. Named beat selection preserves
  tempo and may wait until a 12-bar pattern boundary. Shared phase lock, native
  Orchid parameter control and Pistil synth parameter automation are not added.

## Expanded software Perform — 2026-10-07

- User confirmed the live software Arp worked after lowering Orchid's physical
  volume: “Yup - that works.” Pistil receives only `Orchid Studio Playback`.
- Actual MIDI settings: Performed 1, Bass 2, Chord 3. Fresh passive capture
  `local/raw-chord-check-1791391324788517000.json` observed simultaneous block
  notes on channel 3. This supersedes the pending routing notes below.
- Added Off, Strum, Strum 2, Slop, Harp and eight original software Pattern rhythms,
  retaining Arp/Arp 2. Factory pattern equivalence is unverified.
- 50 tests passed after expansion. New coverage includes cross-poll chord grouping,
  polyphonic release, one-shot sweeps, tempo changes during a sweep, octave tails,
  seeded Slop, rhythm independence from chord size for every bank entry, mode
  change cancellation, scheduler stalls and cleanup following a failed note send.
- Restarted the service with the expanded engine; reselected only `Orchid Studio
  Playback` in Pistil. Preserved `* ORCHID EP`, MacBook Pro Speakers, 44.1 kHz and
  512-sample buffer. No direct Orchid or Hydrogen MIDI inputs were enabled.
- Generated a reproducible synthetic-chord tour with `scripts/make-perform-tour.py`
  into ignored `local/perform-tour.json`. Played all eight modes and all eight
  bank entries in four-beat sections at 96 BPM, velocity 64. The user initially
  reported silence, then confirmed “I can hear the demo now.” The remaining Harp
  and rhythm sections resumed after the pause. Service reported each section
  complete and final `playing: false`; clean audible stopping and recognition of
  each individual mode were not separately listener-confirmed.
- Restored live channel-3 input in Strum mode at 96 BPM, spread 0.25 beats, velocity
  cap 72. These results establish audible demo output, not exact factory matching
  or a live hardware listening check for every mode.

## Live software Perform build — 2026-10-07

- Added raw-chord-only live `arp` and `arp2`, software BPM changes that retain beat
  position, gate/step controls, input velocity limiting, selected-channel sustain,
  and note/pedal cleanup. `perform` and `perform-update` are available through the
  JSON service. Hardware clock and performed/bass channels are ignored by this
  route; raw-chord channel must be supplied explicitly.
- All 39 tests passed. New cases cover channel isolation, octave range, gate,
  release, sustain, tempo phase, scheduling stalls, panic, settings validation and
  input-only lifecycle. These are software tests, not proof of hardware matching.
- Rechecked CoreMIDI after the user reported reconnecting Orchid: no `Orchid`
  input/output appeared in either inventory. Requested physical USB MIDI
  enablement and Performed/Bass/Chord channel settings; response pending.
- Restarted the persistent service with the new code and Hydrogen enabled. Its
  PTY disables canonical input buffering/echo to avoid the prior long-JSON line
  limit. Service reported ready; no hardware performance was started.
- Pistil initially showed the user's edited `* ORCHID EP` patch. Options UI
  interaction subsequently returned only the main window/menu bar, and no
  visible settings panel. A brief read-only thread sample showed a running JUCE
  popup handler/audio processing, not evidence of a crash. Did not force quit or
  replace the patch. This UI issue was subsequently resolved with keyboard menu
  navigation: Options → Down → Return opened Audio/MIDI Settings. Selecting the
  software-input row and pressing Space produced a visible checkmark.
- After the user reconnected USB and selected Enable USB MIDI, CoreMIDI enumerated
  `Orchid` input/output. Pistil showed ORCHID CONNECTED. Verified only
  `Orchid Studio Playback` checked under Active MIDI inputs (Orchid and both
  Hydrogen inputs unchecked), MacBook Pro Speakers, 44100 Hz / 512 samples.
  Closed settings with the edited `* ORCHID EP` patch preserved. A first passive
  note window had no events; a longer read-only monitor was armed while awaiting
  actual Performed/Bass/Chord settings and the user's held chord. Raw-chord routing
  and audible live-performance validation remain pending.
- The user confirmed actual MIDI assignments: Performance 01, Bass 02, Chord 03.
  Started the software `arp` at 96 BPM, eighth-note steps, gate 0.75 and velocity
  cap 72, reading only Orchid channel 3 and outputting only software channel 1.
  The service reported `perform_ready`. Listening confirmation and observed
  raw-chord note timing are pending; readiness alone does not establish audio.

## Captured arpeggio replay — 2026-10-06

- Added `capture.session_from_capture` and the offline `import-capture` CLI. They
  map received note timestamps into beats by interpolating the received 24-PPQN
  clock. Only an explicitly selected note channel is imported; transport, clock,
  CC and SysEx never become playback events. This is note-only import, not a live
  record/overdub interface. Sustain/controllers remain unsupported.
- Imported the user's actual channel-1 arpeggio from this session's successful
  clock test, without asking for another performance. Created a six-beat,
  twelve-note loop (55, 48, 52 repeated four times), repeated over 24 beats, in
  `local/captured-orchid-arp.json`. Incoming clock measured 120 BPM. The first
  selected note defines the loop origin; the final note is released at its edge.
- Submitted playback at 90 then 137 BPM with Hydrogen pattern 0, volume 0.3.
  The first verbose service requests exceeded the macOS terminal input-line
  limit and did not start playback. Cleared that unsubmitted input and retried
  compact requests successfully. The listening version uses default velocity 64
  and timing rounded to 0.001 beat; the saved original retains captured velocity
  96 and full timing precision. Both playback runs reported completed cleanup;
  final service status was `playing:false`. The user subsequently confirmed hearing
  the demonstration with “I did” before asking how it would work live.
- All 30 tests passed, including changed-tempo clock normalization, note-channel
  isolation, boundary releases, same-pitch retriggers, incomplete capture
  rejection and offline import without MIDI or file overwrites. Whitespace check
  passed. Hydrogen and MIDI still use independent playback clocks; this short
  tempo-controlled demonstration does not establish phase-locked long-run sync.

- Created a separate Git repository and Python 3.12.14 virtual environment.
- Installed `orchid-studio==0.1.0` editable with `python-rtmidi==1.5.8`.
- CLI help and `python -m pip check` succeeded.
- `orchid-studio doctor --midi` succeeded on macOS 26.7 / arm64.
- Found `/Applications/Pistil.app`, `/Library/Audio/Plug-Ins/VST3/Pistil.vst3`, and `/Library/Audio/Plug-Ins/Components/Pistil.component`.
- MIDI inventory: `GarageBand Virtual Out` input and `GarageBand Virtual In` output. Orchid was absent at this check.
- No MIDI ports were opened, no MIDI messages were sent, and no audio playback was attempted by this project.
- No Linux installation, Wine activation or Linux audio rendering has been tested yet.

## First playback build — 2026-10-06

- Added validated JSON note sessions, software tempo and semitone transpose, finite repeats, virtual software output, read-only incoming channel counts and panic.
- CoreMIDI initialization aborted inside the execution sandbox. Inventory now runs in a subprocess so `doctor --midi` reports that failure as JSON. Outside the sandbox it successfully enumerated GarageBand Virtual In/Out; Orchid was still absent.
- Through Computer Use, created a new GarageBand project with a Pistil AU instrument showing `ORCHID EP`, Sound 001. The separate Pistil standalone still held its edited `* ORCHID EP` state; no preset change or save was made there.
- Set the new GarageBand project's master mix to -10.6 dB and saved it under `local/Orchid Studio Playback.band` (Git-ignored). Track: `Pistil · Performed`.
- Ran `demo --output 'GarageBand Virtual In' --wait 3`: 16 notes / 32 note messages, channel 1, 96 BPM, 10 seconds. The process completed successfully and sent cleanup. No Orchid destination was opened. Listener confirmation was requested separately; audibility is not yet verified.
- The user then clarified that GarageBand must not be a dependency. Removed named GarageBand output from the CLI and closed GarageBand. The local experiment project remains saved and unused; it is not required by the system.
- Added `serve`, a persistent virtual MIDI source with JSON-lines demo/play/status/stop/panic/quit commands. In Pistil standalone's Audio/MIDI Settings, enabled `Orchid Studio Playback`; verified output `MacBook Pro Speakers`, stereo 1+2, 44100 Hz and 512 samples (11.6 ms). Current edited patch was retained.
- With GarageBand confirmed not running, sent `{"command":"demo"}` through the persistent source. The ten-second phrase completed and cleanup was sent. Status then reported `playing: false`. Listener confirmation requested; audibility remains unverified.
- All 16 unit tests passed. Tests cover deterministic timing/transpose/repeats, distinct channels, invalid clips, note retrigger ordering, interrupt/send-failure cleanup, virtual-only output, exact input port selection, native diagnostic crash isolation, service stop responsiveness, EOF cleanup and JSON error recovery.

At that stage, listener confirmation and drums were pending; the following work establishes both.

## Hydrogen and layered playback — 2026-10-06

- Added local OSC drum controls, optional Hydrogen support in the persistent service and one-shot playback, coordinated stop/panic, and separate per-track `loop_beats`. Added an original two-pattern Hydrogen song generator using installed kit metadata without copying sample audio. Generated instruments disable MIDI output.
- Installed official Hydrogen 1.2.7 in `/Applications/Hydrogen.app`. That x86_64 release has OSC compiled out: no `--osc-port` option and no OSC listener even after enabling preferences.
- Built unmodified official 1.2.7 source natively for arm64 with OSC, CoreMIDI, CoreAudio and PortAudio. Build dependencies came from Homebrew: cmake, qt@5, liblo, libsndfile, libarchive, pkgconf, portaudio. The project includes reproducible build/run scripts; runtime files stay under ignored `local/hydrogen-runtime/`.
- Generated and opened `local/first-drums-v2.h2song` with GMRockKit and original `Studio Groove` / `Studio Variation` patterns. The current song was saved through Hydrogen's UI after the combined demo. Earlier `local/first-drums.h2song` is also retained.
- Reopened the saved song with `scripts/run-hydrogen-macos.sh`: UI showed the expected song/kit, 96 BPM and stopped transport; runtime confirmed PortAudio. The first pattern is selected on reopen; session playback explicitly selects its configured pattern.
- Verified live OSC tempo and volume changes through UI/feedback, and pattern selection through the displayed `Studio Variation`. Reports deliberately distinguish UDP sends from acknowledgements.
- The first combined demonstration produced **only pitched notes**, as confirmed by the user. Hydrogen's direct CoreAudio backend was silent, including after explicitly selecting MacBook Pro Speakers at 44100 Hz / 1024 samples; its meters and transport still moved. No underlying CoreAudio bug has been established.
- Hydrogen's command-line renderer produced a non-silent PCM16 stereo WAV at 44100 Hz (451189 frames, peak 5869, RMS 642.42). Playing that render with `afplay` was **confirmed audible** by the user.
- Switched the same native Hydrogen build to its supported **PortAudio** backend, which reported default output and 0.1-second latency. A five-second live drum test was **confirmed audible**. The Mac launcher now selects PortAudio.
- Played the sixteen-beat layered example at 96 BPM through the persistent service: performed channel 1 loops every four beats; bass channel 2 loops every eight beats; Hydrogen pattern 0 at volume 0.3. Changed Hydrogen to pattern 1 during playback. The user confirmed **both notes and drums played and stopped cleanly**. These channel numbers describe synthetic clips, not observed Orchid channel assignments. Independent Pistil patches have not been established.
- Pistil standalone remains on its edited `* ORCHID EP` patch with `Orchid Studio Playback` selected and laptop speaker output. GarageBand is not running or required. Orchid appeared connected in Pistil during this work, but its actual incoming channel roles have not been measured.
- All 26 unit tests passed, including OSC wire types/indexing, validation, coordinated lifecycle and failure cleanup, original pattern generation, and separate loop expansion. Shell syntax and whitespace checks passed. Tests do not establish shared-clock timing.

Still pending after the later live-routing validation above: recording/overdub, DAW-free independent Pistil patches and recall, and phase-locked synchronization. The MIDI scheduler and Hydrogen currently use separate clocks with a common BPM and coordinated start/stop; latency and drift are not compensated. Obtain architecture/access details for the Ubuntu target before installing runtime dependencies. Linux Pistil remains unverified.

## Shared-clock requirement — 2026-10-06

Latest result: the user explicitly selected **Orchid Studio as master clock**.
A 30-second held-arpeggio test received performed notes on channel 1 and tested
standard incoming USB clock at 90 and 137 BPM, both without and with MIDI Start.
The arp stayed at 250.32–250.36 ms between notes; Orchid's outgoing clock stayed
at 120 BPM. Software send cadence was measured near both requested tempos.
**No incoming-clock following was observed.** All diagnostic ports closed; no
notes, CC, SysEx or maintenance messages were sent. See
[the full clock-input test](CLOCK_INPUT_TEST.md) for evidence and limits.

Earlier investigation:

The user requires live Orchid arpeggios, Hydrogen and the software looper to share tempo. Official Orchid V3.60 release notes document MIDI clock output; prior research observed F8 pulses. A new five-second passive read from the current `Orchid` input observed zero clock ticks and no transport messages; no hardware messages were sent. This does not disprove clock output, but current clock enablement/playback conditions must be established before implementing or claiming a working follower. The installed Hydrogen 1.2.7 source handles Start/Continue/Stop but explicitly lists `TIMING_CLOCK` as unsupported in `src/core/IO/MidiInput.cpp`. Its documented shared transport route is JACK; the currently working PortAudio setup does not provide that synchronization.

## Native drums and editable beats — 2026-10-07

- Replaced independent Hydrogen pattern playback with Studio-driven hits, then
  moved sample rendering into the existing native audio host at the user's request.
  User heard the intermediate OSC version and reported remaining drift. That
  intermediate listening test did **not** pass.
- Native service runs without `--hydrogen`. Four Pistils and 64 locally copied
  drum samples share one AVAudioEngine. Both MIDI notes and drum attacks carry
  host-clock deadlines with 40 ms allowance. Hardware clock is not involved.
- A 70-second native test used layer 1 + drums for 30 seconds, then restored
  layers 2/3/4. It rendered 769 musical drum hits (770 including the earlier
  preview), zero late hits (>2 ms), maximum drum placement error 0.02265 ms at
  44100 Hz, within one sample. These are callback measurements, not proof of
  audible alignment with Pistil. Listener confirmation of this native test is
  pending; the earlier OSC drift report must not be described as resolved by ear.
- A simulated 300 × 12-bar run produced exactly 14,400 expected quarter-note
  hits with no duplicated/missing attacks. Added tests for stalls, quantized
  switching, swing, probability, gain, import validation, archive safety,
  persistence, native routing, transactional rollback and clip-clock sharing.
  Full suite: 83 tests passed. Native Swift host compiled successfully.
- Computer Use verified the combined rack, then the new editor: created a blank
  12-bar beat, selected Electric Empire Clap Hard alongside 808 kick/hats,
  entered steps, repeated them across all bars and saved Workshop House.
  Restart and browser reload retained it. Name edits and Undo were tested.
  Narrow view keeps lane controls visible while the step grid scrolls sideways.
- Preserved all three user layers, four Pistil states and mute settings across
  service restarts. Final startup restores `local/native-drums-session.json`;
  current loop export is `local/current-loops-with-sounds.json`. Final service
  is stopped and ready. A silent scheduling/Stop check verified no additional
  drum attacks after Stop acknowledged. Native panic also drains scheduled MIDI
  while output is silent before completing.
- Imported TR808EmulationKit (16), ElectricEmpireKit (32), VariBreaks (16).
  Source kit metadata reports GPL. Audio is stored under local/drums/assets;
  Hydrogen need not remain installed for these sounds. No sample audio or
  proprietary Pistil states are added to tracked files.

## MIDI clock publishing and host-exit recovery — 2026-10-07

- User reported `Pistil host exited` on Play loops. The main service retained
  the three loop layers. There was no native crash report or stderr diagnostic
  for that exit, so its original cause is unconfirmed. A muted reproduction
  with all saved layers and Workshop House passed five start/stop cycles.
- Fixed the dead-host enable guard. Studio now detects a dead child, recreates
  it and restores checkpoint AU states and native samples before playback.
  Added exit codes, cleanup that tolerates a missing renderer, checkpoint-backed
  export, and an enabled **Restart audio** button after failure.
- Verified actual SIGTERM fault injection twice: explicit `pistil-enable` recovery
  and automatic recovery through `loop-start`. Both restored the four patches
  and 64 samples. The automatic test ran muted and restored all original mute
  settings afterward. The original exit cause is not claimed fixed.
- Added opt-in `Orchid Studio Clock` virtual source: 24 PPQN/F8, Start/FA at
  musical beat zero after count-in, Stop/FC on completion/stop/failure. Follows
  all four transport paths and live tempo updates. No hardware output opened.
  Default 40 ms delay matches native audio scheduling; delay is adjustable.
- Real CoreMIDI receiver during 21 s of loop playback at 124 BPM: 945 clock
  pulses, exactly one Start and one Stop, no count-in pulses and no messages
  after Stop. Median interval 20.142 ms (nominal 20.161 ms), range 15.249–24.398
  ms. This measures software MIDI jitter, not external-device synchronization.
  Audio host stayed healthy with zero late drum attacks. Metrics are saved in
  `local/midi-clock-validation.json`.
- 88 tests pass, covering clock counts, changing tempo without resetting phase,
  count-in, delay, pending-pulse cancellation, stall cleanup, virtual-only routing,
  host recovery and previous music/editor behavior. `git diff --check` passes.
- User confirmed both loops and drums played without the host error in the
  latest audible test. Clock publishing is enabled; the final browser check
  showed active playback and outgoing clock pulses. Loops and patches remain
  preserved.

## Circuitry beat refresh — 2026-10-07

- Replaced all 12 native Studio factory arrangements with original 12-bar
  indietronica grooves. Kept API IDs; each has a distinct kick sequence and
  three changing four-bar phrases. User Workshop House retains its notes with
  new drum timbres. Backed up all 13 old documents and the full loop session.
- Prepared/imported 23 CC0 Frequency 303 one-shots from MS-20, TX81Z and SK-5
  sources: silence trimmed, tails faded, band limited and level matched. Source
  filenames/hashes and processing provenance remain with the local kit. 87
  samples now load in the same native audio host as the four Pistil instances.
- Each of the 12 documents passed API save/read and native start/stop checks.
  Offline full-length renders had pre-master peaks 0.499–0.778, with no clipping
  in the fixed-gain previews. These are engineering checks, not listening claims.
- The user heard Subway Steps, Velvet Floor and Prism Lift through Studio and
  said the first two sounded great; Prism Lift's cymbal was grating. Replaced
  Prism Lift's FM hat with Velvet Floor's silk hat, and its open-hat accents with
  quiet soft claps. User still heard the grating sound. A second revision also
  replaced the primary bright clap and noise tick with the approved soft clap
  and soft click, used Subway Steps' pocket hat at lower gain, removed the air
  accent hits, and thinned hats. Updated saved document, factory and previews.
- Added and visually tested Use suggested BPM (108 BPM for Subway Steps);
  disabled while playing. The browser now displays the active drums-only BPM.
  Preserved loop notes/patches, selected beat, MIDI-clock configuration and
  restored the prior 124 BPM default after the UI test.
- 90 tests cover existing behavior, distinct phrases/kick patterns, optional-kit
  fallback and saved-user-edit precedence. The final softened Prism Lift is
  confirmed by the user: “Gone—this sounds good.” The final 12-bar native
  playback had zero late hits and a drum peak of 0.191. Playback stopped cleanly.

## 2026-10-07 — instrument interface, shared tempo and mixer

- Orchid-inspired cream/green enclosure, orange transport, rotary Perform control,
  six-channel volume/pan mixer, global BPM, icon transport and note/time graph.
  Four loop columns and individual note previews sit below the graph; sound
  library is last. Narrow in-app browser visually checked with no horizontal
  clipping or console errors; keyboard dial, tempo and pan controls verified.
- 96 unit tests passed, including phase-continuous tempo, count-in/pause/resume,
  changing-tempo clip/drum ticks, MIDI Stop/Continue, independent mix routing,
  five-state persistence and legacy four-state migration. Native Swift host built.
- Real host ran five healthy AUs with 87 drum sounds. All five native mixer
  buses accepted gain .25 and alternating pan ±.65; restored original values.
  Loop notes remained 32 / 16 / 28 / 0 with original patches.
- Actual running tempo change 124→90 preserved position (.775→.7799 beats);
  subsequent .65 seconds advanced approximately .975 beats. Pause held exactly
  1.7644 beats, then resume advanced. No MIDI-clock error. Evidence:
  `local/interface-validation.json`.
- UI playback exercised Play, global tempo 124→100, Pause, Resume and Stop with
  existing loops/drums. Host and clock reported no errors. This is technical
  verification; listening confirmation is requested separately.
- Restored 124 BPM, Strum defaults, drum volume .3, other gains 1, centered pans
  and stopped playback. Saved complete five-state session to
  `local/current-loops-with-sounds.json`; pre-migration backup is
  `local/before-interface-session.json`.
- Control skill updated and installed. Its bundled validator could not run
  because PyYAML is unavailable in both local Python environments; frontmatter,
  required fields and referenced project paths were checked directly.

## 2026-10-07 — rotary tempo, sounds, drum lengths and Space

- 99 tests pass, including exact repeated/cropped drum hits for 2, 6, 12, 14,
  32 and 64 bars, next-bar length changes, invalid lengths and session recall.
  JavaScript syntax and diff whitespace checks pass.
- Real UI verified BPM dial arrows (124→125→124), Live Sound 051→052 without
  changing four loop labels, Space pause/resume on the page and focused transport
  button, and Space ignored in the BPM input. The original opaque Live patch was
  restored after this test, preserving custom state as well as its preset label.
- Loop, drums, Live and Live+drums buttons all displayed Pause while active and
  Resume while paused. Switching from paused loops to live completed successfully.
- Real drum length 12→2 switched at beat 48; 32-bar length queued while paused.
  The two-bar native run reported zero late drum hits. Full arrangement, patches,
  mixer and 124 BPM restored; user's Prism Lift drum playback resumed.
- Drum graph shows actual arranged hits, lane labels, bar lines and playhead.
  87 sounds remain available; no browser console errors or host errors observed.
  UI evidence: `local/orchid-studio-rotary-drums.png`. Session backup:
  `local/before-rotary-session.json`; current full session saved separately.

## 2026-10-07 — Bézier tempo and Bluetooth audio recovery

- 102 tests passed. New coverage verifies the exact tempo integral, pause/resume
  through a ramp, retargeting without a beat/BPM discontinuity, 24-PPQN pulse
  counts across a ramp, and current native AU/drum tempo propagation.
- Running loop test sampled 108, 107.161, 104.982, 102.005, 98.609, 95.234,
  92.373, 90.492, 90 BPM over the two-second transition, then returned to 108.
  No outgoing MIDI-clock error. Evidence: `local/bezier-tempo-validation.json`.
- macOS default output was the development Beats Pill at 48 kHz. The old host lacked an
  AVAudioEngine configuration-change handler. Rebuilt host now exposes actual
  device/rate/engine state and recovers from configuration-change notifications.
- Saved the current loops and five AU states before restarting; restored them
  and resumed coordinated loop/drum playback. Native status confirms Beats Pill,
  48 kHz, engine running and no audio error. A listening question is pending.
  A live output-device switch has not been verified; only the restored Bluetooth
  route and normal playback have been verified directly. The native System
  Settings inspection stalled, so no output setting was changed through it.
- User listening confirmation: “Yes—audio is coming from the Beats Pill.”

## 2026-10-07 — five harmonic single-key melodies

- Added Bloom, Orbit, Drift, Spark and Tide. Each generates an original four-bar
  monophonic phrase from a held note, with explicit major/minor harmonic variants.
  User feedback rejected the initial pentatonic audition as elementary; revised
  versions use extended progressions, guide tones, Dorian rhythm, chromatic
  enclosures and borrowed minor iv harmony. Revised listening feedback pending.
- 108 tests pass. Added single-note generation, distinct/repeatable phrases,
  transposition, major/minor guide tones, enclosure resolution, modal borrowing,
  loop rendering, division changes, sustain/release/panic, channel isolation,
  MIDI pitch extremes, scheduler stalls and Bézier-tempo alignment coverage.
- Dial exposes 13 modes and descriptions; Rhythm is disabled for the new phrases.
  Live selection and API capability discovery verified; no browser console errors.
- Audition uses one held C, rendered through the same PerformanceEngine used by
  live/loop recording. It plays on the independent Live AU with the user's drums.
  Original loop counts 32/16/28/0 and all five patch states are preserved.
  Full pre-change session: `local/before-melodies-session.json`.
  Revised audition: `local/five-melodies-demo.json`.


### Original Hooks bank — 2026-10-07

Added Sunline, Sidekick, Electric, Bluehour and Anthem as five original four-bar
Perform melodies. They use broad synth-pop, power-pop, minor dance-pop, lyrical
ballad and arena-rock traits from the user's references; no song transcription or
source recording was used. Recurring motifs return in bar three with contrasting
answers and tonic endings. All ten melodic modes retain the same scheduler.

110 Python tests pass, including melodic phrase repeat/division timing, MIDI
channel isolation, sustain/release/panic, pitch limits, transposition, shared tempo
ramps, bank coverage and composed event bounds. JavaScript syntax passes. Browser
checks verified Hooks selection, Bluehour selection, End-key Anthem selection,
Classic rhythm re-enabling, and return to Sunline. Screenshot:
`local/orchid-hooks-perform.png`. Installed control skill updated and local
references checked. Full session preserved in `local/before-hooks-session.json`.

The native host reports the development Beats Pill at 48 kHz with no audio error. A 50-second
audition uses a single held C for each new mode through the Live AU with the
current drum beat; this does not replace the user's loop layers. Audible musical
quality requires the user's feedback, separate from engine/test success.

The audition completed naturally without a host error. The user then started
Sidekick live at 96 BPM and changed the Live sound; this newer activity was left
running rather than restoring the earlier paused state. The recorded loop notes
were compared against the backup and remained identical. A fresh complete session
was saved to `local/current-loops-with-sounds.json`.


### Supplied MIDI Songs bank — 2026-10-07

Imported all five user-supplied MIDI files into ignored `local/perform-midi`,
without using external song material. They contain short monophonic phrases of
7–9 notes. Added an optional Songs bank, source labels/metadata and variable
phrase lengths on the existing shared-clock melody scheduler. Original notes
transpose relative to MIDI 60, without major/minor remapping. Each source ends
with enough silence to complete a 4/4 bar (8/8/8/12/4 beats).

114 Python tests pass. Synthetic MIDI tests cover running status, PPQN, source
rests/dynamics, malformed files, rejection of polyphony/percussion/hanging notes,
transposition, repeat timing and release. Each real supplied file was also
compared against `looper.render` at C4, gate 1 and eighth-note division: note
count, pitch, onset and duration all match exactly. JavaScript syntax check passes.
Browser checked Songs bank selection, Porgy/Africa labels and source-length help;
proof image `local/orchid-songs-perform.png`. Control skill and docs updated.

The session was preserved before restart in `local/before-song-modes-session.json`.
The restarted native host reports the development Beats Pill at 48 kHz, running without an
audio error. A 50-second source-snippet audition uses the Live AU and does not
replace any saved loop notes. Listener confirmation remains separate from those
programmatic checks.

The full audition completed naturally with no host error. Original loop notes
were verified unchanged and the latest complete session was saved.


### Independent Play Along AU — 2026-10-07

Added sixth Pistil AU, direct raw-chord/pedal route, independent mixer controls,
API enable/disable and six-state session recall. Older 4/5-state sessions inherit
their final patch for missing voices. Fresh Sound reports mirror to slot 6 while
preserving the selected-layer report-pair latch. Slot 6 selection isolates hardware
sound changes from all five earlier voices.

118 tests pass, including source-channel isolation, velocity limits, sustain and
panic, independent Perform/direct note lifetimes, worker pause release/draining,
state migration and separate gain/pan routing. Native host builds successfully
(existing CFString pointer warning remains). The real host reports six instruments
and the Beats Pill output at 48 kHz without an audio error. Existing loop data was
compared unchanged. Browser verified On/Off toggle, Play Along sound destination
and the seven-strip mixer. Screenshot: `local/orchid-play-along-mixer.png`.

A loop-backed physical listening check was offered with Perform temporarily muted.
At completion no hearing reply or fresh Sound-dial report had arrived. Do not
claim listener-confirmed audibility or physical sound following yet. Test playback
was paused, original Perform volume restored, Play Along left enabled, and the
six-state session saved to `local/current-loops-with-sounds.json`.


### Per-layer clear controls and API — 2026-10-07

Each loop card now has a Clear trash button. The existing `loop-clear` API accepts
slot 1–4 (omit for all) during playing/paused states, while rejecting armed/active
takes. Only targeted notes are released; patches stay untouched. Empty clears
preserve the prior undo snapshot. Undo remains available after stopping.
121 tests pass, including real Controller command dispatch, invalid slot rejection,
all-layer clearing, shared-pitch ownership, single-layer isolation and undo.
The running HTTP service accepted a clear on its already-empty layer 4; existing
recorded notes were compared unchanged. Browser checks confirmed enabled clear
buttons for populated layers 1–3 and disabled clear for empty layer 4. Screenshot:
`local/orchid-layer-clear.png`. The session was restored paused with all six sounds.

Renamed Include drums to Start drums with loops, added explanatory hover text and
disabled it during an existing loop run to reflect its startup-only behavior.

### API control map, sound reference and per-layer selectors — 2026-10-07

Added `command-help`, `sounds-list` and unsaved `beat-edit` transformations. All
49 commands and UI control groups are described by runtime discovery and generated
`CONTROL_MAP.md`; factory sound descriptions and every installed Perform mode and
rhythm are in `SOUND_PERFORM_MAP.md`. Factory descriptions derive from configuration,
not listening reviews; user slots may differ. Vendor Pistil editor parameters
remain outside Studio's API. Updated the source and installed agent skill with
both maps. YAML frontmatter and reference targets validated; the Python skill
validator could not run because that environment lacks PyYAML.

Each loop card now has its own named sound dropdown using explicit `layer-preset`
slot routing. 127 unit tests pass; JavaScript syntax check passes. New checks cover
single-voice preset routing without changing recorded notes or other voices,
command/mode/catalog coverage, draft editing without publishing and the fix that
keeps Play Along enabled when toggling Sound following.

Real HTTP checks verified discovery, all 100 sound slots and an unsaved drum clone
without creating a saved beat. Before restarting, the complete session was saved
to `local/before-control-map-session.json`; it was restored paused at 96 BPM.
All layer notes, six sound labels and mixer values compared equal. Browser checks
verified four enabled sound dropdowns with 100 named choices each and the correct
restored selections (001, 049, 051, 055). Screenshot:
`local/orchid-layer-sounds.png`. Current session saved again to
`local/current-loops-with-sounds.json`. No new listening claim is made.

### Start on key — 2026-10-07

Added loop-sequencer Start on key checkbox and `key-start` API command. A stopped
session arms silently at beat zero without count-in. Fresh raw-chord note attacks
start playback, or resume an existing paused loop, and reach Live Perform once.
Stop/panic disarm. Other channels, CC, note-off/zero-velocity and repeated held
notes do not wake the transport. Uses the existing loop MIDI input rather than a
second input client/replay path. Runtime status and events expose the armed state.

131 tests pass, including first live note delivery, one initial bass attack,
source-channel isolation, held-key gating, disarming and API validation. JavaScript
syntax checked. Updated API/control map and installed skill. Saved the latest
session before restart; restored notes, six sound labels and mixer compared equal.
Real service armed at beat zero, 108 BPM, Subway Steps, preserving the user's current
Strum mode. Browser verified checked Start on key and WAITING FOR KEY. Physical
robot-key/listening confirmation requested; not yet confirmed at this checkpoint.
Screenshot: `local/orchid-key-start.png`.

The user subsequently confirmed Start on key worked on the physical robot key
press. This confirms that physical test, not just simulated MIDI delivery.

### Many Rooms — 12 additional beat vibes — 2026-10-07

Added twelve distinct 12-bar electronic groove documents, portable JSON examples,
non-overwriting API installer, generated vibe guide and installed skill reference.
Existing 12 Circuitry grooves and Workshop House retained: 25 total on this Mac.
New grooves span ambient pulse, hip-hop, trip-hop, dub techno, disco house, UK
garage, broken beat, electro, liquid D&B, half-time bass, trance and footwork.

134 tests pass. New tests validate all arrangements, required metadata, distinct
kick/snare timing, triplet placement, sample-optional loading and preservation of
saved edits. JavaScript syntax, skill YAML and reference links verified. Real HTTP
checks confirmed all 12 new IDs, metadata and beat-get documents. Browser verified
25 choices and displayed Blue Platform's vibe, density/energy and suggested use.
Proof: `local/orchid-many-rooms.png`; browser selection restored to Subway Steps.

All 12 offline sample-based renders completed without clipping at master 0.34
(maximum peak 0.2177). These approximate native mixing and are not a claim of
listener approval. Renders and analysis: `local/many-rooms-previews/`. Five-vibe
preview order: Amber Tape, Dub Lantern, Blue Platform, Cloud Chaser, Paper Comet.

Latest session was backed up before service restart. Notes, six sound labels and
mixer compared equal after restoration. Preserved Subway Steps at 108 BPM and
current Strum mode, with Start on key armed silently from bar 1. Existing sample
files and their licenses were reused; no samples downloaded or replaced.


### Studio-wide Space transport — 2026-10-08

Replaced the broad all-input exclusion with text-entry-only exceptions. Capture
keydown/keyup suppress focused-control defaults, repeats and scroll. Serialized
commands read current API state for each press. Stopped Space starts the loaded
loop transport with configured drum accompaniment/live input, rather than the
last section used. Existing recording pause protection remains.

Node regression checks pass for sliders, checkboxes, selects, number fields,
buttons/dials, text entry, held repeats, composition/modifier input, rapid presses
and stopped start. JavaScript syntax verified. Real browser + HTTP checks confirmed
slider Space resumes loops/drums; selector Space pauses without changing the beat;
checkbox Space resumes while retaining Start on key; transport-button Space
pauses once without a second native click. Left session paused; no restart or
session replacement required. API guide and skill updated. Static command-help
text will pick up its revised UI description on the next service restart.

### Key-response delay investigation — 2026-10-08

User reported the whole groove was delayed. Current live mode was Chord/off,
so a software melody grid was not active. Output is the development Beats Pill at 48 kHz.
Read-only CoreAudio query reported device latency 9,120 frames (190 ms), safety
offset 0 and buffer 512 frames (~10.7 ms). This is device-reported buffering, not
an acoustic measurement. Native note scheduling adds 40 ms. User explicitly chose
to retain the Beats Pill instead of comparing with built-in speakers. Frodo's
factory slow attack could affect the live voice but does not explain late drums.

Found and removed count-in from playback of existing loops: the former four-beat
count-in at 108 BPM could add 2.22 seconds on ordinary Play. Recording takes keep
their count-in; armed key-start already bypassed it. Paused looper previously sent
a synchronous drum-stop every input poll; cleanup now runs only when entering
pause. Waiting input polls every 2 ms instead of 10 ms.

Added key_start_timing and dispatch events measuring MIDI receipt to first loop
and live note enqueue. Explicitly excludes hardware scanning, native scheduling,
synth attack and output buffering. 135 tests pass, including immediate ordinary
play, recording count-in, single pause cleanup, first-key retention and dispatch
metrics. Session backed up and restored with identical loops, labels and mixer.
Armed at bar 1 on Beats Pill. Physical latency re-test requested; pending at this
checkpoint. API guide and installed skill updated.

The subsequent physical C press (MIDI 48, raw Chord channel 3) was captured:
MIDI receipt → first loop-note dispatch 8.762 ms; first live-note dispatch
13.045 ms. Looper reported no error. These are software dispatch measurements,
not acoustic latency; user hearing confirmation remains separate.


## Portable repository release — 2026-10-08

- 140 Python tests pass with a separate empty data directory, plus browser shortcut checks.
- Source distribution and wheel include UI assets and both Swift sources, with no sample
  audio, supplied MIDI, plugin binaries, transfer archives or credentials in their inventory.
- Installed the wheel into a new virtual environment and ran it from outside the checkout.
- A private transfer restored 87 sounds and 25 beats into a new path containing relocated
  sample references. Unit checks cover checksum failure, unsafe paths and overwrite refusal.
- Built the native host from the installed wheel for arm64. A muted isolated host loaded
  all six saved Pistil AU states and 87 samples, with a running audio engine and no error.
  No MIDI or audition was sent in that check; the active development session was untouched.
- Python commands report the configured data and host paths. Empty sample racks no longer
  require Hydrogen to start the native AU host. Saved sessions restore stopped via --session.
- This is a local relocation/install check, not a second-device listening test. Intel Mac
  audio and cross-version AU state compatibility still need destination hardware validation.
- Public code is MIT licensed; third-party plugin/sample/song content is excluded.

### Mixer API fades and DJ control — 2026-10-09

- Extended `mixer-set` with validated multi-channel volume/pan changes and
  0–120-second linear/smoothstep fades; added `mixer-get`, `mixer-cancel`,
  `capabilities.mixer_schema`, progress and completion/error events.
- Regression checks cover grouped interpolation, exact endpoints, retargeting,
  UI-style overrides, cancellation, paused/stopped operation, drum-volume state,
  host failure, session recall and worker shutdown. All 159 Python tests and both
  browser tests passed. Repository and installed skill validators passed.
- Restarted the stopped local service after saving its complete session. Verified
  an actual grouped fade through the local API and native host: loop slots 1/2
  gain and pan reached their requested endpoints; drum control state matched.
  Restored all seven original mixer values and verified saved sound labels were
  preserved. Play Along remained enabled with transport stopped.
- This confirms API/native control behavior, not listening quality. Fades update
  at control rate, use elapsed seconds independent of musical transport, and are
  not sample-atomic, beat-quantized or equal-power crossfades. Session exports save
  current applied values; unfinished fades are not replayed on import.
