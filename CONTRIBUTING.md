# Contributing

Use Python 3.10+ and an editable `.[midi]` install. Run the Python unittest suite
and `node --test tests/test_studio_shortcuts.cjs` before a change. Native hosting
uses the bundled Swift sources in `src/orchid_studio/native/`; compile on macOS
with `orchid-studio build-host`. Tests must not require purchased plugin binaries.

Keep runtime/user content out of Git. Never commit plugin binaries, activation
credentials, vendor firmware, supplied song MIDI, sample audio, private transfer
archives or AU patch snapshots. Sample licenses remain with imported samples.
Use synthetic fixtures for automated tests. Public examples contain original
notes/beat structure, not transcriptions of supplied commercial songs.

API behavior lives in `api.py`; agent/UI command descriptions live in
`control_reference.py`. Update docs and `skills/orchid-studio-control` when those
contracts change. Generate public control maps using an empty data directory so
private song names and locally installed content do not enter generated docs:

```sh
ORCHID_STUDIO_DATA_DIR=/tmp/orchid-empty-catalog .venv/bin/python scripts/build-control-reference.py
```

Keep performed/bass/raw-chord input separate. Software tempo remains master;
no hardware feedback route or firmware work is part of Studio. Read `AGENTS.md`
for project constraints. If reporting audio behavior, distinguish dispatch timing,
render counters and actual listening confirmation.

The CI template is `scripts/ci-workflow.yml`. To enable GitHub Actions, copy it to
`.github/workflows/ci.yml` and push with workflow permission. The initial publishing
credential lacked that permission; CI is not enabled merely by having this template.
