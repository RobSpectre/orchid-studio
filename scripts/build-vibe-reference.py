"""Generate the Many Rooms vibe guide and portable beat JSON from runtime data."""
import json
from pathlib import Path
from orchid_studio.vibe_beats import documents, BANK
root=Path(__file__).resolve().parents[1]
lines=['# Many Rooms — 12 additional electronic vibes','',
'Twelve original 12-bar (48-beat), 4/4 arrangements. Adds to the existing Circuitry bank; no existing beat IDs are replaced. Descriptions express composition intent, not a claim of listener approval.','',
'| Beat / API ID | BPM | Energy / density | Vibe and best use |','| --- | ---: | --- | --- |']
for d in documents().values():
 lines.append(f"| **{d['name']}** · `{d['id']}` | {d['suggested_bpm']} | {d['energy']} / {d['density']} | {d['vibe']} Best for: {d['best_for']}. |")
lines+=['','## Find and select a vibe','',
'`beats-list` and `capabilities.beats` expose `bank`, `genre`, `feel`, `vibe`, `tags`, `energy`, `density`, `best_for`, `arrangement`, `bars` and `suggested_bpm`. `beat-get.document` returns the full editable arrangement with the same metadata. Older/custom beats may have null energy/density and empty tags; do not infer labels for those.','',
'```json','{"command":"beats-list"}','{"command":"beat-get","beat":"blue-platform"}','{"command":"beats-select","beat":"blue-platform"}','{"command":"tempo","bpm":132}','```','',
'Selecting a beat preserves global BPM and queues a live change to the next bar. Apply `tempo` only when you want to move the entire session. For standalone audition while stopped:','',
'```json','{"command":"beats-play","beat":"still-water","bpm":68,"volume":0.3}','{"command":"stop"}','```','',
'Use IDs, not numeric pattern indexes; user documents can change catalog ordering. `drums-length` still supports even 2–64-bar playback lengths. Sources remain 12 bars. Keep the selected arrangement and performance settings when auditioning alternatives; save `loop-export.document` first.','',
'## Choose around a melody','',
'- Most space: Still Water, Black Velvet, Velvet Gravity. Dub Lantern is a sparse steady pulse.',
'- Warm movement: Amber Tape, Peach District.',
'- Syncopated interplay: Blue Platform, Broken Compass, Chrome Messenger.',
'- More rhythmic activity: Cloud Chaser, Horizon Engine, Paper Comet. Use softer melody parts or lower drum level if these compete.',
'- Density describes hit activity; energy describes the intended feel at suggested tempo. Neither sets volume automatically.','',
'## Sound palette and installation','',
'The bank uses the installed, softened Orchid Circuitry kit plus selected 808/Electric Empire electronic kick, clap and click samples. No crash, open cymbal, bell, whistle or ringing accent is used. Source licenses and sample paths remain in `kits-list`; no audio binaries are bundled in source or beat JSON.','',
'Factory defaults load from `vibe_beats.py` only when each groove’s required sounds are installed. Saved beat documents override defaults. The existing `local/` sample library and licensed sample metadata are preserved. `scripts/install-vibe-bank.py` adds missing IDs through the API and skips existing beats to preserve edits. It needs no stopped transport because no sample import/reload is performed.','',
'Portable note-only beat documents: `examples/drums/many-rooms/*.json`. Install their referenced samples before importing with `beat-save`. The current Mac already has all required sounds. On another installation, inspect `kits-list`; do not silently substitute missing samples.','',
'## Phrase structure','']
for d in documents().values():lines.append(f"- **{d['name']}**: {d['arrangement']}")
lines+=['','## Local preview audio','',
'`local/many-rooms-previews/` contains full 12-bar offline WAV previews and level measurements. `five-vibes.wav` plays four bars each of Amber Tape, Dub Lantern, Blue Platform, Cloud Chaser and Paper Comet, with short gaps. This is sample-based preview mixing, separate from the live native host and listener confirmation.', '',
'Regenerate with `scripts/render-vibe-previews.py` in a Python environment with NumPy and the installed samples; FLAC conversion uses macOS `afconvert`.']
text='\n'.join(lines)+'\n'
(root/'docs/BEAT_VIBES.md').write_text(text)
(root/'skills/orchid-studio-control/references/beat-vibes.md').write_text(text)
out=root/'examples/drums/many-rooms';out.mkdir(parents=True,exist_ok=True)
for d in documents().values():(out/(d['id']+'.json')).write_text(json.dumps(d,indent=2)+'\n')
print('Generated vibe guide and 12 portable beat documents')
