> The host now also renders local drum samples in the same audio engine. See
> [Studio drum machine](DRUM_STUDIO.md). Build includes `src/orchid_studio/native/DrumSampler.swift`.
> Scheduled MIDI and drum hits use host-clock deadlines with 40 ms allowance;
> native panic silences output while draining that horizon before releasing notes.

# Independent Pistil sounds on macOS

Orchid Studio can load six instances of the user's installed Pistil Audio Unit,
one per loop layer plus independent Live Perform and Play Along voices. The host is a small Swift/AppKit/AVAudioEngine application;
it does not require a DAW or bundle the proprietary plugin. The existing native
Pistil standalone remains available as the shared-sound fallback.

## Build and run

Requirements: macOS, Apple's command-line developer tools, and the user's
activated Pistil AU registered with macOS (either system-wide or per-user installation).
The installed AU identifies itself as `aumu / Pitl / Tptp`. No additional SDK,
package-manager dependency or plugin download is required for this Mac build.

```sh
scripts/build-pistil-host-macos.sh
.venv/bin/orchid-studio serve --api-port 8765 --api-only \
  --sound-input Orchid --pistil-host
```

The generated app is `Orchid Studio Pistil.app` in the configured data directory.
See [PORTABILITY.md](PORTABILITY.md) for setup and transfer commands. The service owns its child
process through JSON pipes; closing the service also releases its notes and
closes the host. Plugin diagnostics go to `pistil-host.log` in that directory. The host loads
muted, waits for Pistil's deferred initial preset setup, then enables its mixer
at gain 0.35. It uses the macOS default audio output. Six in-process plugins
share the host's audio engine; an AU crash can stop all six, but leaves loop
notes in the separate Python service. Restart and restore saved loops to recover.

For an existing service started without the flag, stop playback and issue
`{"command":"pistil-enable"}`, or use **Enable independent sounds** in the page.
Enabling does not import the standalone application's edited patch. Existing
note-only loop files contain no historical sounds: select initial sounds for
those layers once and save the enriched document. Keep the standalone patch
intact during migration. Do not re-enable direct Orchid MIDI in standalone as
part of this route; the host receives Studio's internal per-layer messages only.

## Selection, playback and persistence

- Each layer has a separate synth, effects, held notes and AU patch state.
  Identical pitches on two layers no longer merge into one shared voice.
- **Select** or the **Active layer / record into** selector directs fresh Sound
  dial messages to that layer. Monitoring uses Live (slot 5), or the take slot
  while recording. Select Live in the mixer to change its sound. Opening its **Sound editor**
  also selects it. Other recorded layers keep their sounds. A new take selects
  its slot automatically. Finish/cancel a take before selecting another layer.
- The original Sound-dial filter still accepts only validated preset CC102 and
  the observed 142-byte Sound-state report. A paired report stays on the same
  layer even if selection changes between packets. No captured hardware packets
  are replayed. The host creates no hardware MIDI endpoint or hardware output.
- `layer-preset` selects factory Sound 1–100 on an explicit software layer.
  Synth/effect editing uses the real Pistil editor. Card labels identify the
  most recent dial/API preset; subsequent custom edits are retained in the AU
  state even if that label still shows its originating preset number.
- Loop Save/export includes six opaque base64 AU property-list states under
  `instruments`. Open/import validates all notes and patch containers before
  replacement, and requires the host when patch states are present. The host
  waits for queued Sound changes before capturing state. No plugin binary or
  samples are embedded. Save these user patch documents outside tracked examples.
- Stop retains sounds and loops; service exit does not autosave. The local
  working backup used during development is `local/current-loops-with-sounds.json`.
  An older note-only import leaves current sounds unchanged. Undo affects note
  takes/edits, not sound selection or edits made inside the plugin editor.

```json
{"command":"pistil-status"}
{"command":"layer-select","slot":2}
{"command":"layer-preset","slot":2,"preset":49}
{"command":"layer-editor","slot":2}
{"command":"loop-export"}
```

API status reports whether the independent host is enabled, the selected slot,
labels and host errors. `pistil-status` additionally reads per-instance output
peaks; these prove signal activity, not audible output. Normal live Perform and
legacy clip playback use Live (slot 5); the four-layer looper explicitly
routes each layer to its own instance. Stop/Panic release all six engines.

This implementation is macOS-only. The Python loop format/control layer remains
portable, but this AU state cannot be presumed interchangeable with Windows
VST3 state. Linux Pistil compatibility remains unverified. Studio sends BPM to
the AU host. Native drums, loops and software Perform use the shared Studio
timeline. Each AU has its own volume/pan bus; drums have their own pan bus.
Mixer values are saved with AU states. Four-state sessions remain importable.

Sources: [Apple AU instantiation](https://developer.apple.com/documentation/avfaudio/avaudiounit/instantiate(with:options:completionhandler:)),
[Apple AU state](https://developer.apple.com/documentation/audiotoolbox/auaudiounit),
[Pistil independent-instance behavior](https://support.telepathicinstruments.com/hc/en-us/articles/16936612575247-Desyncing-Pistil-Instances-from-Orchid-to-Prevent-Sound-Changes).


## Audio output changes

The host follows macOS's default audio output. A hardware channel/sample-rate
change can stop AVAudioEngine. Studio now observes its configuration-change
notification, reconnects the main output at the new device format and restarts
rendering while retaining all six AU instances and their mixer/patch states.
It releases voices during recovery to avoid hanging notes. Physical held chords
may need to be pressed again; loop scheduling continues on the Studio timeline.

`pistil-status.host.audio` exposes device name/ID, output sample rate, engine
running state, route-change count and any recovery error. A successful MIDI send
or retained peak is not proof that the audio engine is running or audible.
On this Mac, the development Beats Pill was the default output at 48 kHz; restarting the
previous host on that output restored an active engine. Listening confirmation
is recorded separately. Bluetooth acoustic latency is separate from Studio's
shared beat clock; external wired devices may require their own delay adjustment.

Reference: https://developer.apple.com/documentation/AVFAudio/AVAudioEngineConfigurationChangeNotification


## Dedicated Play Along voice

The macOS host now has six independent Pistil AUs: loops 1–4, Live Perform 5,
and direct Play Along 6. The seventh mixer strip (including drums) gives Play
Along its own volume, pan and enable toggle. The sound selector also offers
Play Along. The new AU initially inherits the saved Live sound when restoring
older four/five-voice sessions; six-voice exports use `pistil-au-v3`.

Play Along listens only to the configured raw Chord channel (confirmed 3 on this
Orchid). It sends unpatterned notes and sustain/sostenuto to slot 6. It excludes
the performed/bass streams, clock, program changes and SysEx. It runs while the
Studio transport runs, alongside live Perform, loops or drums; pause/stop releases
its notes and pedals. Press keys again after resuming. Disable its toggle or turn
its mixer down when you want only the generated Perform voice. It is not recorded
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
