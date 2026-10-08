import json
from pathlib import Path
import tempfile
import unittest
from orchid_studio.indie_beats import documents, sound_id
from orchid_studio.beats import catalog
from orchid_studio.drum_library import DrumLibrary, validate


class IndieBankTests(unittest.TestCase):
    def test_playable_distinct_arrangements_with_restrained_fills(self):
        bank=documents()
        self.assertEqual(list(bank),[b['id'] for b in catalog()])
        kick_shapes=[]
        for d in bank.values():
            validate(d)
            self.assertEqual(d['bars'],12)
            self.assertEqual({int(h['beat']//4) for h in d['hits']},set(range(12)))
            # Explicit development across three phrases, not copies of a short loop.
            phrases=[{(h['lane'],h['beat']%16,h['velocity']) for h in d['hits'] if int(h['beat']//16)==i} for i in range(3)]
            self.assertEqual(len({frozenset(p) for p in phrases}),3)
            self.assertTrue(all(h['velocity']<=.28 for h in d['hits'] if h['lane']=='click'))
            self.assertTrue(all(h['beat']*4==int(h['beat']*4) for h in d['hits']))
            kick_shapes.append(tuple(h['beat'] for h in d['hits'] if h['lane']=='kick'))
        self.assertEqual(len(set(kick_shapes)),12)
        self.assertGreaterEqual(len({l['sound'] for d in bank.values() for l in d['lanes']}),20)

    def test_optional_pack_upgrade_and_saved_edits_take_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);base=DrumLibrary(root)
            self.assertTrue(all(l['sound'].startswith('tr808') for l in base.get('glass-house')['lanes']))
            sounds={l['sound']:{'id':l['sound']} for d in documents().values() for l in d['lanes']}
            (root/'sounds.json').write_text(json.dumps({'sounds':sounds,'kits':[]}))
            upgraded=DrumLibrary(root)
            self.assertEqual(upgraded.get('glass-house'),documents()['glass-house'])
            d=upgraded.get('glass-house');d['name']='My edited beat';upgraded.save(d)
            self.assertEqual(DrumLibrary(root).get('glass-house')['name'],'My edited beat')
            self.assertEqual(upgraded.catalog()[5]['feel'],'bright clipped house')
