# Circuitry Vol. 2

Twelve original 12-bar electronic arrangements, inspired by the contrast of
intimate, intricate programming and clear dance pulses in The Postal Service.
No recordings, melodies or exact drum patterns from the band are used.
Jimmy Tamborello's [Song Exploder explanation](https://songexploder.net/transcripts/the-postal-service-transcript.pdf)
was the aesthetic reference. The patterns leave tonal space for Orchid/Pistil:
short clicks and noise replace long tuned accents, with modest ghost notes,
three distinct four-bar phrases and a clean return to the downbeat.

| Beat (same API ID) | BPM | Character |
| --- | ---: | --- |
| Liquid Circuit · `liquid-circuit` | 160 | Soft liquid breaks |
| Neon Breaks · `neon-breaks` | 148 | Cut-up pocket breaks |
| Subway Steps · `subway-steps` | 108 | Shuffled two-step |
| Night Runner · `night-runner` | 84 | Spacious half-time |
| Velvet Floor · `velvet-floor` | 116 | Warm micro-house |
| Glass House · `glass-house` | 124 | Bright clipped house |
| After Hours · `after-hours` | 102 | Broken late-night house |
| Warehouse Glow · `warehouse-glow` | 128 | Dry motorik pulse |
| Aurora Drive · `aurora-drive` | 120 | Airy synth-pop drive |
| Prism Lift · `prism-lift` | 132 | Trance-pop |
| Orbital Pulse · `orbital-pulse` | 136 | Interlocking electro |
| Daybreak Rush · `daybreak-rush` | 140 | Buoyant electronic finale |

The running UI/API retains stable beat IDs. **Use suggested BPM** sets Studio's
shared tempo while stopped; selection alone still preserves tempo. All notes
and drums remain on the existing Studio transport and native audio engine.
Use Edit a copy, then lane sound pickers to combine any of the 87 loaded sounds.

## Samples and reproducibility

The **Orchid Circuitry** kit contains 23 selected MS-20, TX81Z and Casio SK-5
one-shots by [Frequency 303 / Allan Legemaate](https://www.frequency303.com/samples/),
released by the author under CC0. Source packs:

- [MS-20 drums](https://www.frequency303.com/samples/ms20-drums/): download **Drums** as `MS-20-Drums.zip`.
- [TX81Z drums](https://www.frequency303.com/samples/tx81z-drums/): `TX81Z-Drums-AllanLegemaate.zip`.
- [SK-5 drums](https://www.frequency303.com/samples/sk5-samples/): **Drums**, `SK-5-Drums.zip`.

Put the archives in `local/drum-downloads`. Run the preparation script using a
Python environment with NumPy, then the installer with Studio running and stopped:

```sh
python3 scripts/prepare-indie-samples.py
.venv/bin/python scripts/install-indie-bank.py
```

Preparation decodes PCM/float WAV, trims silence, removes DC, gently filters
extremes, shortens resonant tails, applies boundary fades, matches peaks by role,
and writes 44.1 kHz PCM mono WAV. It does not download or execute pack content.
Source filenames, hashes, processing settings and license live alongside the
prepared local kit. Original archives remain unchanged. Sample binaries remain
outside tracked source; the scripts and rhythm definitions reproduce the bank.

The installer backs up the full loop session and all replaced beats before
importing the kit and saving the 12 documents through the public API. It leaves
custom compositions alone. On this Mac, Workshop House was separately updated
with new kick/clap/hat sounds while retaining its notes. The original 13 beat
documents and session are in `local/indie-bank-backup/`.

On new library construction, Circuitry factory arrangements are used only when
all required sounds are installed. Saved user documents override factory defaults.
Without the pack, the old 808 bank remains available; legacy Hydrogen song export
still produces the old 808 arrangements.

Local review renders are in `local/circuitry-previews/`: all 12 full arrangements
plus `three-grooves.wav` (Subway Steps, Velvet Floor, Prism Lift). These are offline
previews, separate from the live native playback check; level measurements alone
do not establish perceived quality.
