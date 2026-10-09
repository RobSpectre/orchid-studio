---
name: orchid-studio-control
description: Operate Orchid Studio through its local API — transport, six Pistil voices, Perform modes, loops, drums, samples, mixer scenes, fades and MIDI clock. Use for Studio control, DJ-style mixing and discovering its sound/Perform map; not for Orchid firmware or hardware parameter research.
---

# Orchid Studio control

Project: the `orchid-studio` checkout. CLI: `orchid-studio` (or `.venv/bin/orchid-studio` in a checkout).
Run `doctor` to locate runtime data; inspect `status.storage` for the running service.
UI: `http://127.0.0.1:8765/`. Send JSON to `POST /command`.

Read `status` and `capabilities` before changing a session.
Check `status.orchid_connection` for current MIDI port presence; `connected:null`
means unknown/unavailable, not disconnected. A ready Sound follower can have a stale
port after USB changes. Connection does not imply transport is playing or audio is audible. For a specific command,
use `{"command":"command-help","name":"loop-clear"}`. Without `name` it returns
all command descriptions, fields, prerequisites, the UI map and drum-edit actions.
Prefer this running API over opening competing MIDI/OSC clients.

## Find the right control

- [Complete control map](references/control-map.md): every Studio UI function,
  API command, fields, constraints, document operations and draft undo/export.
- [Sounds and Perform](references/sounds-perform.md): 100 Pistil slots, every
  installed Perform mode and rhythm, descriptions and evidence limitations.
- [Beat vibes](references/beat-vibes.md): 12 additional Many Rooms arrangements,
  from sparse ambient to garage, D&B, trance and footwork; IDs, tempos and uses.
- [Mixer and DJ moves](references/mixer.md): grouped levels, fades, crossfades,
  pan sweeps, mix snapshots and restoring the previous balance.
- Live discovery is authoritative: `sounds-list` for Pistil/drum sounds,
  `perform-options` for modes/banks/descriptions/settings, `beats-list` for drum
  arrangements and `kits-list` for sample provenance. Optional Songs vary by machine.
- Beat document details: [DRUM_STUDIO.md](references/drum-studio.md).
- Session/HTTP details: [API.md](references/api.md).
- Host recovery/platform details: [PISTIL_HOST.md](references/pistil-host.md).

```sh
.venv/bin/orchid-studio request '{"command":"status"}'
.venv/bin/orchid-studio request '{"command":"capabilities"}'
```

## Session and routing rules

Save `loop-export.document` before restarting or replacing a session. Keep the
whole document: recorded notes, independent sounds, mixer, tempo and drum settings.
Never replace the user's layers with a demo. `loop-import` requires stopped
transport and an enabled native host for instrument states. Samples and supplied
song MIDI under the configured data directory are not bundled; preserve those directories separately.

This Orchid was confirmed Performed 1, Bass 2, Chord 3. Recheck if configuration
changes. Live Perform and Play Along consume only the explicit raw Chord channel.
Do not merge Performed/Bass notes with raw chords or create a hardware MIDI loop.

Native AU slots: loops **1–4**, Live Perform **5**, direct Play Along **6**.
Mixer channels: `layer-1`…`layer-4`, `drums`, `live`, `play-along`. Use
`layer-preset` with an explicit slot and preset; `layer-select` chooses the next
physical Sound-dial destination. Fresh Sound reports also update slot 6. Selecting
6 isolates that change from earlier voices. A new direct voice inherits the saved
Live patch until a fresh report; Studio cannot reliably query current hardware sound.

`play-along` enables raw notes/pedals even while stopped or paused. Pause leaves
held notes alone; Stop/panic releases them, and fresh keys still play. Its On/Off
route is independent of Sound following. Native startup with
`--sound-input Orchid --pistil-host` enables the confirmed channel-3 route.

Space in the Studio UI pauses/resumes the whole transport, including with mixer,
selector or button focus. From stopped it starts the loaded loop session with its
configured drums and live input. Text fields retain spaces. API agents use explicit
`pause` / `resume` / `loop-start`; active takes must finish/cancel before pause.

Studio owns global BPM: `tempo` changes all software timing and published MIDI
clock, using a two-second Bézier transition. `transition_seconds:0` is immediate.
`clock-configure` requires stopped playback; it publishes `Orchid Studio Clock`
at 24 PPQN with Start/Stop/Continue (no idle clock or SPP), default offset 40 ms.
Orchid's hardware arpeggiator is not a verified clock follower.

## Musical operations

For mixer work, read `mixer-get` and `capabilities.mixer_schema`; retain the returned
`mixer` object before a DJ move. `mixer-set` accepts one `channel` or a `channels`
map, with `volume` (linear gain 0–1.5), `pan` (-1–1), optional `transition_seconds`
(0–120) and `curve` (`linear` or `smoothstep`). Use one grouped request for a
crossfade. Defaults are immediate; timed fades continue while stopped/paused.
`queued` means accepted, not finished: verify `mixer_automation` or the
`mixer_transition_completed` event, and check `mixer_error`. Manual changes replace
fades on their channel. `mixer-cancel` freezes current values; Stop/panic also
cancels fades. Restore the saved mixer with `mixer-set.channels`; never assume
unity was the previous balance. Gain zero leaves sequencing/routing enabled.

For Live Perform, `perform` starts; `perform-update` changes a running performance;
`perform-configure` changes defaults and the looper monitor. Read settings bounds
from capabilities. `queued` updates require `perform_updated`/status verification.
The software Perform modes are original interpretations, not exact hardware clones.

`key-start` with `enabled:true` arms loaded loops silently. When stopped, supply
`input`, `chord_channel`, optional `settings` and `drums` as for `loop-start`.
A fresh raw-chord note starts at beat zero without count-in; the triggering note
also feeds Live Perform. On an existing paused loop it resumes from the cursor.
Held-note repeats, Performed/Bass channels and CCs do not wake it. Stop/panic disarm;
re-enable to wait for another key. Disable with `enabled:false` for manual playback.
Inspect `looper.start_on_key`, `waiting_for_key`, and `loop_key_started` events.
`looper.key_start_timing` measures MIDI receipt to first loop/live dispatch, not
heard latency; it excludes synth attack and audio/Bluetooth buffering. Ordinary
loop playback starts immediately too; count-in is only for recording a take.

For loops, use eighth-note recording grid `.5` by default. `loop-start` without
`slot` plays existing layers; with `slot` it arms a take. `loop-record` arms another
layer at the next loop boundary. Empty takes preserve old clips. `loop-step` inserts
explicit pitches without physical timing. `loop-clear` takes slot 1–4 (omit for all),
works during playback/pause except an active take, and preserves sounds. Stop then
`loop-undo` restores the last edit. Clear on an empty layer preserves undo history.
`loop-cancel` discards unfinished input. Pause is blocked during a take.

Use `drums:{"engine":"studio","beat":"glass-house","volume":0.3}` on loop/Perform
start for accompaniment. Omit drums to start without them. Native samples and Pistil
share one audio engine; Hydrogen's independent transport is not used. `beats-select`
queues to the next bar; `drums-length` sets an even 2–64-bar runtime override or null.
Source arrangements and playback length are separate; inspect `beat-get` fields.

For selecting a vibe, inspect `beats-list` fields `vibe`, `tags`, `energy`,
`density` and `best_for`. Many Rooms adds 12 full 12-bar grooves. Start sparse
(Still Water / Black Velvet / Velvet Gravity) when a melody needs space; choose
Cloud Chaser / Paper Comet for more activity. Descriptions are composition intent,
not listening confirmation. Selection preserves BPM; apply `tempo` deliberately.
Never assume older/custom beats have energy/density metadata. Prefer beat IDs.

For drum edits, use `beat-get` then `beat-edit` for clone/new, steps/accents,
copy/repeat/clear bar, resize, swing and lane sound/gain/mute. These are unsaved
transforms returning `document` plus `undo_document`; keep client history and use
`beat-save` to publish. Clone with a new ID to preserve originals. Browser drafts
remain private until saved. Default new compositions to 12 bars; avoid harsh/tuned
accents unless requested. `kits-import`, `sample-upload`, rack reload and sample
preview require stopped playback. Preserve source licenses.

## Verify and recover

A successful command, transmitted MIDI, meter movement or host counter is not proof
of audibility. Inspect errors in `status`, `events` and `pistil-status.host.audio`.
Before asking for physical input, a display reading or listening confirmation,
play `afplay /System/Library/Sounds/Glass.aiff` on this Mac. Ask the user only for
physical/sensory steps; operate software yourself. Use Computer Use for controls
inside the Pistil plugin; `layer-editor` opens it but does not expose every vendor
synth/FX parameter as a Studio API control.

If the API is unavailable, start one process and wait for `api_ready`:

```sh
.venv/bin/orchid-studio serve --api-port 8765 --api-only --sound-input Orchid --pistil-host
```

The native host reuses the installed licensed AU and needs no DAW. Recover a failed
host using `pistil-enable` while stopped; checkpoint restoration cannot recover
unsaved patch edits made after capture. Preserve standalone/plugin edits and licenses.
Do not install arbitrary runtimes, change Orchid firmware or replay archived captures.
Linux Pistil support is unverified. Legacy Hydrogen OSC is optional and requires an
explicit need; consult the checkout’s `docs/HYDROGEN.md`.

## Install or transfer to another Mac

Read [portability](references/portability.md) for setup and supported platforms.
Full hosting is macOS-only; an installed Windows VST3 does not provide this AU host.
Use the skill’s bundled references rather than assuming the original developer’s paths.
`ORCHID_STUDIO_DATA_DIR` (or the global `--data-dir` CLI option) selects writable state.
Existing checkouts with `local/` retain it; new Macs use Application Support.

`orchid-studio build-host` compiles bundled Swift source using Apple tools; it never
copies Pistil. `backup FILE.zip` captures the running session plus local samples,
beat edits and supplied MIDI. Match the server’s data directory and finish an active
take first. This is a private transfer artifact, never a public repository asset.
`restore FILE.zip --to NEW_DIRECTORY` validates and relocates into a new directory.
Build using that data directory, then `serve --pistil-host --session PATH/session.json`
with API/MIDI flags as above. Launch restores stopped; reconfigure actual input,
raw Chord channel, output device, clock and key-start on the destination.
A successful compile/import is not proof of audible playback on another Mac.
