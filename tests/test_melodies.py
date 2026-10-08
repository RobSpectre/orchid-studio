import unittest
from orchid_studio.perform import PerformanceEngine, options
from orchid_studio.melodies import BUILTIN_MELODIES as MELODIES, MELODIES as ALL_MELODIES, melodic_pitch
from orchid_studio.looper import render
from orchid_studio.timeline import Timeline


class MelodyTests(unittest.TestCase):
    def render(self,mode,root=60,length=16,**config):
        return render([{'beat':0,'duration':length,'note':root,'velocity':70}],length,
                      {'mode':mode,'step_beats':.5,'gate':.75,**config})

    def test_distinct_single_note_melodies_and_repeatable_recordings(self):
        signatures=[]
        for mode in MELODIES:
            notes=self.render(mode)
            self.assertGreaterEqual(len(notes),10)
            self.assertGreaterEqual(len({n['note'] for n in notes}),5)
            self.assertGreaterEqual(len({n['velocity'] for n in notes}),3)
            self.assertEqual(notes,self.render(mode))
            self.assertTrue(all(n['beat']+n['duration']<=16 for n in notes))
            self.assertTrue(all(1<=n['velocity']<=70 for n in notes))
            signatures.append([(n['beat'],n['note'],n['duration']) for n in notes])
        self.assertEqual(len({str(s) for s in signatures}),len(MELODIES))
        self.assertEqual(set(options()['melodic_modes']),set(ALL_MELODIES))

    def test_banks_cover_modes_once_and_hooks_return_to_a_recognizable_motif(self):
        caps=options()
        flattened=[m for bank in caps['mode_banks'].values() for m in bank]
        self.assertEqual(flattened,caps['modes'])
        self.assertEqual(len(flattened),len(set(flattened)))
        self.assertEqual(len(caps['mode_banks']['hooks']),5)
        for mode in caps['mode_banks']['hooks']:
            events=MELODIES[mode]['events']
            call=[(t,p,d) for t,p,d,_ in events if t<6]
            return_call=[(t-16,p,d) for t,p,d,_ in events if 16<=t<22]
            self.assertEqual(call,return_call)
            self.assertEqual(events[-1][1][0]%12,0)
            self.assertEqual(events[-1][1][1]%12,0)
            notes=self.render(mode)
            self.assertNotEqual([(n['beat'],n['note']) for n in notes if 4<=n['beat']<8],
                                [(n['beat']-8,n['note']) for n in notes if 12<=n['beat']<16])

    def test_composed_events_have_valid_dynamics_and_nonoverlapping_gates(self):
        for mode,melody in MELODIES.items():
            events=melody['events']
            for i,(onset,pitches,duration,accent) in enumerate(events):
                with self.subTest(mode=mode,onset=onset):
                    self.assertGreaterEqual(onset,0)
                    self.assertGreater(duration,0)
                    self.assertTrue(0<accent<=1)
                    self.assertEqual(len(pitches),2)
                    self.assertLessEqual(onset+duration,events[i+1][0] if i+1<len(events) else 32)

    def test_transpose_and_chord_quality(self):
        for mode in MELODIES:
            c=self.render(mode);d=self.render(mode,62)
            self.assertEqual([n['note']+2 for n in c],[n['note'] for n in d])
        self.assertEqual(melodic_pitch({60:70,63:70,67:70},(4,3)),63)
        self.assertEqual(melodic_pitch({60:70,64:70,67:70},(4,3)),64)
        self.assertEqual(melodic_pitch({60:70},(4,3),'orbit'),63)
        # Minor dominant leading tone survives; chromatic enclosures resolve.
        self.assertEqual(melodic_pitch({60:70,63:70},(11,11),'bloom'),71)
        spark=self.render('spark')
        self.assertEqual([n['note'] for n in spark if 1.5<=n['beat']<=2],[65,63,64])
        tide=self.render('tide')
        self.assertTrue(any(n['note']==68 and n['beat']>=8 for n in tide))

    def test_four_bar_phrase_repeats_and_division_changes_its_length(self):
        for mode in MELODIES:
            notes=self.render(mode,length=32)
            a=[n for n in notes if n['beat']<16]
            b=[{**n,'beat':n['beat']-16} for n in notes if n['beat']>=16]
            self.assertEqual(len(a),len(b))
            for first,second in zip(a,b):
                self.assertEqual(first['note'],second['note'])
                self.assertEqual(first['velocity'],second['velocity'])
                self.assertAlmostEqual(first['beat'],second['beat'])
                self.assertAlmostEqual(first['duration'],second['duration'])
            fast=self.render(mode,step_beats=.25,length=16)
            self.assertEqual(len(fast),len(notes))

    def test_release_pedal_mode_change_and_panic_release_generated_pitches(self):
        for mode in MELODIES:
            sent=[];e=PerformanceEngine(sent.append,3,1,{'mode':mode,'bpm':60,'chord_window_ms':0})
            e.receive([0x90,60,80],0);e.advance(0);self.assertFalse(sent)
            e.receive([0x92,60,80],0);e.advance(0);self.assertTrue(e.voices)
            e.receive([0xB2,64,127],0);e.receive([0x82,60,0],0)
            self.assertTrue(e.held)
            e.receive([0xB2,64,0],0);self.assertFalse(e.voices)
            count=len(sent);e.advance(20);self.assertEqual(len(sent),count)
            e.receive([0x92,60,80],20);e.advance(20)
            e.update({'mode':'off'},20);e.advance(20)
            self.assertEqual(set(e.voices),{60})
            e.panic();self.assertFalse(e.voices);self.assertFalse(e.player.active)

    def test_pitch_boundaries_stall_and_late_key_press(self):
        for mode in MELODIES:
            for root in (0,120,127):
                self.assertTrue(all(0<=n['note']<=127 for n in self.render(mode,root)))
            sent=[];e=PerformanceEngine(sent.append,3,1,{'mode':mode,'bpm':60,'chord_window_ms':0})
            e.advance(.26);e.receive([0x92,60,60],.26);e.advance(.26)
            self.assertFalse(sent)
            e.advance(.5);self.assertEqual(sent[-1][:2],[144,melodic_pitch({60:60},MELODIES[mode]['events'][0][1],mode)])
            count=sum(m[0]==144 for m in sent)
            e.advance(90)
            self.assertLessEqual(sum(m[0]==144 for m in sent)-count,1)
            e.panic()

    def test_shared_tempo_ramp_preserves_melodic_event_positions(self):
        now=[0.];t=Timeline(clock=lambda:now[0]);t.reset(120)
        onsets=[]
        e=PerformanceEngine(lambda m:onsets.append(t.position()) if m[0]==144 else None,
                            3,1,{'mode':'orbit','chord_window_ms':0})
        e.timeline=t;e.receive([0x92,60,60],0)
        for i in range(3001):
            now[0]=i*.001
            if i==500:t.tempo(60)
            e.advance(now[0])
        self.assertGreater(len(onsets),5)
        expected=[event[0]*.5 for event in MELODIES['orbit']['events']][:len(onsets)]
        for beat,target in zip(onsets,expected):self.assertAlmostEqual(beat,target,delta=.003)
        e.panic()


if __name__=='__main__':unittest.main()
