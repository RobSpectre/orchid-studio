"""Original 12-bar indietronica arrangements for the optional CC0 Circuitry kit.

No sampled songs or transcribed artist patterns. Stable IDs preserve selections.
Legacy Hydrogen/808 exports remain in beats.py; these are native Studio documents.
"""
from .beats import catalog

KIT_ID = 'orchid-circuitry'
BANK_NAME = 'Orchid Studio — Circuitry Vol. 2'
# Per groove: tempo, swing, feel, six sounds, four kick bars, two snare bars,
# two 16-step hat masks, two percussion responses. Steps are sixteenths.
SPECS = [
 (160,.04,'soft liquid breaks',
  ('FM Compressed Kick','FM Short Snare','Analog Dust Hat','FM Air Shaker','FM Soft Click','Analog Open Hat'),
  ((0,7,10),(0,6,11,14),(0,7,10,15),(0,6,10)),((4,12),(4,12)),
  ('x.x.x.x.x.x.x.x.','x.x..xx.x.x.x..x'),((3,11),(7,14))),
 (148,.08,'cut-up pocket breaks',
  ('Analog Punch Kick','Pocket Snare','FM Fine Hat','FM Sand Shaker','FM Noise Tick','Analog Air Clap'),
  ((0,6,10),(0,3,10,14),(0,7,11),(0,6,9,14)),((4,12),(4,11,12)),
  ('x..xx.x...x.x.x.','x.x...x.x..xx.x.'),((2,9),(6,15))),
 (108,.14,'shuffled two-step',
  ('FM Soft Kick','FM Low Snare','Pocket Hat','FM Air Shaker','FM Soft Click','Analog Soft Clap'),
  ((0,7),(0,10,14),(0,6,11),(0,7,14)),((4,12),(4,12)),
  ('..x...x...x...x.','..x..xx...x..xx.'),((1,10),(3,9))),
 (84,.02,'spacious half-time',
  ('Analog Pillow Kick','Analog Paper Snare','FM Low Hat','FM Sand Shaker','FM Noise Tick','Analog Air Clap'),
  ((0,6),(0,11),(0,3,14),(0,6,10)),((8,),(8,)),
  ('x...x.x...x...x.','x.x...x...x.x..x'),((5,13),(3,15))),
 (116,.16,'warm brushed micro-house',
  ('Analog Round Kick','Analog Soft Clap','Analog Silk Hat','FM Sand Shaker','FM Soft Click','Analog Open Hat'),
  ((0,4,8,12),(0,4,8,12),(0,4,8,12,15),(0,4,8,12)),((4,12),(4,12)),
  ('..x...x...x...x.','..x..xx...x..xx.'),((3,10),(7,14))),
 (124,.04,'bright clipped house',
  ('FM Compressed Kick','Analog Air Clap','FM Fine Hat','FM Air Shaker','FM Noise Tick','Analog Open Hat'),
  ((0,4,8,12),(0,4,8,12),(0,4,8,11,12),(0,4,8,12)),((4,12),(4,12)),
  ('x.x.x.x.x.x.x.x.','..x.x.x...x.x.x.'),((1,9),(5,13))),
 (102,.12,'broken late-night house',
  ('Pocket Kick','FM Low Snare','Analog Dust Hat','FM Sand Shaker','FM Soft Click','Analog Soft Clap'),
  ((0,6,8),(0,4,11),(0,6,12),(0,7,8,14)),((4,12),(4,12)),
  ('..x.x...x.x...x.','x.x...x...x..xx.'),((7,15),(3,10))),
 (128,.02,'dry motorik pulse',
  ('Analog Punch Kick','FM Short Snare','Pocket Hat','FM Air Shaker','FM Noise Tick','Analog Air Clap'),
  ((0,4,8,12),(0,4,8,12),(0,4,8,12),(0,4,8,14)),((4,12),(4,12)),
  ('x.x.x.x.x.x.x.x.','x.x.x.x.x.x.x...'),((6,14),(2,10))),
 (120,0,'airy synth-pop drive',
  ('Analog Pillow Kick','FM Bright Snare','Analog Silk Hat','FM Air Shaker','FM Soft Click','Analog Open Hat'),
  ((0,8,10),(0,6,8),(0,8,11),(0,6,10,14)),((4,12),(4,12)),
  ('x.x.x.x.x.x.x.x.','x.x...x.x.x...x.'),((7,15),(3,11))),
 (132,.03,'sparkling trance-pop',
  ('FM Soft Kick','Analog Soft Clap','Pocket Hat','FM Sand Shaker','FM Soft Click','Analog Soft Clap'),
  ((0,4,8,12),(0,4,8,12),(0,4,8,12),(0,4,8,12,15)),((4,12),(4,12)),
  ('..x...x...x...x.','x.x...x...x...x.'),((3,9),(7,13))),
 (136,0,'interlocking electro pulse',
  ('Analog Round Kick','FM Short Snare','FM Low Hat','FM Air Shaker','FM Soft Click','Analog Soft Clap'),
  ((0,4,8,12),(0,4,8,12),(0,6,8,12),(0,4,10,12)),((4,12),(4,12)),
  ('x..x..x.x..x..x.','..x.x...x.x...x.'),((1,7),(5,11))),
 (140,.02,'buoyant electronic finale',
  ('FM Compressed Kick','Analog Paper Snare','Analog Dust Hat','FM Sand Shaker','FM Noise Tick','Analog Air Clap'),
  ((0,4,8,12),(0,4,7,8,12),(0,4,8,12),(0,4,8,10,14)),((4,12),(4,12)),
  ('x.x..xx.x.x..xx.','x.x.x.x.x.x.x.x.'),((3,11),(7,15))),
]


def sound_id(name):
    return KIT_ID+'-'+name.lower().replace(' ','-')


def documents():
    result={}
    for index,(entry,spec) in enumerate(zip(catalog(),SPECS)):
        bpm,swing,feel,sounds,kicks,snares,hats,percs=spec
        roles=('kick','snare','hat','shaker','click','air')
        gains=(1,.82,.75,.45,.36,.55)
        lanes=[{'id':role,'name':sound,'sound':sound_id(sound),'gain':gain,'muted':False}
               for role,sound,gain in zip(roles,sounds,gains)]
        hits={}
        def add(role,bar,step,velocity):
            beat=bar*4+step/4
            hits[(role,beat)]={'lane':role,'beat':beat,'velocity':round(velocity,3),'probability':1}
        for bar in range(12):
            # Three four-bar phrases: establish, develop, breathe and return.
            section=bar//4;part=bar%4;thin=bar==8
            for step in kicks[part]:
                if thin and step not in (0,8):continue
                add('kick',bar,step,.82 if step==0 else .73 if step%4==0 else .59)
            for step in snares[bar%2]:
                add('snare',bar,step,.67 if step in (4,8,12) else .27)
            mask=hats[(bar+section)%2]
            for step,char in enumerate(mask):
                if char!='x' or (thin and step%4) or (bar==0 and step%2):continue
                add('hat',bar,step,(.46,.22,.35,.25)[step%4]*(.84 if bar==0 else 1))
            # Shakers answer the main hat instead of an uninterrupted loud 16th stream.
            if section>=1 and not thin:
                for step in ((1,5,9,13) if index%2 else (3,7,11,15)):
                    if part==0 and step>8:continue
                    add('shaker',bar,step,.31 if step%8<4 else .23)
            if bar not in (0,8):
                for step in percs[bar%2]:add('click',bar,step,.25 if section==1 else .19)
            # Air at phrase responses, not on every offbeat.
            if bar in (2,5,6,9,10):
                for step in ((6,14) if 'Hat' in sounds[5] else (12,)):
                    add('air',bar,step,.28 if 'Hat' in sounds[5] else .22)
            # Quiet, different turnarounds every four bars; no rapid ratchet bursts.
            if part==3:
                fill=((10,15),(11,14),(13,15))[(section+index)%3]
                for step in fill:
                    if step not in snares[bar%2]:add('snare',bar,step,.20 if step==fill[0] else .28)
                add('click',bar,14 if index%2 else 15,.24)
                if section==2:
                    # Leave the last eighth free of hats for a clean loop downbeat.
                    for role in ('hat','shaker','air'):
                        for step in (14,15):hits.pop((role,bar*4+step/4),None)
            elif section==1 and part in (1,2):
                ghost=(7,11,3,15)[index%4]
                if ghost not in snares[bar%2]:add('snare',bar,ghost,.17)
        if entry['id']=='prism-lift':
            # Listening revision: use the approved soft kit, no layered air/clap.
            hits={key:h for key,h in hits.items() if h['lane']!='air'}
            for lane in lanes:
                if lane['id']=='hat':lane['gain']=.50
                if lane['id']=='shaker':lane['gain']=.32
        d={'kind':'orchid-beat','version':1,'id':entry['id'],'name':entry['name'],
           'bars':12,'suggested_bpm':bpm,'genre':('indie breaks' if index<4 else 'micro-house' if index<8 else 'electro-pop'),
           'feel':feel,'bank':BANK_NAME,'kit':'Orchid Circuitry · MS-20 / TX81Z / SK-5',
           'swing':swing,'lanes':lanes,'hits':sorted(hits.values(),key=lambda h:(h['beat'],h['lane']))}
        result[d['id']]=d
    return result
