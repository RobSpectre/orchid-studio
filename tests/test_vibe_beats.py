import json
import tempfile
import unittest
from pathlib import Path
from orchid_studio.vibe_beats import documents
from orchid_studio.drum_library import DrumLibrary, validate

class VibeBeatTests(unittest.TestCase):
    def test_twelve_valid_distinct_full_length_electronic_grooves(self):
        docs=documents();self.assertEqual(len(docs),12)
        self.assertEqual(docs,documents())
        signatures=set()
        for d in docs.values():
            validated=validate(d,{l['sound']:{} for l in d['lanes']})
            self.assertEqual(validated['bars'],12)
            self.assertTrue(all(any(bar*4<=h['beat']<(bar+1)*4 for h in d['hits']) for bar in range(12)))
            signatures.add(tuple((h['lane'],h['beat']) for h in d['hits'] if h['lane'] in ('kick','snare')))
            self.assertTrue(d['tags'] and d['vibe'] and d['best_for'] and d['arrangement'])
            self.assertFalse(any('cymbal' in l['sound'] or 'open-hat' in l['sound'] or 'ring' in l['sound'] for l in d['lanes']))
        self.assertEqual(len(signatures),12)
        self.assertLess(len(docs['still-water']['hits']),len(docs['cloud-chaser']['hits'])/2)
        self.assertTrue(any(abs(h['beat']*4-round(h['beat']*4))>.1 for h in docs['paper-comet']['hits']))

    def test_optional_samples_saved_edits_and_catalog_metadata(self):
        docs=documents()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);empty=DrumLibrary(root)
            self.assertTrue(set(docs).isdisjoint(empty.documents))
            sounds={l['sound']:{} for d in docs.values() for l in d['lanes']}
            (root/'sounds.json').write_text(json.dumps({'sounds':sounds,'kits':[]}))
            lib=DrumLibrary(root);self.assertTrue(set(docs)<=lib.documents.keys())
            d=lib.get('still-water');d['name']='My edited water';lib.save(d)
            restored=DrumLibrary(root);self.assertEqual(restored.get(d['id'])['name'],'My edited water')
            item=next(x for x in restored.catalog() if x['id']=='still-water')
            for key in ('vibe','tags','energy','density','best_for','arrangement','bank'):self.assertEqual(item[key],d[key])
            item['tags'].append('external mutation');self.assertNotIn('external mutation',restored.get(d['id'])['tags'])

    def test_vibe_metadata_validation(self):
        d=documents()['still-water']
        for key,value in [('tags','ambient'),('tags',[2]),('energy','loud'),('density',[]),('vibe',42)]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate({**d,key:value})
