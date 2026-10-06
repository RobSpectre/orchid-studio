# Initial validation — 2026-10-06

- Created a separate Git repository and Python 3.12.14 virtual environment.
- Installed `orchid-studio==0.1.0` editable with `python-rtmidi==1.5.8`.
- CLI help and `python -m pip check` succeeded.
- `orchid-studio doctor --midi` succeeded on macOS 26.7 / arm64.
- Found `/Applications/Pistil.app`, `/Library/Audio/Plug-Ins/VST3/Pistil.vst3`, and `/Library/Audio/Plug-Ins/Components/Pistil.component`.
- MIDI inventory: `GarageBand Virtual Out` input and `GarageBand Virtual In` output. Orchid was absent at this check.
- No MIDI ports were opened, no MIDI messages were sent, and no audio playback was attempted by this project.
- No Linux installation, Wine activation or Linux audio rendering has been tested yet.

Next: register this folder as a project, continue the playback task there, and restore normal Orchid USB MIDI connectivity before live capture. Obtain architecture/access details for the Ubuntu 26.04.1 target before installing runtime dependencies.
