"""Read bounded, monophonic Standard MIDI Files as clock-relative Perform phrases.

Only notes and tempo metadata are imported. No controller, SysEx or program
messages from a file are ever forwarded to a device.
"""
import math
import struct


def read_phrase(data):
    if len(data)>1024*1024 or data[:4]!=b'MThd' or len(data)<14:
        raise ValueError('Expected a MIDI file of at most 1 MiB')
    size=struct.unpack('>I',data[4:8])[0]
    fmt,count,ppqn=struct.unpack('>HHH',data[8:14])
    if size<6 or fmt not in (0,1) or not count or ppqn==0 or ppqn&0x8000:
        raise ValueError('Only synchronous MIDI format 0/1 with PPQN timing is supported')
    pos=8+size; notes=[]; tempos=[]; end=0
    for track in range(count):
        if data[pos:pos+4]!=b'MTrk' or pos+8>len(data):raise ValueError('Missing MIDI track')
        length=int.from_bytes(data[pos+4:pos+8],'big');pos+=8
        raw=data[pos:pos+length];pos+=length
        if len(raw)!=length:raise ValueError('Truncated MIDI track')
        i=0;tick=0;running=None;active={}
        def byte():
            nonlocal i
            if i>=len(raw):raise ValueError('Truncated MIDI event')
            value=raw[i];i+=1;return value
        def vlq():
            value=0
            for _ in range(4):
                b=byte();value=(value<<7)|(b&127)
                if b<128:return value
            raise ValueError('Invalid MIDI variable-length integer')
        while i<len(raw):
            tick+=vlq();status=byte()
            if status<128:
                if running is None:raise ValueError('Invalid MIDI running status')
                i-=1;status=running
            if status==255:
                running=None;kind=byte();n=vlq()
                if i+n>len(raw):raise ValueError('Truncated MIDI metadata')
                payload=raw[i:i+n];i+=n
                if kind==81 and n==3 and int.from_bytes(payload,'big'):
                    tempos.append((tick,60000000/int.from_bytes(payload,'big')))
                if kind==47:break
            elif status in (240,247):
                running=None;n=vlq();i+=n
                if i>len(raw):raise ValueError('Truncated MIDI SysEx')
            elif 128<=status<=239:
                running=status;kind=status>>4;channel=status&15
                values=[byte() for _ in range(1 if kind in (12,13) else 2)]
                if any(v>127 for v in values):raise ValueError('Invalid MIDI data byte')
                if kind not in (8,9):continue
                note,velocity=values;key=(channel,note)
                if kind==9 and velocity:
                    if channel==9:raise ValueError('Select a pitched melody without percussion')
                    if key in active:raise ValueError('Overlapping repeated MIDI note')
                    active[key]=(tick,velocity)
                elif key in active:
                    start,v=active.pop(key)
                    if tick>start:notes.append((start/ppqn,note,(tick-start)/ppqn,v))
            else:raise ValueError('Unsupported MIDI event')
        if active:raise ValueError('MIDI phrase has unterminated notes')
        end=max(end,tick/ppqn)
    notes.sort()
    if not notes or len(notes)>4096:raise ValueError('Expected 1–4096 melody notes')
    if any(a[0]+a[2]>b[0]+1e-8 for a,b in zip(notes,notes[1:])):
        raise ValueError('Choose a single monophonic melody track before importing')
    end=max(end,max(n[0]+n[2] for n in notes))
    if end>256:raise ValueError('Choose a phrase no longer than 64 bars')
    # Preserve every supplied onset and duration. Trailing silence makes an
    # integer number of 4/4 bars, so short motifs align with Studio's loops.
    beats=math.ceil(end/4)*4
    return {'notes':notes,'source_beats':end,'loop_beats':beats,
            'suggested_bpm':round(sorted(tempos)[0][1],2) if tempos else 120}
