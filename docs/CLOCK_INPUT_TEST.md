# Orchid external-clock verification

Orchid Studio must own the master tempo. This diagnostic establishes whether
the connected Orchid's native arpeggiator can follow standard USB MIDI clock.
Earlier failed drum-transport tests are not sufficient evidence about arp timing.

The vendor's [performance-mode guide](https://support.telepathicinstruments.com/hc/en-us/articles/15280943220367-Exploring-Performance-Modes-Arp-Strum-Pattern-and-More)
describes the arpeggiator as following master BPM. The
[Options overview](https://support.telepathicinstruments.com/hc/en-us/articles/15280847893263-Navigating-the-Options-Menu-A-Complete-Overview)
does not document a clock-input/source selector. MIDI clock output is documented
in the [V3.60 release notes](https://firmware.telepathicinstruments.com/); output
support alone establishes nothing about incoming clock.

## Controlled hardware test

`scripts/check-orchid-clock.py` is an explicit hardware diagnostic, separate from
the product's software-only output path. By default it prints the plan without
opening MIDI. `--run` opens only uniquely named `Orchid` input/output ports and
waits for a performed note. No input is echoed. Its only allowed outgoing messages
are F8 (Timing Clock), FA (Start), and FC (Stop); it sends no notes, CC or SysEx.
The finite test stops its clock after 30 seconds and releases its ports. It does
not modify firmware or replay historical captures.

Before running, obtain the user's readiness, displayed hardware BPM, and a
repeating arpeggio selected without replacing the Sound preset. Keep hardware
volume low. Ask the user to hold one chord throughout, without changing tempo or
the Perform setting. Record firmware and actual channel settings when available.

Six phases of five seconds each:

1. Passive baseline.
2. 90 BPM clock without transport.
3. 137 BPM clock without transport.
4. MIDI Start, then 90 BPM clock.
5. 137 BPM clock while running.
6. MIDI Stop and passive recovery.

Raw received packets and timestamped outgoing clock calls are saved under
Git-ignored `local/clock-test/`; existing capture files cannot be overwritten.
Summaries group simultaneous notes and compute intervals independently for each
channel, excluding the first second of each phase for settling. A repeated
performed stream identifies the candidate arp channel; no default role is assumed.

## Interpretation

For a fixed arpeggiator subdivision, the interval at 137 BPM should be approximately
90/137 of the interval at 90 BPM. Check both repeats, sufficient repeated notes,
outgoing clock cadence/jitter, the baseline and recovery. A display change or
outgoing clock alone is not proof of arpeggiator synchronization. Matching tempo
is only the first check; claiming usable sync also requires phase alignment and
long-run drift testing.

If repeated arp events remain at the original interval despite verified tempo
changes, record no clock-following response in this tested configuration. Do not
generalize that to all firmware/settings. Missing notes, an unchanged chord,
poor clock delivery or a prematurely released chord make the test inconclusive.

First attempt: the user reported displayed BPM 120. The armed recorder received
5761 F8 clock packets over its 120-second wait, but no note-on. It timed out before
any active phase; **zero MIDI messages were sent**. Evidence:
`local/clock-test/120bpm-90-137-clock.json`. Clock output is now observed in the
current connection, but input-clock following remains untested. Establish the
performed-note stream and rerun with a new capture filename.

## Completed test — 2026-10-06

The user held a repeating arpeggio at displayed 120 BPM for the complete test.
Performed note-ons arrived on channel 1. No other note-on channel was observed;
this does not establish the bass/raw-chord assignments. Capture:
`local/clock-test/120bpm-90-137-clock-retry.json`.

| Phase | Software clock sent, measured BPM | Median arp interval (ms) | Orchid clock output (BPM) |
| --- | ---: | ---: | ---: |
| Baseline | — | 250.333 | 120.000 |
| Clock only, 90 | 89.962 | 250.335 | 120.000 |
| Clock only, 137 | 136.967 | 250.355 | 120.007 |
| Start + clock, 90 | 89.966 | 250.328 | 119.994 |
| Running clock, 137 | 136.900 | 250.353 | 120.000 |
| Stop, then recovery | — | 250.324 | 119.995 |

Each interval summary has 16 distinct onsets after settling. Sent-clock timestamps
show 180 ticks per five-second 90 BPM phase and 274 per 137 BPM phase (908 total),
plus one FA and one FC. Software send-call intervals ranged approximately
13.8–32.9 ms across both tempos; these are host timestamps, not hardware receipt
acknowledgements. No notes, CC or SysEx were sent, and all ports closed normally.

**Result: the native arpeggiator did not follow incoming USB MIDI clock in this
configuration**, with or without Start. Its unchanged approximately 250 ms note
spacing remained consistent with eighth notes at 120 BPM. Following the test
tempos would instead produce approximately 333 ms at 90 BPM and 219 ms at 137 BPM
for the same subdivision. Orchid's own clock also remained at 120 BPM.

Treat live native-arpeggiator external sync as unavailable for this project's
current setup. This is a measured negative result for the connected unit/settings,
not a claim about every firmware version or undocumented mode. No firmware/settings
workaround is established. The user requires a software master: capture the actual
performed note sequence and normalize its musical timing for software loop replay,
or implement a separately scoped software arpeggiator. Neither route makes the
live hardware arpeggiator follow the software clock.
