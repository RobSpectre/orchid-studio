# Research handoff — 2026-10-06

## Goal and accepted direction

The hardware project pursued remote access to every Orchid rotary encoder. Working routes exist for presets, synth parameters, effects and voicing, but independent native Key, Loop, BPM/drum transport and master Volume control remain unresolved. The user now wants to read Orchid MIDI and render its sounds on the laptop, with software loops, additional rhythms and separate bass/chord/lead parts. Computer audio is accepted for this approach.

Use Pistil itself; parameter descriptions alone are insufficient to recreate identical DSP. Telepathic describes Pistil's synth engine as identical to Orchid's. We have not performed a bit-exact audio comparison. [Standalone documentation](https://support.telepathicinstruments.com/hc/en-us/articles/15715167630479-Using-Pistil-as-a-Standalone-Application).

Orchid sends performance notes (including strums/arpeggios), bass and optional raw chords on separate MIDI streams. Official guidance describes defaults 1/2/3, but firmware notes and prior investigation indicate the raw chord output can default to Off. Confirm actual settings. [MIDI recording guide](https://support.telepathicinstruments.com/hc/en-us/articles/15303089658127-How-to-Record-MIDI-from-All-Three-Channels-Performance-Bass-Chord).

Pistil offers AU/VST3 hosting. Multiple instances can be desynced from Orchid to keep independent patches while receiving notes. Desync ignores CC/SysEx, so verify sustain/controller behavior before relying on it. [DAW loading](https://support.telepathicinstruments.com/hc/en-us/articles/15841252156815-Loading-Pistil-in-your-DAW), [instance desync](https://support.telepathicinstruments.com/hc/en-us/articles/16936612575247-Desyncing-Pistil-Instances-from-Orchid-to-Prevent-Sound-Changes).

## Existing machine state

- macOS 26.7; Pistil standalone 1.0.2 and its AU/VST3 are installed. User unlocked Pistil previously.
- GarageBand is installed and has hosted Pistil successfully. Its prior investigation instance may route plugin output to a now-absent virtual MIDI destination named `pistil-hosted-investigation-2026-10-02`; inspect routing afresh.
- Standalone was last open on `* ORCHID EP`, Sound 001, with edited state. Preserve that state; don't silently discard it.
- Latest inventory before project creation contained only GarageBand Virtual In/Out, no Orchid MIDI port. No laptop playback demonstration has been verified yet.
- Pending physical setup: normal Orchid startup (no Options held), Enable USB MIDI, physical Volume lowered for a laptop-only listening test. Do not repeat bootloader-entry tests.
- User identified the Linux target as "Linux 26.04.01 - latest LTS release," interpreted as Ubuntu 26.04.1 LTS. CPU architecture and remote access remain unknown.

## Hardware evidence to retain

The sibling research repository is `../orchid_demo` (an optional private development archive, not an installation dependency). It has substantial uncommitted research; do not reset, blanket-stage or move it.

Useful relative paths within that repository:

- `skills/orchid-midi/references/coverage.md` — supported vs unresolved controls.
- `skills/orchid-midi/references/names.md` — Sound, Bass, Perform and FX labels.
- `skills/orchid-midi/src/orchid_midi_cli/sequencer.py` — MIDI-only demo/groove prototype, not a software audio/drum engine.
- `skills/orchid-midi/captures/pistil-hosted-findings-2026-10-02.json` — hosted plugin experiments.
- `skills/orchid-midi/references/recovery-investigation.md` — recovery limitations.
- `skills/orchid-midi/references/maintenance-incident.md` — loud-tone incident.

Verified hardware controls include Sound/Bass presets, Sound Reverb/Phaser/Chorus/Filter, chord/bass voicing and Drum Saturator Mix. Perform has a factory-preset donor workaround, not an independent mode/amount command. The Python CLI's parameter catalog is broader than what has been physically tested.

MIDI Start/Stop/Continue, clock, Machine Control and captured CC replay did not provide native loop/drum transport or Key/master Volume setters in prior tests. Native drum note triggering is not established. Provide a separate software drum engine.

Official stock firmware reinstall succeeded on October 4. Options-held startup later reached `Orchid Boot V3.92`, but that mode did not enumerate USB on this Mac/cable. Normal startup did enumerate and sounded normal. Independent recovery is still not established. No modified firmware was installed. None of that recovery work is required for this project.
