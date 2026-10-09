# Mixer and DJ moves

Use the running local API. Read `status`, `capabilities.mixer_schema` and
`mixer-get` first; older services may need the updated source and a session-safe
restart. Native audio must be healthy for changes. Keep the `mixer` object as
`original_mix` so every move can be restored to the user's actual balance.

## Channels and timing

`layer-1`–`layer-4` are the loop voices; `live` is generated Perform; `play-along`
is the independent raw-key voice; `drums` is the native sample rack. Volume is
linear gain: 0 silences, 1 is unity, 1.5 is the maximum. Pan is -1 left, 0 center,
1 right. Gain zero does not stop a loop, disable Play Along, or clear notes.
Loop mute (`loop-mute`) and the Play Along toggle remain separate controls.

Use `mixer-set` with either `channel` and volume/pan or a `channels` map. All
values are validated before applying; omitted fields keep their current values.
`transition_seconds` defaults to 0 (immediate), accepts up to 120 seconds, and
uses `linear` or `smoothstep`. Smoothstep eases the beginning and end. These are
control-rate fades attempted at 50 Hz, not sample-accurate or equal-power fades.
Group members share a start time but native writes are sequential.

Fades run in wall-clock duration even while stopped or paused. To estimate a
four-bar fade at steady BPM, use `16 * 60 / bpm` seconds. A later BPM change does
not stretch that duration; there is no automatic bar alignment. Issue on the
chosen beat using Studio's `clock` if musical alignment matters.

## Moves

These levels are examples, not assumed current settings. Choose endpoints from
the saved mix and the user's intended balance. Do not turn up every channel to
unity merely to make a transition.

Drop the drums immediately:

```json
{"command":"mixer-set","channel":"drums","volume":0}
```

Crossfade two loop voices over eight seconds (first establish the desired
starting balance, such as loop 1 at 0.7 and loop 2 at 0):

```json
{"command":"mixer-set","channels":{"layer-1":{"volume":0},"layer-2":{"volume":0.7}},"transition_seconds":8,"curve":"smoothstep"}
```

Sweep the direct synth to the right while gently reducing its level:

```json
{"command":"mixer-set","channel":"play-along","volume":0.6,"pan":0.7,"transition_seconds":4}
```

Freeze those faders at their current values:

```json
{"command":"mixer-cancel","channels":["layer-1","layer-2","play-along"]}
```

To recall the saved mix, send `{"command":"mixer-set","channels":original_mix,
"transition_seconds":2}` with the actual saved object substituted. Snapshots are
client-held JSON; no named scene library is implied. Complete session exports
include current applied levels, but never resume unfinished fades on import.

## Verify and interrupt

A fade returns `queued`. Check `mixer-get.mixer_automation`: each active channel
has `from`, `target`, `transition_seconds`, `curve`, and applied `progress`.
Completion removes that channel and emits `mixer_transition_completed`.
Check `error` and `mixer_error` events; a host failure cancels active fades and
may leave a partially applied group. Do not interpret no active fades alone as
successful arrival at the requested endpoint: compare the actual mix.

A new set or UI fader move cancels the prior fade on that whole channel, even if
only pan or volume was supplied. Other channel fades continue. `mixer-cancel`
without channels cancels all at their current values. Stop/panic, session import,
host recovery and shutdown cancel all fades. Pause/resume leaves fades running.
Explicit drum volume from legacy controls or new accompaniment overrides its fade.
A completed control transition is not listener-confirmed sound. Use the project's
attention chime before asking the user to listen or play physical keys.
