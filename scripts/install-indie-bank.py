#!/usr/bin/env python3
"""Install the prepared Circuitry kit and original 12-bar bank via the running API.
Backs up every replaced document and the full session before changing anything.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
from orchid_studio.api_client import request
from orchid_studio.indie_beats import documents

from orchid_studio.paths import data_dir
ROOT=data_dir()
def call(command,**kwargs):
    r=request({'command':command,**kwargs})
    if r['status']=='error':raise RuntimeError(r['error'])
    return r

def main():
    if call('status')['playing']:raise SystemExit('Stop Studio playback before installing the bank.')
    kit=ROOT/'drum-downloads/OrchidCircuitry'
    if not (kit/'drumkit.xml').is_file():raise SystemExit('Run prepare-indie-samples.py first; see docs/INDIE_BEATS.md.')
    backup=ROOT/('before-circuitry-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir()
    (backup/'session.json').write_text(json.dumps(call('loop-export')['document'],indent=2))
    for identifier in documents():
        (backup/(identifier+'.json')).write_text(json.dumps(call('beat-get',beat=identifier)['document'],indent=2))
    call('kits-import',path=str(kit))
    for d in documents().values():call('beat-save',document=d)
    print('Installed 12 arrangements. Backups:',backup)

if __name__=='__main__':main()
