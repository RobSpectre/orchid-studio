"""Add missing Many Rooms beats via API; preserve all existing beat IDs/edits."""
from orchid_studio.api_client import request
from orchid_studio.vibe_beats import documents

def call(command,**kwargs):
    r=request({'command':command,**kwargs})
    if r.get('status')=='error':raise RuntimeError(r['error'])
    return r

def main():
    existing={d['id'] for d in call('beats-list')['beats']}
    sounds={s['id'] for s in call('kits-list')['sounds']}
    additions=[d for d in documents().values() if d['id'] not in existing]
    missing={l['sound'] for d in additions for l in d['lanes']}-sounds
    if missing:raise SystemExit('Install required sounds first: '+', '.join(sorted(missing)))
    for d in additions:call('beat-save',document=d)
    print(f'Added {len(additions)} beats; skipped {len(documents())-len(additions)} existing IDs.')
if __name__=='__main__':main()
