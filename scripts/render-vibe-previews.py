"""Offline sample-based previews; requires NumPy, does not touch live transport.

Approximate native sample mixing; listener review remains separate from validation.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import wave
import xml.etree.ElementTree as ET
import numpy as np
from orchid_studio.drum_library import DrumLibrary
from orchid_studio.vibe_beats import documents

from orchid_studio.paths import data_dir
ROOT=Path(__file__).resolve().parents[1];OUT=data_dir()/'many-rooms-previews';OUT.mkdir(parents=True,exist_ok=True)
loader=importlib.util.spec_from_file_location('prepare_samples',ROOT/'scripts/prepare-indie-samples.py')
module=importlib.util.module_from_spec(loader);loader.loader.exec_module(module)
lib=DrumLibrary();rate=44100;cache={}

def sample(id):
    if id in cache:return cache[id]
    sound=lib.sounds[id];root=ET.fromstring(sound['instrument']);path=Path(next(root.iter('filename')).text)
    if path.suffix.lower()!='.wav':
        dest=OUT/(id+'-source.wav')
        if not dest.exists():subprocess.run(['/usr/bin/afconvert',str(path),str(dest),'-f','WAVE','-d','LEI16'],check=True,capture_output=True)
        path=dest
    try:mono,sr=module.decode(path.read_bytes())
    except ValueError:
        with wave.open(str(path),'rb') as f:
            assert f.getsampwidth()==2
            sr=f.getframerate();mono=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(float).reshape(-1,f.getnchannels()).mean(axis=1)/32768
    if sr!=rate:mono=np.interp(np.arange(round(len(mono)*rate/sr))*sr/rate,np.arange(len(mono)),mono)
    gain=float(root.findtext('volume') or 1)*float(root.findtext('gain') or 1)
    layer=root.find('.//layer')
    if layer is not None:gain*=float(layer.findtext('gain') or 1)
    pan=float(root.findtext('pan') or 0)
    stereo=np.stack((mono*np.sqrt((1-pan)/2),mono*np.sqrt((1+pan)/2)),axis=1)*gain
    cache[id]=stereo;return stereo

def write(path,audio):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())

stats=[];montage=[]
for id,d in documents().items():
    seconds=48*60/d['suggested_bpm'];audio=np.zeros((round((seconds+1)*rate),2));lanes={l['id']:l for l in d['lanes']}
    for h in d['hits']:
        lane=lanes[h['lane']];x=sample(lane['sound'])*lane['gain']*h['velocity']*.34
        beat=h['beat']
        if int(np.floor(beat*4+1e-8))%2:beat+=d['swing']*.25
        start=round(beat*60/d['suggested_bpm']*rate);audio[start:start+len(x)]+=x[:len(audio)-start]
    peak=float(abs(audio).max());rms=float(np.sqrt(np.mean(audio**2)))
    assert 0<peak<1,(id,peak)
    write(OUT/(id+'.wav'),audio)
    stats.append({'id':id,'seconds':round(seconds,2),'peak':round(peak,4),'rms':round(rms,4),'hits':len(d['hits'])})
    if id in ('amber-tape','dub-lantern','blue-platform','cloud-chaser','paper-comet'):
        excerpt=audio[:round(16*60/d['suggested_bpm']*rate)].copy();fade=min(2205,len(excerpt))
        excerpt[-fade:]*=np.linspace(1,0,fade)[:,None]
        montage.extend((excerpt,np.zeros((round(.6*rate),2))))
write(OUT/'five-vibes.wav',np.concatenate(montage));(OUT/'analysis.json').write_text(json.dumps(stats,indent=2))
print(json.dumps({'renders':len(stats),'maximum_peak':max(x['peak'] for x in stats),'montage':str(OUT/'five-vibes.wav')}))
