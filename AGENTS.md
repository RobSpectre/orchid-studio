# Project context

Build a software music system using Orchid as a MIDI controller and Pistil as the sound engine. The user accepts laptop audio and wants software key/transpose, tempo, looping and drums. Prioritize an audible demonstration and a portable CLI/API that agents can operate.

Read `docs/RESEARCH_HANDOFF.md` and `docs/LINUX_PISTIL.md` before choosing the host architecture. The original research is in the sibling `../orchid_demo` repository; treat that archive as read-only in this project. It contains uncommitted work. Do not copy proprietary firmware/plugin binaries or credentials into this repository.

Use Computer Use for Pistil/DAW UI. The user prefers us to operate the computer and asks only for physical actions, display readings or hearing confirmation. Play an attention chime before asking for that help (macOS: `afplay /System/Library/Sounds/Glass.aiff`; use an appropriate available equivalent on Linux). Do not claim audio was heard merely because MIDI was sent or a meter moved.

This project does not modify Orchid firmware or invoke maintenance commands. An earlier diagnostic caused a loud high tone and required a reboot. Do not replay old research captures. Native Key/Loop/BPM/master Volume setters remain unresolved; implement those musical behaviors in software. Physical MIDI reports are not proof of incoming hardware support.

Keep performed notes and bass separate. Do not merge raw chord notes with the performed stream and create duplicate notes. Check actual channel configuration before assuming defaults. Default to software destinations, never a MIDI feedback loop into Orchid. Stop/panic must release active notes and sustain on all used software tracks.

Pistil on Linux is not verified. Confirm distro, architecture, Wine/yabridge versions, plugin activation, GUI, MIDI/audio and project recall before declaring support. Do not auto-downgrade system Wine or install arbitrary runtime workarounds. Preserve the user's licensed installation and current patches. Reuse existing hosts before writing a custom plugin host or recreating synth DSP.
