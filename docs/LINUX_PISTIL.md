# Pistil on Ubuntu 26.04.1 — installation experiment

Status checked 2026-10-06: **no native Linux build is listed; Pistil under Wine is unverified**. Telepathic lists macOS 13+ and Windows 10+ and supplies download/authorization details to purchasers. Use the licensed Windows installer from the user's existing purchase. Do not copy the Mac AU/VST3 binary to Linux or put license keys in this repository. [Vendor requirements](https://telepathicinstruments.com/products/pistil).

The target is interpreted as Ubuntu 26.04.1 LTS; confirm with `/etc/os-release`. Its official release is documented by [Ubuntu](https://lists.ubuntu.com/archives/ubuntu-announce/2026-August/000326.html). CPU and machine access still need checking. This procedure assumes x86_64; ARM needs a separate assessment.

## Proposed bridge route

Install Windows Pistil into its own Wine prefix, bridge its VST3 with yabridge, then load it in a native Linux VST3 host. Route Orchid MIDI through the host; USB access inside Wine is unnecessary for note playback.

Yabridge's README warns that 5.1.1 is incompatible with Wine 9.22/10.x and suggests Wine 9.21 or a development build. Check current upstream guidance and record the exact tested pair. Do not downgrade the system blindly. Register the prefix's VST3 directory and synchronize; bridged plugins appear under `~/.vst3/yabridge`. [Upstream setup and compatibility](https://github.com/robbert-vdh/yabridge), [releases](https://github.com/robbert-vdh/yabridge/releases).

After installing an appropriate Wine/yabridge pair, these are the prefix/bridge commands (the installer filename is illustrative):

```sh
WINEPREFIX="$HOME/.local/share/orchid-studio/wine-pistil" wineboot -u
WINEPREFIX="$HOME/.local/share/orchid-studio/wine-pistil" wine /absolute/path/to/PistilInstaller.exe
yabridgectl add "$HOME/.local/share/orchid-studio/wine-pistil/drive_c/Program Files/Common Files/VST3"
yabridgectl sync
yabridgectl status
```

Download only the vendor installer and upstream bridge distribution. Review the installer normally and activate using the user's existing license. Do not export a global `WINEPREFIX` for all plugins. Package-manager commands are intentionally deferred until the target architecture and compatible runtime are verified.

## What must pass on the real machine

- Run `orchid-studio doctor --midi`; record OS, architecture and actual runtime versions.
- Scan and load Pistil; the editor must render and respond, and licensing must complete normally. A blank editor requires investigation; the Mac build uses a web-based UI, but we have not inspected the Windows runtime dependencies. Do not assume WebView2 is required or sufficient.
- Play a short host-generated MIDI clip with Orchid disconnected. Confirm audible output, then save/reopen the host session with the same patch.
- Connect Orchid to the native host and confirm performed/bass streams independently. Disable duplicate monitoring and feedback routes.
- Check three instances with different sounds, sustained notes, pitch bend, stop/panic and stable playback. Record buffer size, sample rate and any dropouts.

Until these checks pass, use native Pistil on the Mac for the demo. A Linux sequencer can remain portable without pretending Pistil's Windows compatibility is established. Alternative renderers will have different sounds unless proven otherwise.
