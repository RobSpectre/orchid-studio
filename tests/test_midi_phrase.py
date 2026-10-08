import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from orchid_studio.midi_phrase import read_phrase
from orchid_studio.song_modes import load_songs
from orchid_studio.melodies import MELODIES
from orchid_studio.perform import MODES, PerformanceEngine
from orchid_studio.looper import render


def midi(track,division=96):
    return b'MThd'+struct.pack('>IHHH',6,0,1,division)+b'MTrk'+struct.pack('>I',len(track))+track

# Two-note, one-bar synthetic fixture with initial and trailing rests,
# running status, note-on-zero release, unequal dynamics, and tempo metadata.
TRACK=bytes.fromhex('00ff510307a120 18903c50 303c00 30904028 304000 18ff2f00')


class MidiPhraseTests(unittest.TestCase):
    def test_ppqn_running_status_and_rests(self):
        p=read_phrase(midi(TRACK))
        self.assertEqual(p['notes'],[(.25,60,.5,80),(1.25,64,.5,40)])
        self.assertEqual(p['source_beats'],2)
        self.assertEqual(p['loop_beats'],4)
        self.assertEqual(p['suggested_bpm'],120)

    def test_rejects_truncated_files_polyphony_drums_and_hanging_notes(self):
        for raw in (b'',midi(TRACK)[:-1],midi(TRACK,division=0xE728),
                    midi(bytes.fromhex('00903c50 00904050 60803c00 00804000 00ff2f00')),
                    midi(bytes.fromhex('00992450 60992400 00ff2f00')),
                    midi(bytes.fromhex('00903c50 60ff2f00'))):
            with self.subTest(raw=raw),self.assertRaises(ValueError):read_phrase(raw)

    def test_imported_phrase_preserves_intervals_timing_and_bar_repeat(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'test.mid').write_bytes(midi(TRACK))
            (root/'songs.json').write_text(json.dumps([{'id':'song-test','label':'TEST','title':'Synthetic test','file':'test.mid'}]))
            songs,errors=load_songs(root);self.assertFalse(errors)
            with patch.dict(MELODIES,songs),patch('orchid_studio.perform.MODES',(*MODES,'song-test')):
                config={'mode':'song-test','step_beats':.5,'gate':1,'velocity_limit':80}
                def phrase(root_note):
                    return render([{'beat':0,'duration':8,'note':root_note,'velocity':80}],8,config)
                result=phrase(60)
                self.assertEqual([(n['beat'],n['note'],n['velocity']) for n in result],
                                 [(.25,60,80),(1.25,64,40),(4.25,60,80),(5.25,64,40)])
                for n in result:self.assertAlmostEqual(n['duration'],.5)
                self.assertEqual([n['note'] for n in phrase(62)],[62,66,62,66])
                sent=[];e=PerformanceEngine(sent.append,3,1,{**config,'bpm':60,'chord_window_ms':0})
                e.receive([0x92,60,80],0);e.advance(0);e.advance(.25)
                self.assertTrue(e.voices)
                e.receive([0x82,60,0],.26);self.assertFalse(e.voices)
                e.advance(5);self.assertFalse(e.voices)

    def test_missing_or_invalid_optional_library_does_not_break_builtin_modes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.assertEqual(load_songs(root),({},[]))
            (root/'songs.json').write_text(json.dumps([{'id':'song-test','file':'../outside.mid'}]))
            songs,errors=load_songs(root);self.assertEqual(songs,{});self.assertTrue(errors)


if __name__=='__main__':unittest.main()
