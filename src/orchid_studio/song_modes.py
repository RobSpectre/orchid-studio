"""Local user-supplied MIDI phrases; intentionally separate from bundled music."""
import json
from pathlib import Path
from .midi_phrase import read_phrase

from .paths import data_dir

ROOT=data_dir()/'perform-midi'


def load_songs(root=None):
    root=Path(root) if root is not None else data_dir()/'perform-midi'
    manifest=root/'songs.json';modes={};errors=[]
    if not manifest.exists():return modes,errors
    try:
        entries=json.loads(manifest.read_text())
        if not isinstance(entries,list) or len(entries)>32:raise ValueError('Expected up to 32 song entries')
        for entry in entries:
            mode=entry['id'];file=entry['file']
            if not isinstance(mode,str) or not mode.startswith('song-') or not mode[5:].replace('-','').isalnum():
                raise ValueError('Song IDs must start with song- and use letters/numbers/hyphens')
            if Path(file).name!=file:raise ValueError('MIDI file must be inside the local song directory')
            if mode in modes:raise ValueError('Duplicate song mode')
            phrase=read_phrase((root/file).read_bytes())
            maximum=max(n[3] for n in phrase['notes'])
            modes[mode]={'bank':'songs','label':entry['label'],'title':entry['title'],
                'description':f"{entry['title']} · supplied MIDI · {len(phrase['notes'])} notes · {phrase['loop_beats']//4} bars. C4 = original pitch.",
                'harmony':'Source intervals preserved; chord quality does not reharmonize this phrase',
                'source_file':file,'source_beats':phrase['source_beats'],
                'suggested_bpm':phrase['suggested_bpm'],'reference_note':60,
                'phrase_units':phrase['loop_beats']*2,
                'events':tuple((b*2,(n-60,n-60),d*2,v/maximum) for b,n,d,v in phrase['notes'])}
    except (OSError,ValueError,KeyError,TypeError) as exc:
        # A bad optional import must not take down existing live instruments.
        return {},[str(exc)]
    return modes,errors
