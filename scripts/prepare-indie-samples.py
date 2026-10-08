#!/usr/bin/env python3
"""Prepare CC0 Frequency 303 one-shots for Studio; requires numpy, never downloads.

Download the three archives linked in docs/INDIE_BEATS.md into local/drum-downloads.
Only data files are read. Outputs and source audio stay in gitignored local/.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import wave
import zipfile
import xml.etree.ElementTree as ET
import numpy as np

from orchid_studio.paths import data_dir
ROOT = data_dir()
KIT = 'Orchid Circuitry'
# Name, source pack, path, max seconds, high-pass, low-pass, peak, pan.
SAMPLES = [
 ('Analog Pillow Kick','MS-20-Drums','MS-20-drums/Kick - 1.wav',.32,25,5000,.86,0),
 ('Analog Punch Kick','MS-20-Drums','MS-20-drums/Kick - 3.wav',.24,28,6000,.86,0),
 ('Analog Round Kick','MS-20-Drums','MS-20-drums/Kick - 5.wav',.28,28,4200,.86,0),
 ('Analog Paper Snare','MS-20-Drums','MS-20-drums/Snare - 1.wav',.19,140,6500,.8,0),
 ('Analog Soft Clap','MS-20-Drums','MS-20-drums/Clap - 1.wav',.18,240,6200,.75,.03),
 ('Analog Air Clap','MS-20-Drums','MS-20-drums/Clap - 2.wav',.22,280,7000,.75,-.03),
 ('Analog Dust Hat','MS-20-Drums','MS-20-drums/Closed Hat - 1.wav',.065,2100,7500,.60,-.12),
 ('Analog Silk Hat','MS-20-Drums','MS-20-drums/Closed Hat - 4.wav',.09,1700,7200,.60,.10),
 ('Analog Open Hat','MS-20-Drums','MS-20-drums/Open Hat - 2.wav',.18,2300,6800,.60,.12),
 ('FM Compressed Kick','TX81Z-Drums-AllanLegemaate','Standard/Kick - Bass Drum Compressed.wav',.26,28,5500,.86,0),
 ('FM Soft Kick','TX81Z-Drums-AllanLegemaate','Additional/Kick - Bass Drum 1.wav',.29,28,4200,.86,0),
 ('FM Short Snare','TX81Z-Drums-AllanLegemaate','Additional/Snare - Snare 1 Short.wav',.14,180,6500,.80,0),
 ('FM Low Snare','TX81Z-Drums-AllanLegemaate','Additional/Snare - Snare 2 Lo.wav',.18,180,6000,.80,0),
 ('FM Bright Snare','TX81Z-Drums-AllanLegemaate','Standard/Snare - Snare 1 High.wav',.16,200,7200,.75,0),
 ('FM Fine Hat','TX81Z-Drums-AllanLegemaate','Standard/Hat - FM Hi-Hats High.wav',.055,2500,7800,.60,-.14),
 ('FM Low Hat','TX81Z-Drums-AllanLegemaate','Standard/Hat - FM Hi-Hats Low.wav',.085,1800,6900,.60,.1),
 ('FM Air Shaker','TX81Z-Drums-AllanLegemaate','Additional/Perc - Shaker Hi.wav',.085,2000,6800,.55,.18),
 ('FM Sand Shaker','TX81Z-Drums-AllanLegemaate','Additional/Perc - Shaker Lo.wav',.075,1300,6000,.55,-.18),
 ('FM Soft Click','TX81Z-Drums-AllanLegemaate','Additional/Perc - Wood Block.wav',.027,850,5400,.5,-.1),
 ('FM Noise Tick','TX81Z-Drums-AllanLegemaate','Standard/FX - Noise Shot.wav',.032,1200,6500,.5,.12),
 ('Pocket Kick','SK-5-Drums','SK-5-Drums/Kick.wav',.23,32,4600,.86,0),
 ('Pocket Snare','SK-5-Drums','SK-5-Drums/Snare.wav',.14,180,5800,.75,0),
 ('Pocket Hat','SK-5-Drums','SK-5-Drums/Hat.wav',.065,1800,6800,.60,-.08),
]


def decode(data):
    if data[:4]!=b'RIFF' or data[8:12]!=b'WAVE':raise ValueError('expected RIFF WAVE')
    offset=12;chunks={}
    while offset+8<=len(data):
        tag=data[offset:offset+4];size=struct.unpack_from('<I',data,offset+4)[0]
        chunks[tag]=data[offset+8:offset+8+size];offset+=8+size+(size%2)
    fmt,channels,sr,_,_,bits=struct.unpack_from('<HHIIHH',chunks[b'fmt ']);width=bits//8;raw=chunks[b'data']
    if fmt==3:
        x=np.frombuffer(raw,dtype='<f4' if bits==32 else '<f8').astype(float)
        return x.reshape(-1,channels).mean(axis=1),sr
    if fmt!=1:raise ValueError('unsupported WAV encoding')
    if width==2: x=np.frombuffer(raw,dtype='<i2').astype(float)/32768
    elif width==3:
        a=np.frombuffer(raw,dtype=np.uint8).reshape(-1,3).astype(np.int32)
        v=a[:,0]|(a[:,1]<<8)|(a[:,2]<<16);v=np.where(v&0x800000,v-0x1000000,v)
        x=v.astype(float)/8388608
    elif width==4:x=np.frombuffer(raw,dtype='<i4').astype(float)/2147483648
    elif width==1:x=(np.frombuffer(raw,dtype=np.uint8).astype(float)-128)/128
    else:raise ValueError('unsupported PCM width')
    return x.reshape(-1,channels).mean(axis=1),sr


def prepare(downloads, output):
    output.mkdir(parents=True,exist_ok=True)
    kit=ET.Element('drumkit_info')
    for k,v in {'name':KIT,'author':'Frequency 303 / Allan Legemaate; Studio edits',
                'license':'CC0-1.0 — https://www.frequency303.com/samples/',
                'info':'MS-20, TX81Z and SK-5. Trimmed, filtered, level matched for Orchid Studio.'}.items():ET.SubElement(kit,k).text=v
    instruments=ET.SubElement(kit,'instrumentList');manifest=[]
    for index,(name,pack,member,duration,hp,lp,peak,pan) in enumerate(SAMPLES):
        with zipfile.ZipFile(downloads/(pack+'.zip')) as archive:
            if pack.startswith('TX81Z'):member=pack+'/'+member
            raw=archive.read(member)
        x,sr=decode(raw)
        # Trim silence, retain a tiny attack lead, remove DC and gently roll off extremes.
        x-=np.mean(x)
        active=np.flatnonzero(np.abs(x)>max(np.max(np.abs(x))*.002,1e-6))
        if not len(active):raise ValueError('silent source '+name)
        x=x[max(0,active[0]-int(sr*.0003)):active[-1]+1][:int(sr*duration)]
        n=1<<(len(x)*2-1).bit_length();f=np.fft.rfftfreq(n,1/sr)
        response=(1/(1+(f/lp)**6))*(1/(1+(hp/np.maximum(f,1))**6));response[0]=0
        x=np.fft.irfft(np.fft.rfft(x,n)*response,n)[:len(x)]
        fade=min(int(sr*.020),len(x)//3);x[-fade:]*=np.linspace(1,0,fade)**2
        attack=max(2,int(sr*.0003));x[:attack]*=np.linspace(0,1,attack)
        x*=peak/max(np.max(np.abs(x)),1e-9)
        if sr!=44100:x=np.interp(np.arange(round(len(x)*44100/sr))*sr/44100,np.arange(len(x)),x)
        filename=name.lower().replace(' ','-')+'.wav'
        with wave.open(str(output/filename),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes((x*32767).astype('<i2').tobytes())
        ins=ET.SubElement(instruments,'instrument')
        for k,v in {'id':index,'name':name,'volume':1,'pan':pan,'muteGroup':1 if 'Hat' in name else -1,
                    'filename':filename,'midiOutChannel':-1}.items():ET.SubElement(ins,k).text=str(v)
        manifest.append({'name':name,'source_pack':pack,'source_member':member,
                         'source_sha256':hashlib.sha256(raw).hexdigest(),'filename':filename,
                         'duration':len(x)/44100,'peak':float(np.max(np.abs(x))),
                         'rms':float(np.sqrt(np.mean(x*x))),'highpass_hz':hp,'lowpass_hz':lp})
    ET.indent(kit);ET.ElementTree(kit).write(output/'drumkit.xml',encoding='utf-8',xml_declaration=True)
    (output/'provenance.json').write_text(json.dumps(manifest,indent=2))
    (output/'LICENSE.txt').write_text('Source audio: Frequency 303 / Allan Legemaate. CC0-1.0.\nhttps://www.frequency303.com/samples/\nStudio edits: silence trim, gentle band limiting, tail fade, level matching, mono conversion.\n')
    print(json.dumps({'kit':str(output),'sounds':len(manifest),'seconds':sum(m['duration'] for m in manifest)},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--downloads',type=Path,default=ROOT/'drum-downloads');p.add_argument('--output',type=Path,default=ROOT/'drum-downloads/OrchidCircuitry')
    args=p.parse_args();prepare(args.downloads,args.output)
