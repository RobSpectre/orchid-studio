"""Editable beat documents and a local, mixed Hydrogen sound rack.

Samples stay local, with source author/license metadata. No hardware MIDI output.
"""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
import wave
import xml.etree.ElementTree as ET

from .beats import catalog, patterns
from .sequencer import integer, number

from .paths import data_dir

ROOT = data_dir() / 'drums'


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')[:64] or 'untitled'


def xml(path):
    root = ET.parse(path).getroot()
    for n in root.iter():
        n.tag = n.tag.split('}')[-1]
    return root


def put(node, key, value):
    child = node.find(key)
    if child is None:
        child = ET.SubElement(node, key)
    child.text = str(value)


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(data)
    temporary.replace(path)


def validate(document, sounds=None):
    if not isinstance(document, dict) or document.get('kind') != 'orchid-beat' or document.get('version') != 1:
        raise ValueError('expected an orchid-beat version 1 document')
    d = copy.deepcopy(document)
    for key in ('id', 'name'):
        if not isinstance(d.get(key), str) or not d[key].strip() or len(d[key]) > 100:
            raise ValueError(f'beat {key} must be 1–100 characters')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', d['id']):
        raise ValueError('beat id must be lowercase letters, digits and hyphens')
    integer(d.get('bars'), 1, 64, 'bars')
    d['suggested_bpm'] = number(d.get('suggested_bpm', 124), 30, 300, 'suggested_bpm')
    d['swing'] = number(d.get('swing', 0), 0, .45, 'swing')
    for key in ('vibe','best_for','arrangement'):
        if key in d and (not isinstance(d[key],str) or len(d[key])>1200):
            raise ValueError(f'{key} must be text up to 1200 characters')
    for key,choices in (('energy',('low','medium','high')),('density',('sparse','medium','busy'))):
        if key in d and d[key] not in choices:raise ValueError(f'invalid {key}')
    if 'tags' in d and (not isinstance(d['tags'],list) or len(d['tags'])>16 or
                       any(not isinstance(tag,str) or not 1<=len(tag)<=64 for tag in d['tags'])):
        raise ValueError('tags must be at most 16 short strings')
    lanes = d.get('lanes')
    if not isinstance(lanes, list) or not 1 <= len(lanes) <= 32:
        raise ValueError('a beat needs 1–32 lanes')
    ids = set()
    for lane in lanes:
        if not isinstance(lane, dict) or not isinstance(lane.get('id'), str) or not re.fullmatch(r'[a-z0-9-]{1,64}', lane['id']) or lane['id'] in ids:
            raise ValueError('lane IDs must be unique lowercase letters, digits or hyphens')
        ids.add(lane['id'])
        if not isinstance(lane.get('name'), str) or not 1 <= len(lane['name']) <= 100:
            raise ValueError('lane needs a short name')
        if not isinstance(lane.get('sound'), str) or (sounds is not None and lane['sound'] not in sounds):
            raise ValueError('lane sound is missing; import the required kit first')
        lane['gain'] = number(lane.get('gain', 1), 0, 1.5, 'lane gain')
        lane['muted'] = lane.get('muted', False)
        if type(lane['muted']) is not bool:
            raise ValueError('lane muted must be boolean')
    if not isinstance(d.get('hits'), list) or len(d['hits']) > 8192:
        raise ValueError('hits must be an array of at most 8192 hits')
    seen = set()
    for hit in d['hits']:
        if not isinstance(hit, dict) or hit.get('lane') not in ids:
            raise ValueError('hit must reference a lane')
        beat = number(hit.get('beat'), 0, d['bars'] * 4, 'hit beat')
        if beat >= d['bars'] * 4:
            raise ValueError('hit must start before the end of the beat')
        key = (hit['lane'], beat)
        if key in seen:
            raise ValueError('duplicate hit in the same lane and position')
        seen.add(key)
        hit['velocity'] = number(hit.get('velocity', .6), .01, 1, 'velocity')
        hit['probability'] = number(hit.get('probability', 1), 0, 1, 'probability')
    d['hits'].sort(key=lambda h: (h['beat'], h['lane']))
    return d


def builtin_documents():
    result = {}
    for entry, pattern in zip(catalog(), patterns()):
        voices = sorted({n['instrument'] for n in pattern['notes']})
        d = {'kind':'orchid-beat', 'version':1, 'id':entry['id'], 'name':entry['name'],
             'bars':12, 'suggested_bpm':entry['suggested_bpm'], 'genre':entry['genre'], 'swing':0,
             'lanes':[{'id':slug(v), 'name':v, 'sound':'tr808emulationkit-' + slug(v), 'gain':1, 'muted':False} for v in voices],
             'hits':[{'lane':slug(n['instrument']), 'beat':n['position']/48, 'velocity':n['velocity'], 'probability':1} for n in pattern['notes']]}
        result[d['id']] = d
    return result


class DrumLibrary:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else data_dir() / 'drums'
        self.documents = builtin_documents()
        self.sounds = {}
        self.kits = []
        manifest = self.root / 'sounds.json'
        if manifest.is_file():
            data = json.loads(manifest.read_text())
            self.sounds, self.kits = data['sounds'], data['kits']
        # Upgrade factory arrangements only when the optional sound pack is present.
        # Saved user edits below always win over these defaults.
        from .indie_beats import documents
        upgraded = documents()
        required = {lane['sound'] for d in upgraded.values() for lane in d['lanes']}
        if required <= self.sounds.keys():
            self.documents.update(upgraded)
        from .vibe_beats import documents as vibe_documents
        for identifier,document in vibe_documents().items():
            if {lane['sound'] for lane in document['lanes']} <= self.sounds.keys():
                self.documents[identifier]=document
        for path in sorted((self.root / 'beats').glob('*.json')):
            d = validate(json.loads(path.read_text()))
            self.documents[d['id']] = d

    def catalog(self):
        return [{'id':d['id'], 'name':d['name'], 'bars':d['bars'], 'length_beats':4*d['bars'],
                 'pattern':i, 'genre':d.get('genre','custom'), 'suggested_bpm':d['suggested_bpm'],
                 'feel':d.get('feel','Editable Studio arrangement'), 'kit':d.get('kit','Mixed sound rack'),
                 'bank':d.get('bank','Custom'), 'vibe':d.get('vibe',d.get('feel','Editable Studio arrangement')),
                 'tags':copy.deepcopy(d.get('tags',[])), 'energy':d.get('energy'), 'density':d.get('density'),
                 'best_for':d.get('best_for',''), 'arrangement':d.get('arrangement','')}
                for i,d in enumerate(self.documents.values())]

    def get(self, identifier):
        if identifier not in self.documents:
            raise ValueError('unknown beat; use beats-list')
        return copy.deepcopy(self.documents[identifier])

    def save(self, document):
        d = validate(document, self.sounds)
        atomic(self.root / 'beats' / (d['id']+'.json'), json.dumps(d, indent=2))
        self.documents[d['id']] = d
        return copy.deepcopy(d)

    def persist(self):
        atomic(self.root/'sounds.json', json.dumps({'sounds':self.sounds, 'kits':self.kits}, indent=2))

    def local_sample(self, path):
        path=Path(path)
        if path.stat().st_size>32*1024*1024:
            raise ValueError('each sample must be under 32 MB')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        target=self.root/'assets'/(digest+path.suffix.lower())
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copyfile(path,target)
        return str(target.resolve())

    def materialize(self):
        # Copy only the chosen audio assets, retaining source/license metadata.
        updated=copy.deepcopy(self.sounds)
        for sound in updated.values():
            instrument=ET.fromstring(sound['instrument'])
            for f in instrument.iter('filename'):
                f.text=self.local_sample(f.text)
            sound['instrument']=ET.tostring(instrument,encoding='unicode')
        self.sounds=updated
        self.persist()

    def import_kit(self, path):
        path = Path(path).expanduser().resolve()
        if path.is_file() and path.suffix == '.h2drumkit':
            # Extract only bounded regular files. Never follow archive links or paths outside the destination.
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            target = self.root/'imports'/digest
            with tarfile.open(path) as archive:
                members = archive.getmembers()
                if len(members)>4096 or sum(m.size for m in members)>128*1024*1024:
                    raise ValueError('kit archive exceeds 128 MB / 4096 files')
                for m in members:
                    destination = (target/m.name).resolve()
                    if not destination.is_relative_to(target.resolve()) or not (m.isfile() or m.isdir()):
                        raise ValueError('unsafe kit archive path or link')
                for m in members:
                    if m.isfile():
                        destination=target/m.name
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        with archive.extractfile(m) as source:
                            destination.write_bytes(source.read())
            matches = list(target.rglob('drumkit.xml'))
            if len(matches)!=1:
                raise ValueError('archive must contain one drumkit.xml')
            path=matches[0].parent
        metadata = path/'drumkit.xml' if path.is_dir() else path
        kit=xml(metadata)
        name=kit.findtext('name') or metadata.parent.name
        kit_id=slug(name)
        if any(k['id']==kit_id for k in self.kits):
            return next(k for k in self.kits if k['id']==kit_id)
        additions={}
        for instrument in kit.findall('instrumentList/instrument'):
            instrument=copy.deepcopy(instrument)
            label=instrument.findtext('name') or 'Sound'
            sound_id=kit_id+'-'+slug(label)
            if sound_id in additions:
                sound_id+='-'+str(len(additions))
            for f in instrument.iter('filename'):
                sample=(metadata.parent/(f.text or '')).resolve()
                if not sample.is_relative_to(metadata.parent.resolve()) or not sample.is_file():
                    raise ValueError(f'missing or unsafe sample: {f.text}')
                f.text=self.local_sample(sample)
            if not list(instrument.iter('filename')):
                continue
            additions[sound_id]={'id':sound_id,'name':label,'kit':kit_id,'author':kit.findtext('author') or '',
                                 'license':kit.findtext('license') or 'Unspecified by source',
                                 'instrument':ET.tostring(instrument,encoding='unicode')}
        if not additions:
            raise ValueError('kit has no sample instruments')
        if len(self.sounds)+len(additions)>92:
            raise ValueError('mixed rack supports 92 sounds; import a smaller kit')
        entry={'id':kit_id,'name':name,'author':kit.findtext('author') or '',
               'license':kit.findtext('license') or 'Unspecified by source','sounds':list(additions)}
        self.sounds.update(additions);self.kits.append(entry);self.persist()
        return entry

    def upload(self, name, payload, license_text='User supplied'):
        if not isinstance(name,str) or not name.strip() or len(name)>100:
            raise ValueError('sample needs a name of 1–100 characters')
        if not isinstance(payload,str) or len(payload)>12*1024*1024:
            raise ValueError('WAV upload must be under 8 MB')
        try:
            data=base64.b64decode(payload,validate=True)
            with wave.open(io.BytesIO(data)) as audio:
                if audio.getnchannels() not in (1,2) or audio.getsampwidth() not in (1,2,3,4) or audio.getnframes()/audio.getframerate()>30:
                    raise ValueError('use a mono/stereo PCM WAV under 30 seconds')
        except (ValueError,wave.Error,EOFError) as exc:
            raise ValueError('use a valid mono/stereo PCM WAV under 30 seconds') from exc
        if len(data)>8*1024*1024:
            raise ValueError('WAV upload must be under 8 MB')
        folder=self.root/'samples'/(slug(name)+'-'+hashlib.sha256(data).hexdigest()[:10])
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'sample.wav').write_bytes(data)
        kit=ET.Element('drumkit_info');put(kit,'name',folder.name);put(kit,'license',str(license_text)[:500])
        ins=ET.SubElement(ET.SubElement(kit,'instrumentList'),'instrument')
        put(ins,'id',0);put(ins,'name',name);put(ins,'volume',.8)
        component=ET.SubElement(ins,'instrumentComponent');put(component,'component_id',0);put(component,'gain',1)
        layer=ET.SubElement(component,'layer')
        for k,v in {'filename':'sample.wav','min':0,'max':1,'gain':1,'pitch':0}.items():put(layer,k,v)
        ET.ElementTree(kit).write(folder/'drumkit.xml')
        return self.import_kit(folder)

    def ensure_stock(self):
        if any(k['id']=='tr808emulationkit' for k in self.kits):return
        candidates=[Path('/Applications/Hydrogen.app/Contents/Resources/data/drumkits/TR808EmulationKit'),
                    Path('/usr/share/hydrogen/data/drumkits/TR808EmulationKit')]
        for path in candidates:
            if (path/'drumkit.xml').is_file():
                self.import_kit(path);return
        raise ValueError('import the TR808EmulationKit directory with kits-import first')

    def rack(self):
        self.ensure_stock()
        song=ET.Element('song')
        for k,v in {'version':'1.2.0','name':'Orchid Studio Sound Rack','bpm':124,'volume':.3,
                    'mode':'pattern','loopEnabled':'false','isMuted':'false','humanize_time':0,
                    'humanize_velocity':0,'swing_factor':0,'metronomeVolume':0}.items():put(song,k,v)
        components=ET.SubElement(song,'componentList');component=ET.SubElement(components,'drumkitComponent')
        for k,v in {'id':0,'name':'Main','volume':1}.items():put(component,k,v)
        instruments=ET.SubElement(song,'instrumentList')
        for i,s in enumerate(self.sounds.values()):
            ins=ET.fromstring(s['instrument'])
            # Keep all sounds loaded together. Equal note/index mapping works in both Hydrogen map modes.
            for k,v in {'id':i,'name':s['name'],'midiOutChannel':-1,'midiOutNote':36+i,
                        'isMuted':'false','isSoloed':'false','muteGroup':-1}.items():put(ins,k,v)
            for component in ins.findall('instrumentComponent'):put(component,'component_id',0)
            instruments.append(ins)
        p=ET.SubElement(ET.SubElement(song,'patternList'),'pattern')
        put(p,'name','Studio schedules every hit');put(p,'size',192);put(p,'denominator',4)
        ET.SubElement(p,'noteList');ET.SubElement(song,'patternSequence')
        for tag in ('virtualPatternList','ladspa','BPMTimeLine','tagTimeLine'):ET.SubElement(song,tag)
        path=self.root/'studio-rack.h2song'
        atomic(path,ET.tostring(song,encoding='unicode'))
        return str(path.resolve())

    def sound_list(self):
        return [{k:v for k,v in s.items() if k!='instrument'} for s in self.sounds.values()]
