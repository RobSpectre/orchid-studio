"""Twelve original 12-bar electronic grooves; optional installed sample rack.

Beat documents reference existing licensed samples; no audio assets are bundled.
"""
from .indie_beats import sound_id

BANK = 'Orchid Studio — Many Rooms'

def spec(id,name,bpm,genre,feel,energy,density,best_for,sounds,kick,snare,hat,perc,swing=0,breaks=(),fills=(),tags=()):
    return dict(id=id,name=name,bpm=bpm,genre=genre,feel=feel,energy=energy,density=density,best_for=best_for,
                sounds=sounds,kick=kick,snare=snare,hat=hat,perc=perc,swing=swing,breaks=breaks,fills=fills,tags=tags)

# Patterns contain sixteenth-note positions in each of four bars. Fractional
# positions deliberately place triplets in Paper Comet. Each bank has its own
# drum skeleton; tempo is not what distinguishes these arrangements.
SPECS = [
 spec('still-water','Still Water',68,'ambient pulse','A soft heartbeat surrounded by long silences; tiny clicks mark the horizon.','low','sparse','Sustained pads, sparse robot melodies and slow introductions',
 ('Analog Pillow Kick','Analog Soft Clap','FM Low Hat','FM Soft Click'),
 ((0,),(),(0,10),()),((),(8,),(),(8,)),((2,10),(),(6,),()),((),(14,),(),(6,)),breaks=(5,9),tags=('ambient','minimal','spacious')),
 spec('amber-tape','Amber Tape',82,'electronic hip-hop','A lazy, swung pocket with low snares and short, dusty hats.','low','medium','Warm electric piano, intimate hooks and unhurried bass riffs',
 ('Pocket Kick','FM Low Snare','Analog Dust Hat','FM Noise Tick'),
 ((0,7,10),(0,6,14),(0,7,11),(0,10,15)),((4,12),(4,12),(4,12),(4,12)),
 ((0,2,6,8,10,14),(0,2,6,10,12,14),(0,6,8,10,14),(2,6,8,10,14)),((3,),(11,),(),(15,)),.19,breaks=(7,),fills=((11,14),),tags=('dusty','swung','hip-hop')),
 spec('black-velvet','Black Velvet',92,'trip-hop','A heavy half-time backbeat with sparse kicks and a slow, shadowy sway.','low','sparse','Moody chord beds, breathy lead sounds and lots of negative space',
 ('Analog Punch Kick','Analog Paper Snare','FM Low Hat','FM Soft Click'),
 ((0,6),(0,14),(0,3,11),(0,6)),((8,),(8,),(8,),(8,)),
 ((2,10),(6,14),(2,6,10),(2,14)),((),(5,),(),(13,)),.06,breaks=(6,),fills=((7,15),),tags=('dark','half-time','cinematic')),
 spec('dub-lantern','Dub Lantern',118,'dub techno','A restrained four-on-the-floor pulse with widely spaced, dotted click answers.','medium','sparse','Long evolving chords, dub-style synth echoes and minimal arrangements',
 ('Analog Round Kick','Analog Soft Clap','Pocket Hat','FM Soft Click'),
 ((0,4,8,12),)*4,((12,),(4,),(12,),(4,12)),((2,10),(6,14),(2,10),(6,)),
 ((3,9,15),(5,11),(1,7,13),(3,9)),.04,breaks=(7,),tags=('dub','hypnotic','minimal','four-on-floor')),
 spec('peach-district','Peach District',122,'disco house','A warm dance-floor bounce with steady kicks, a soft clap and answering pocket hats.','medium','medium','Bright piano chords, playful bass and buoyant chorus hooks',
 ('Analog Round Kick','Analog Soft Clap','Analog Silk Hat','FM Sand Shaker'),
 ((0,4,8,12),(0,4,8,12,15),(0,4,8,12),(0,4,8,11,12)),((4,12),)*4,
 ((2,6,10,14),(2,6,10,14),(2,5,6,10,14),(2,6,10,14)),((1,9),(3,11),(1,9),(7,15)),.12,breaks=(8,),fills=((3,15),(11,14)),tags=('warm','uplifting','house','four-on-floor')),
 spec('blue-platform','Blue Platform',132,'UK garage','A loping two-step kick pattern with swung offbeats and dry, clipped snare responses.','medium','medium','Syncopated bass, vocal-style leads and nimble chord stabs',
 ('FM Soft Kick','Pocket Snare','Pocket Hat','FM Noise Tick'),
 ((0,7,10),(0,6,14),(0,7,11),(0,10)),((4,12),)*4,
 ((2,6,11,14),(2,5,10,14),(2,6,10,13),(2,6,10,14)),((3,9),(7,15),(1,11),(5,13)),.23,breaks=(4,),fills=((7,15),(11,10)),tags=('garage','swung','two-step','bouncy')),
 spec('broken-compass','Broken Compass',112,'broken beat','Interlocking 3–3–2 accents, displaced snares and uneven spaces that resolve every four bars.','medium','medium','Angular bass motifs and call-and-response melodies',
 ('Analog Punch Kick','FM Short Snare','FM Fine Hat','FM Soft Click'),
 ((0,6,12),(0,7,10),(0,6,11),(0,8,14)),((3,10),(4,11),(3,12),(4,12)),
 ((2,5,8,14),(2,6,9,14),(2,5,10,14),(2,6,10)),((1,9),(5,13),(7,15),(3,11)),.05,breaks=(9,),fills=((3,15),),tags=('broken','syncopated','3-3-2')),
 spec('chrome-messenger','Chrome Messenger',126,'electro','A dry drum-machine conversation: kick syncopation, handclap backbeats and precise ticks.','medium','medium','Sequenced bass lines, robotic leads and clipped analog chords',
 ('electricempirekit-kick-low-1','tr808emulationkit-clap','FM Low Hat','electricempirekit-click'),
 ((0,6,10),(0,3,8,14),(0,6,11),(0,8,10,15)),((4,12),)*4,
 ((0,2,6,8,10,14),(2,6,8,10,14),(0,2,6,10,14),(2,6,10,14)),((3,11),(7,15),(1,9),(5,13)),0,breaks=(6,),fills=((11,14),),tags=('electro','robotic','dry')),
 spec('cloud-chaser','Cloud Chaser',170,'liquid drum and bass','A rolling break with a firm snare backbeat, restrained ghost notes and soft, fast hats.','high','busy','Wide pads, flowing bass and spacious melodies over a fast rhythm',
 ('FM Compressed Kick','FM Short Snare','Analog Dust Hat','FM Sand Shaker'),
 ((0,6),(0,10,14),(0,7,10),(0,6,15)),((4,12),)*4,
 ((0,2,4,6,8,10,12,14),(0,2,6,8,10,14),(0,2,4,6,8,10,12,14),(0,2,6,8,10,14)),
 ((3,11),(7,15),(1,9),(3,13)),.025,breaks=(8,),fills=((3,11),(7,15),(11,10)),tags=('liquid','dnb','rolling','fast')),
 spec('velvet-gravity','Velvet Gravity',140,'half-time bass','A broad half-time snare with deep kicks and isolated hat responses; weight without a busy top end.','medium','sparse','Sub-heavy riffs and a strong lead that needs room to breathe',
 ('electricempirekit-kick-low-2','Analog Paper Snare','FM Low Hat','FM Soft Click'),
 ((0,6),(0,3,14),(0,11),(0,6,15)),((8,),)*4,
 ((2,10),(6,14),(2,14),(6,10)),((13,),(),(5,),()),.02,breaks=(7,),fills=((11,14),),tags=('half-time','bass','spacious','heavy')),
 spec('horizon-engine','Horizon Engine',138,'progressive trance','A forward four-on-the-floor drive, soft offbeat hats and a measured lift across three phrases.','high','medium','Long arpeggios, suspended chords and gradual melodic builds',
 ('FM Compressed Kick','Analog Soft Clap','Pocket Hat','FM Air Shaker'),
 ((0,4,8,12),)*4,((4,12),)*4,
 ((2,6,10,14),)*4,((1,9),(1,5,9,13),(3,11),(1,5,9,13)),0,breaks=(7,),fills=((11,14),),tags=('trance','driving','uplifting','four-on-floor')),
 spec('paper-comet','Paper Comet',154,'footwork','Restless kick/clap exchanges and brief triplet hat answers; compact bursts separated by air.','high','busy','Short chopped hooks, playful bass phrases and rhythmic experiments',
 ('Pocket Kick','Analog Soft Clap','FM Fine Hat','FM Noise Tick'),
 ((0,6,10,14),(0,3,8,11),(0,6,12),(0,7,10,15)),((4,10),(4,12),(6,12),(4,10,14)),
 ((0,4/3,8/3,8,10),(2,6,10,14),(0,2,8,28/3,32/3),(2,6,12,14)),
 ((7,15),(5,13),(3,11),(1,9)),0,breaks=(5,),fills=((11,15),),tags=('footwork','juke','triplets','playful')),
]


def documents():
    result={}
    for spec in SPECS:
        roles=('kick','snare','hat','perc')
        gains=(.95,.66,.38,.24)
        lanes=[dict(id=role,name=name,sound=name if name.startswith(('electricempirekit-','tr808emulationkit-')) else sound_id(name),gain=gain,muted=False)
               for role,name,gain in zip(roles,spec['sounds'],gains)]
        hits={}
        def add(role,bar,step,velocity):
            beat=round(bar*4+step/4,6)
            hits[(role,beat)]=dict(lane=role,beat=beat,velocity=round(velocity,3),probability=1)
        for bar in range(12):
            part=bar%4;phrase=bar//4
            for role in roles:
                for i,step in enumerate(spec[role][part]):
                    # Each arrangement has its own breathing bars. The opening
                    # phrase introduces the core; response percussion enters later.
                    if role=='perc' and phrase==0:continue
                    if bar in spec['breaks'] and (role in ('hat','perc') or (role=='kick' and step!=0)):continue
                    velocity={'kick':.82 if step==0 else .69,'snare':.66,'hat':.36 if i%2==0 else .24,'perc':.25}[role]
                    if role=='hat' and phrase==0:velocity*=.82
                    add(role,bar,step,velocity)
            if phrase==2 and spec['energy']=='high' and bar not in spec['breaks']:
                # One short response per final-phrase bar, never a cymbal wash.
                add('perc',bar,7,.22)
        for bar,step in spec['fills']:
            if ('snare',bar*4+step/4) not in hits:add('snare',bar,step,.25)
        # Clear the very last sixteenth of upper percussion for the loop reset.
        hits={k:h for k,h in hits.items() if not (h['lane'] in ('hat','perc') and h['beat']>=47.75)}
        arrangement='Bars 1–4 establish the core; 5–8 add quiet responses; 9–12 return with a small variation. Breathing bars: '+', '.join(str(x+1) for x in spec['breaks'])+'.'
        result[spec['id']]=dict(kind='orchid-beat',version=1,id=spec['id'],name=spec['name'],bars=12,
            suggested_bpm=spec['bpm'],genre=spec['genre'],feel=spec['feel'],vibe=spec['feel'],
            tags=list(spec['tags']),energy=spec['energy'],density=spec['density'],best_for=spec['best_for'],
            arrangement=arrangement,bank=BANK,kit='Mixed electronic rack · Circuitry / 808 / Electric Empire',
            swing=spec['swing'],lanes=lanes,hits=sorted(hits.values(),key=lambda h:(h['beat'],h['lane'])))
    return result
