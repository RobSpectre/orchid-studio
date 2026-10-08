import base64
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave
import zipfile

from orchid_studio.drum_audio import NativeDrumAudio
from orchid_studio.drum_library import DrumLibrary
from orchid_studio.looper import Looper
from orchid_studio.paths import data_dir, host_path
from orchid_studio.transfer import export_bundle, import_bundle


class PortabilityTests(unittest.TestCase):
    def seed(self, root):
        library = DrumLibrary(root / 'drums')
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
            audio.writeframes(b'\x10\x00' * 480)
        library.upload('Portable click', base64.b64encode(buf.getvalue()).decode(), 'Test fixture')
        sound = next(iter(library.sounds))
        library.save({'kind':'orchid-beat','version':1,'id':'portable','name':'Portable','bars':2,
            'lanes':[{'id':'click','name':'Click','sound':sound}], 'hits':[{'lane':'click','beat':0}]})
        loop = Looper(lambda m:None, lambda e:None)
        loop.edit('step', {'slot':1, 'beat':0, 'notes':[36], 'duration':1})
        return loop.export()

    def test_round_trip_relocates_samples_preserves_notes_beats_and_licenses(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); old = root/'old computer'; new = root/'new computer'
            session = self.seed(old)
            archive = root/'session.zip'
            export_bundle(archive, session, old)
            with zipfile.ZipFile(archive) as bundle:
                metadata = bundle.read('drums/sounds.json').decode()
                self.assertNotIn(str(old), metadata)
                self.assertNotIn('Pistil.component', ' '.join(bundle.namelist()))
            result = import_bundle(archive, new)
            self.assertEqual(json.loads(Path(result['session']).read_text()), session)
            library = DrumLibrary(new/'drums')
            backend = NativeDrumAudio(Mock(), library); backend.load()
            spec = backend.host.call.call_args.kwargs['sounds'][0]
            self.assertTrue(Path(spec['path']).is_file())
            self.assertTrue(Path(spec['path']).is_relative_to(new.resolve()))
            self.assertEqual(library.kits[0]['license'], 'Test fixture')
            self.assertEqual(library.get('portable')['hits'][0]['beat'], 0)
            with self.assertRaises(ValueError): import_bundle(archive, new)
            with self.assertRaises(FileExistsError): export_bundle(archive, session, old)

    def test_rejects_traversal_and_checksum_damage_without_creating_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); session=self.seed(root/'source')
            good=root/'good.zip'; export_bundle(good,session,root/'source')
            for extra in ('../escape', 'drums/assets/../../escape', '/tmp/escape', 'unexpected.component'):
                bad=root/'bad.zip'
                with zipfile.ZipFile(bad,'w') as archive:
                    archive.writestr(extra,b'bad')
                with self.assertRaises(ValueError):import_bundle(bad,root/'destination')
                self.assertFalse((root/'destination').exists())
            with zipfile.ZipFile(good) as original, zipfile.ZipFile(root/'corrupt.zip','w') as corrupt:
                for name in original.namelist():
                    corrupt.writestr(name, b'{}' if name=='session.json' else original.read(name))
            with self.assertRaisesRegex(ValueError,'checksum'):
                import_bundle(root/'corrupt.zip',root/'destination')
            self.assertFalse((root/'destination').exists())

    def test_configured_paths_are_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'ORCHID_STUDIO_DATA_DIR':folder}):
            self.assertEqual(data_dir(),Path(folder).resolve())
            self.assertTrue(host_path().is_relative_to(data_dir()))
            self.assertEqual(DrumLibrary().root,data_dir()/'drums')

    def test_native_host_can_load_empty_rack_without_hydrogen(self):
        with tempfile.TemporaryDirectory() as folder:
            library=DrumLibrary(folder)
            library.ensure_stock=Mock(side_effect=AssertionError('Must not require Hydrogen'))
            router=Mock()
            self.assertEqual(NativeDrumAudio(router,library).load()['sounds'],0)
            router.host.call.assert_called_once_with('drum-load',sounds=[])

    def test_session_startup_imports_without_starting_transport(self):
        from orchid_studio.service import serve
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'session.json'
            session=self.seed(Path(folder)/'data');path.write_text(json.dumps(session))
            reports=[]
            serve(lambda m:None, ['{"command":"status"}\n','{"command":"quit"}\n'], reports.append,session=path)
            status=next(r for r in reports if 'looper' in r)
            self.assertFalse(status['playing'])
            self.assertEqual(status['looper']['layers'][0]['notes'],session['layers'][0]['notes'])
