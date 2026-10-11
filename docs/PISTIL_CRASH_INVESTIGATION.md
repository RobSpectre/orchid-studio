# Pistil crash investigation — October 11, 2026

Confirmed trigger: a scheduled MIDI event whose absolute sample timestamp is
already behind the audio renderer can crash Pistil 1.0.2. Orchid Studio's native
host can submit exactly that event. Silent isolated tests reproduced both the
demo's exact Pistil fault location and its heap-corruption failure.

This investigation did not change the running demo, its patches, audio routing,
licensed installation, or production host binary. A host-owned render-buffer
scheduler (`native/MIDIScheduler.swift`, reported as `render-buffer-v1`) now
implements the repair direction below; its regression tests pass, but it has not
yet run in the demo with Pistil. Diagnostic programs were separate processes;
offline tests had no audio device output, and the real-time host probes
remained muted throughout.

## Reports and account comparison

The demo account supplied 11 `OrchidStudioPistil` macOS crash reports on October
11, between approximately 15:03 and 16:53 Eastern:

| Reports | Failure |
| --- | --- |
| 8 | Allocator detected `memory corruption of free block`, SIGTRAP |
| 3 | SIGBUS in `OrchidProcessor::processBlock` + 10088, Pistil image offset 5946968 |

The direct Pistil crashes are the reports ending `152009`, `152736`, and `165309`.
They fault at an audio-output sample store. Their render-segment counters are
2,147,483,647 in two cases and 2,147,483,433 in the third, far beyond a normal
audio buffer. Other reports detect damage later in unrelated allocations,
including Swift input parsing, JUCE timers, and Pistil's own crash handler.
An allocator stack alone does not identify the original writer.

The rspectre account also has native-host crash reports at 00:16 and 00:20 on
October 11. The first reports the same heap corruption; the second faults in
CoreAudio's object lookup. These predate the diagnostic tests in this investigation.
The second is not independently proven to have the same cause.

All 13 original reports identify the same host and Pistil binaries:

- Host UUID: `92cf72a9-f51b-3a1b-86b5-4a5d7ac0a684`.
- Pistil 1.0.2 UUID: `4a53fda5-9011-3ff5-8e6e-3e3b44ba6165`.
- The component is the system installation at
  `/Library/Audio/Plug-Ins/Components/Pistil.component`.

The demo workspace symlinks to the rspectre checkout. Both use the same
`local/Orchid Studio Pistil.app` and `local/pistil-recovery.json`. The compiled
host's cached Swift source matches the current native host source. There is no
different demo host build in these reports.

The demo launcher also starts the robot service and visualizer and selects an
`Orchid PA` multi-output device using BlackHole and headphones. At inspection,
the running host instead reported MacBook Pro Speakers, three route changes,
and a 16 kHz output format. These establish environmental differences and route
changes, but do not establish the audio device as the crash trigger.

## Fault in Studio's scheduling path

`NativeHost.call` in `src/orchid_studio/pistil_host.py` assigns ordinary MIDI
requests a deadline of `time.monotonic() + 0.04`. The native host reads commands
on a worker and handles them on the main queue.

The MIDI branch in `src/orchid_studio/native/PistilHost.swift` converts the
deadline using the instrument's last render timestamp:

```swift
let delta = at - AVAudioTime.seconds(forHostTime: last.hostTime)
let target = last.sampleTime + Int64(max(0, delta) * last.sampleRate)
schedule(target, 0, 3, buffer.baseAddress!)
```

For a late request, clamping the delta to zero selects `last.sampleTime`.
That is an earlier render position, not an instruction to play immediately.
Rendering can also advance between reading `lastRenderTime` and scheduling.
Thus increasing the 40 ms allowance or merely clamping the delta is insufficient
to eliminate the race.

Apple documents `AUEventSampleTimeImmediate` as the special next-cycle value;
it is distinct from a previously observed sample timestamp. See
[AUEventSampleTime](https://developer.apple.com/documentation/audiotoolbox/1387633-aueventsampletime)
and the installed SDK's `AUAudioUnit.h` scheduling declarations.

Python's monotonic clock and `mach_absolute_time` were compared locally and
agreed; a Python/native clock-epoch mismatch was not observed.

## Reproduction and controls

A small diagnostic reuses AVAudioEngine and the installed Pistil AU. It renders
four 512-frame blocks offline at 44.1 kHz, then schedules one MIDI event. The
next block begins at sample 2048. Each case runs in its own process.

| Submitted timestamp | Result |
| --- | --- |
| `AUEventSampleTimeImmediate` | 20 subsequent blocks rendered; clean exit |
| 2048, current block boundary | 20 subsequent blocks rendered; clean exit |
| 3812, future event | 20 subsequent blocks rendered; clean exit |
| 2147485695, far future | 20 subsequent blocks rendered; clean exit; not a long-run test |
| 1536, one block late | SIGTRAP, same allocator corruption signature |
| 2047, one sample late | SIGBUS at Pistil `processBlock` + 10088 |
| -2048, stale negative time | SIGBUS at Pistil `processBlock` + 10088 |

The one-sample-late test reproduces the exact instruction from all three direct
Pistil demo faults without drums, six voices, preset restoration, robot input,
hardware MIDI, or live audio routing. It uses the stock preset in one instance.

A separate muted copy of the existing six-voice Studio host added timing logs
without changing its scheduling behavior. Ten note-offs with normal 40 ms
deadlines completed successfully. A fresh process receiving just one note-off
with a deadline 100 ms in the past exited with SIGTRAP and the same allocator
corruption. Its final timing log was:

```text
at=9899.162061375 host=9899.280525083333 sample=34304
rate=44100 delta=-0.1184637083333655 target=34304
```

These are crash reproduction results, not listening tests. All experimental
processes exited or were reaped. The live demo service was only queried for
status and events.

## Repair direction and remaining uncertainty

Studio should retain deadlines in a host-owned MIDI queue and deliver due events
against the current render buffer, clamping late events to a valid current-buffer
offset. Future events must remain queued. Stop/panic, restore, shutdown, and
route recovery must cancel pending events before releasing notes. This preserves
Studio's master timeline and avoids racing a stale render timestamp.

A simpler temporary approach is deadline-based dispatch using immediate MIDI
delivery, accepting block/thread scheduling jitter. The immediate offline test
passed, but this workaround has not been integrated or validated as a production
fix. Do not silently claim sample-accurate timing for such a workaround.

Add bounded scheduling diagnostics: late-event count, maximum lateness,
route changes, and process exit timestamps. Current shared `pistil-host.log`
was empty, and historical service events lack per-command timestamps. We cannot
prove which delay caused each original crash or quantitatively explain the
higher observed frequency in demo. Additional load, main-queue work, and audio
route transitions are plausible contributors, not established causes.

The reproducible trigger and host defect are established. Attribution of every
historical failure to this trigger, and production stability after repair,
remain unverified. Pistil also needs defensive handling of late MIDI events;
the host-side repair should prevent this unsafe input rather than relying on a
vendor update.

Private evidence and diagnostic sources are in
`local/crash-investigation-2026-10-11/` (untracked). This directory contains only
reports, service snapshots/logs, and our diagnostic source/executables; it does
not contain copied proprietary plugin binaries or credentials.
