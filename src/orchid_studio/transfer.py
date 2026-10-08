"""Private, relocatable session/sample bundles. Never includes plugin binaries."""
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from .paths import data_dir

MAX_TOTAL = 512 * 1024 * 1024
MAX_FILES = 4096
AUDIO = {'.wav', '.flac', '.aiff', '.aif', '.ogg'}


def export_bundle(output, document, root=None):
    from .drum_library import DrumLibrary
    from .looper import Looper
    Looper(lambda m: None, lambda e: None).restore(document)
    root = Path(root) if root is not None else data_dir()
    output = Path(output)
    library = DrumLibrary(root / 'drums')
    payload = {'session.json': json.dumps(document, indent=2).encode()}
    sounds = copy.deepcopy(library.sounds)
    for sound in sounds.values():
        instrument = ET.fromstring(sound['instrument'])
        for filename in instrument.iter('filename'):
            sample = Path(filename.text or '')
            if not sample.is_absolute():
                sample = library.root / sample
            if sample.suffix.lower() not in AUDIO or not sample.is_file() or sample.stat().st_size > 32*1024*1024:
                raise ValueError(f'Missing or unsupported sample: {sample}')
            content = sample.read_bytes()
            name = 'assets/' + hashlib.sha256(content).hexdigest() + sample.suffix.lower()
            payload['drums/' + name] = content
            filename.text = name
        sound['instrument'] = ET.tostring(instrument, encoding='unicode')
    payload['drums/sounds.json'] = json.dumps({'sounds': sounds, 'kits': library.kits}, indent=2).encode()
    # Save defaults too so a later release cannot silently change the transferred grooves.
    for identifier, beat in library.documents.items():
        payload[f'drums/beats/{identifier}.json'] = json.dumps(beat, indent=2).encode()
    songs = root / 'perform-midi'
    if (songs / 'songs.json').is_file():
        entries = json.loads((songs / 'songs.json').read_text())
        payload['perform-midi/songs.json'] = json.dumps(entries, indent=2).encode()
        for entry in entries:
            name = entry['file']
            if Path(name).name != name or Path(name).suffix.lower() not in ('.mid', '.midi'):
                raise ValueError('Unsafe song filename')
            payload['perform-midi/' + name] = (songs / name).read_bytes()
    if len(payload) > MAX_FILES or sum(map(len, payload.values())) > MAX_TOTAL:
        raise ValueError('Transfer exceeds 512 MB / 4096 files')
    manifest = {'kind': 'orchid-studio-transfer', 'version': 1,
        'private': True, 'plugin_bundled': False,
        'files': {name: hashlib.sha256(content).hexdigest() for name, content in payload.items()}}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects earlier backups; remove only our incomplete output.
    with output.open('xb') as stream:
        try:
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
                for name, content in payload.items():
                    archive.writestr(name, content)
        except Exception:
            output.unlink(missing_ok=True)
            raise
    return {'status': 'exported', 'path': str(output.resolve()), 'files': len(payload),
            'sounds': len(sounds), 'beats': len(library.documents), 'private': True}


def import_bundle(archive_path, destination):
    """Restore only into a new directory; verify everything before publishing it."""
    from .drum_library import DrumLibrary
    from .looper import Looper
    from .pistil_host import validate_states
    from .song_modes import load_songs
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise ValueError('Restore destination already exists; choose a new data directory.')
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES + 1 or sum(i.file_size for i in entries) > MAX_TOTAL:
            raise ValueError('Transfer exceeds 512 MB / 4096 files')
        names = [i.filename for i in entries]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate archive entries')
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Unsafe archive path or link')
            allowed = entry.filename in ('manifest.json', 'session.json', 'drums/sounds.json', 'perform-midi/songs.json')
            allowed |= len(path.parts) == 3 and path.parts[:2] == ('drums', 'assets') and path.suffix.lower() in AUDIO
            allowed |= len(path.parts) == 3 and path.parts[:2] == ('drums', 'beats') and path.suffix == '.json'
            allowed |= len(path.parts) == 2 and path.parts[0] == 'perform-midi' and path.suffix.lower() in ('.mid', '.midi')
            if not allowed or entry.is_dir():
                raise ValueError('Unexpected transfer file: ' + entry.filename)
        if not {'manifest.json', 'session.json', 'drums/sounds.json'} <= set(names):
            raise ValueError('Incomplete transfer bundle')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('kind') != 'orchid-studio-transfer' or manifest.get('version') != 1:
            raise ValueError('Expected Orchid Studio transfer version 1')
        if set(manifest['files']) != set(names) - {'manifest.json'}:
            raise ValueError('Transfer manifest does not match its files')
        payload = {name: archive.read(name) for name in manifest['files']}
        if any(hashlib.sha256(content).hexdigest() != manifest['files'][name] for name, content in payload.items()):
            raise ValueError('Transfer checksum mismatch')
    document = json.loads(payload['session.json'])
    Looper(lambda m: None, lambda e: None).restore(document)
    if 'instruments' in document:
        validate_states(document['instruments']['states'])
    metadata = json.loads(payload['drums/sounds.json'])
    for sound in metadata['sounds'].values():
        instrument = ET.fromstring(sound['instrument'])
        for filename in instrument.iter('filename'):
            name = filename.text or ''
            parts = PurePosixPath(name).parts
            if len(parts) != 2 or parts[0] != 'assets' or 'drums/' + name not in payload:
                raise ValueError('Sample reference is not bundled')
            filename.text = str(destination / 'drums' / name)
        sound['instrument'] = ET.tostring(instrument, encoding='unicode')
    payload['drums/sounds.json'] = json.dumps(metadata, indent=2).encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.orchid-restore-', dir=destination.parent))
    try:
        for name, content in payload.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        DrumLibrary(temporary / 'drums')  # Validate saved beat documents.
        _, errors = load_songs(temporary / 'perform-midi')
        if errors:
            raise ValueError('Invalid songs: ' + '; '.join(errors))
        if destination.exists():
            raise ValueError('Restore destination appeared during import')
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {'status': 'imported', 'data_dir': str(destination),
            'session': str(destination / 'session.json'), 'sounds': len(metadata['sounds']),
            'hint': 'Build the host on this Mac, then serve with --session pointing at this session.'}
