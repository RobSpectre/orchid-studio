# Current drum architecture — 2026-10-07

User chose native sample playback inside Studio after a shared Python timeline
with OSC-triggered Hydrogen still sounded out of time. The native sampler now
shares AVAudioEngine with Pistil; clock and audio validation is recorded in
VALIDATION.md. Editable beat documents, kit import and mixed sounds are described
in DRUM_STUDIO.md. Earlier Hydrogen/JACK investigations below are historical.

# First working milestones

2026-10-07 control milestone: local HTTP API and control page expose all software
Perform settings; a discoverable `orchid-studio-control` skill uses the same API.
The electronic Hydrogen bank contains 12 arrangements, 12 bars each, split equally
between D&B, house and trance. Synthesized TR808EmulationKit samples replace the
initial acoustic-sounding direction. See [API.md](API.md).

2026-10-07 implementation: all eight visible Perform categories and an original
software bank of eight four-beat patterns are implemented. See
[LIVE_PERFORM.md](LIVE_PERFORM.md). Channel 3 raw chords and live laptop Arp audio
are confirmed. New mode timing, channel isolation and cleanup have automated
coverage; exact Orchid factory behavior still requires comparison recordings.

Orchid Studio generates notes for Pistil using its own BPM, with bass and the
hardware performed stream excluded from this route. Slop randomization, Harp
voicing and factory Pattern tables are not claimed as exact clones. Hydrogen
still needs a shared transport integration. Live generation is distinct from the
already demonstrated captured-note playback; simultaneous live recording/overdub
and looping remain to implement.

Clock-input test result: the connected Orchid did not follow 90/137 BPM incoming USB clock with or without Start; its held arpeggio remained at 120 BPM. See [CLOCK_INPUT_TEST.md](CLOCK_INPUT_TEST.md). The capability check below has therefore returned a negative result for the current setup; proceed with software-master loop replay and do not assume the native live arpeggiator can be synchronized.

Architecture constraint (2026-10-06): use Pistil standalone directly; GarageBand and other DAWs must not be dependencies. Orchid Studio owns sequencing and agent control and exposes a software-only virtual MIDI source. Keep the original research archive read-only.

Synchronization requirement (2026-10-06): Orchid Studio is the master clock and owns BPM. Orchid's live arpeggios/performance, the software looper and Hydrogen should follow one tempo and beat reference, including tempo changes. Equal numeric BPM and simultaneous start are insufficient. Establish whether Orchid follows incoming MIDI clock before promising synchronization of its native arpeggiator. If it cannot, preserve captured performed notes as tempo-controlled software loops; live software arpeggiation is a separate feature, not verified equivalence to Orchid's performance engine. Hydrogen 1.2.7 explicitly rejects `TIMING_CLOCK` in `src/core/IO/MidiInput.cpp`, so forwarding F8 to it is not a sync implementation. Evaluate software-master JACK timebase (Hydrogen's supported transport synchronization), including Mac audio-backend implications, before adding that dependency. Validate beat alignment, start/downbeat mapping, tempo changes, long-run drift, output latency and clock-loss cleanup.

1. **Audible native playback.** Inventory MIDI, connect the licensed native Pistil standalone to Orchid Studio's virtual MIDI source, lower hardware output and confirm laptop sound with the user. Preserve the user's current patch. The first software-generated phrase and persistent JSON transport are implemented; the user confirmed pitched notes audible. Live raw-chord Arp routing is now listener-confirmed.
2. **Separate parts.** Route bass independently; establish separate chord and lead instances with retained patch state. Check note channels, sustain, note-offs and Sound-dial synchronization explicitly. Document actual host routing.
3. **Software MIDI loops.** Record timestamped note/controller events in musical ticks, play multiple clips, implement record/overdub/stop/clear, tempo, quantization, transpose/key behavior and reliable panic. A transpose/scale operation is not automatically equivalent to Orchid's internal chord engine; label the behavior precisely.
4. **Hydrogen drums.** Use Hydrogen as the drum machine and control its patterns, kits, mixer, tempo and transport through OSC. The initial adapter, two original patterns, layered MIDI clip playback and coordinated start/stop are implemented. Establish reliable live audio, then shared clock synchronization and quantized launches; the initial separate clocks are not phase-locked. See `HYDROGEN.md`.
5. **Agent control.** Expose deterministic JSON commands and session files: inputs, tracks, sounds, tempo, recording, clip launch, mute, mix, stop and panic. Reuse the existing MIDI CLI where its protocol controls are needed; do not fork its entire research archive.
6. **Linux validation.** Try the licensed Windows Pistil VST3 in a compatible Wine/yabridge setup on the actual Ubuntu target. Promote it from experimental only after GUI/activation, audio, MIDI, independent instances and reopen/recall pass.

Start with Pistil standalone. Investigate its separate-part capabilities before choosing how to provide independent sounds without a DAW. Consider a minimal plugin-host component only if standalone cannot satisfy that requirement and after the direct playback proof. Do not spend the first milestone implementing a new DAW.

Acceptance demo: record a chord phrase from Orchid, release the keys and hear it repeat on the laptop; add a bass line, software drums and a lead; change software tempo and key; stop with no stuck notes; reopen the session with independent sounds intact. Log which steps were observed, not merely attempted.
