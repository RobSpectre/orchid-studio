# Orchid Studio

Software looping, sequencing and drums, played from a Telepathic Orchid and rendered on the computer with Pistil.

```text
Orchid USB MIDI → channel routing → MIDI loops / sequencer
                                    ├─ Pistil: chords
                                    ├─ Pistil: bass
                                    ├─ Pistil: lead
                                    └─ software drums → laptop audio
```

This is a new project, separate from the hardware reverse-engineering archive. Its first milestone is audible Orchid-to-Pistil playback on macOS. A looper, drum engine and plugin host are not implemented yet. The initial CLI provides read-only environment diagnostics.

## Start here

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[midi]'
.venv/bin/orchid-studio doctor --midi
```

`doctor` reports the platform, installed Wine/yabridge command versions, common Pistil plugin locations and optional MIDI port names. It never opens a device port or sends MIDI. Run without `--midi` if only platform diagnostics are needed.

- [Research handoff](docs/RESEARCH_HANDOFF.md): established findings and current machine state.
- [Linux Pistil installation experiment](docs/LINUX_PISTIL.md): Ubuntu 26.04.1, Windows VST3, Wine and yabridge; compatibility unverified.
- [Development milestones](docs/DEVELOPMENT_PLAN.md): audible proof, looping, drums and automation.

Pistil is proprietary and must be installed and licensed separately. This repository contains no vendor binaries, firmware, sound banks or license keys. Linux is an experimental target: Telepathic lists only macOS and Windows support. See the linked research for sources.
