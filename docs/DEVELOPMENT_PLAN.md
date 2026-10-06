# First working milestones

1. **Audible native playback.** Inventory MIDI, load the licensed native Pistil in an existing Mac host, route Orchid's performed notes, lower hardware output and confirm laptop sound with the user. Save a separate host project and preserve the user's existing session.
2. **Separate parts.** Route bass independently; establish separate chord and lead instances with retained patch state. Check note channels, sustain, note-offs and Sound-dial synchronization explicitly. Document actual host routing.
3. **Software MIDI loops.** Record timestamped note/controller events in musical ticks, play multiple clips, implement record/overdub/stop/clear, tempo, quantization, transpose/key behavior and reliable panic. A transpose/scale operation is not automatically equivalent to Orchid's internal chord engine; label the behavior precisely.
4. **Software drums.** Use an established sampler/synth or a small documented drum renderer with redistributable/generated sounds. Put kick, snare and hats under the same software transport as MIDI loops. The computer produces the audio.
5. **Agent control.** Expose deterministic JSON commands and session files: inputs, tracks, sounds, tempo, recording, clip launch, mute, mix, stop and panic. Reuse the existing MIDI CLI where its protocol controls are needed; do not fork its entire research archive.
6. **Linux validation.** Try the licensed Windows Pistil VST3 in a compatible Wine/yabridge setup on the actual Ubuntu target. Promote it from experimental only after GUI/activation, audio, MIDI, independent instances and reopen/recall pass.

Start with an existing host. Choose an embedded hosting architecture only after proving that the installed plugin can produce the requested music through a stable route. Do not spend the first milestone implementing a new DAW.

Acceptance demo: record a chord phrase from Orchid, release the keys and hear it repeat on the laptop; add a bass line, software drums and a lead; change software tempo and key; stop with no stuck notes; reopen the session with independent sounds intact. Log which steps were observed, not merely attempted.
