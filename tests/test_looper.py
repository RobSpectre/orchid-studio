import copy
import unittest
from unittest.mock import Mock

from orchid_studio.api import Controller
from orchid_studio.looper import Looper, Voices, quantize, render
from orchid_studio.perform import settings
from orchid_studio.sequencer import compile_session


def note(beat=0, duration=1, pitch=60):
    return {'beat':beat,'duration':duration,'note':pitch,'velocity':64}


class LoopTests(unittest.TestCase):
    def test_clear_running_layer_releases_only_that_layer_and_supports_undo(self):
        sent=[];l=Looper(sent.append,lambda e:None)
        for slot in (1,2):l.edit('step',{'slot':slot,'beat':0,'notes':[60]})
        saved=copy.deepcopy(l.layers)
        l.worker=Mock();l.worker.is_alive.return_value=True
        l.bus=Voices(sent.append,1)
        l.bus.receive(0,[144,60,64]);l.bus.receive(1,[144,60,64])
        l.edit('clear',{'slot':1})
        self.assertEqual(l.layers[0]['notes'],[])
        self.assertEqual(l.layers[1],saved[1])
        self.assertNotIn([128,60,0],sent) # Other layer still owns the same pitch.
        l.bus.release(1);self.assertIn([128,60,0],sent)
        undo=copy.deepcopy(l.undo_layers);l.edit('clear',{'slot':1})
        self.assertEqual(l.undo_layers,undo) # Empty clears cannot erase recovery.
        l.worker=None;l.edit('undo',{})
        self.assertEqual(l.layers,saved)

    def test_api_clear_is_available_during_playback_and_rejects_invalid_slots(self):
        c=Controller(lambda m:None,lambda r:None)
        try:
            for slot in (1,2):self.assertEqual(c.execute({'command':'loop-step','slot':slot,'beat':0,'notes':[60]})['status'],'ok')
            l=c.transport.looper;l.worker=Mock();l.worker.is_alive.return_value=True
            self.assertEqual(c.execute({'command':'loop-clear','slot':1})['status'],'ok')
            self.assertFalse(l.layers[0]['notes']);self.assertTrue(l.layers[1]['notes'])
            before=copy.deepcopy(l.layers)
            self.assertEqual(c.execute({'command':'loop-clear','slot':5})['status'],'error')
            self.assertEqual(l.layers,before)
            self.assertEqual(c.execute({'command':'loop-clear'})['status'],'ok')
            self.assertTrue(all(not x['notes'] for x in l.layers))
            l.worker=None
            self.assertEqual(c.execute({'command':'loop-undo'})['status'],'ok')
            self.assertEqual(l.layers,before)
        finally:c.close()

    def test_clear_rejects_active_take_without_mutation(self):
        l=Looper(lambda m:None,lambda e:None)
        l.edit('step',{'slot':1,'beat':0,'notes':[60]})
        before=copy.deepcopy(l.layers);l.take={'slot':1}
        with self.assertRaises(ValueError):l.edit('clear',{'slot':1})
        self.assertEqual(l.layers,before)

    def test_eighth_grid_groups_chord_across_midpoint_and_keeps_short_taps(self):
        notes=quantize([note(.24,.05,60),note(.27,.02,64),note(.29,.03,67)],16,.5)
        self.assertEqual({n['beat'] for n in notes},{0})
        self.assertEqual({n['duration'] for n in notes},{.5})
        self.assertEqual(quantize([note(.38,.3)],16,.5)[0]['beat'],.5)

    def test_boundary_and_same_pitch_collisions_are_safe(self):
        notes=quantize([note(0,.7),note(.13,.4),note(3.9,1)],4,.5)
        compile_session({'version':1,'bpm':120,'length_beats':4,'tracks':[{'name':'layer','channel':1,'notes':notes}]})
        self.assertTrue(all(n['beat']+n['duration']<=4 for n in notes))
        self.assertEqual(notes[-1]['beat'],3.5)
        self.assertEqual(len(notes),2)

    def test_free_timing_preserves_attack(self):
        self.assertEqual(quantize([note(.273,.183)],4,0)[0]['beat'],.273)

    def test_all_perform_modes_render_valid_releasing_clips(self):
        from orchid_studio.perform import MODES
        for mode in MODES:
            with self.subTest(mode=mode):
                output=render([note(0,4,p) for p in (60,64,67)],4,{'mode':mode})
                self.assertTrue(output)
                compile_session({'version':1,'bpm':120,'length_beats':4,'tracks':[{'name':'layer','channel':1,'notes':output}]})
        arp=render([note(0,4,p) for p in (60,64,67)],4,{'mode':'arp','step_beats':.5})
        self.assertEqual([n['note'] for n in arp],[60,64,67,60,64,67,60,64])

    def test_shared_notes_survive_other_layer_release_and_panic(self):
        sent=[];bus=Voices(sent.append,1)
        bus.receive(0,[0x90,60,60]);bus.receive(1,[0x90,60,70])
        bus.receive(0,[0x80,60,0]);bus.receive(0,[0xB0,120,0])
        self.assertEqual(sent,[[0x90,60,60]])
        bus.release(1)
        self.assertEqual(sent[-1],[0x80,60,0])
        bus.receive(1,[0x90,64,70]);bus.panic()
        self.assertIn([0x80,64,0],sent)
        self.assertIn([0xB0,64,0],sent)

    def test_step_undo_and_roundtrip_import_validation(self):
        l=Looper(lambda m:None,lambda e:None)
        req={'slot':1,'beat':0,'duration':4,'notes':[60,64,67],'settings':{'mode':'arp'}}
        l.edit('step',req);saved=l.export()
        l.edit('clear',{'slot':1});self.assertFalse(l.layers[0]['notes'])
        l.edit('undo',{});self.assertEqual(l.export(),saved)
        restored=Looper(lambda m:None,lambda e:None);restored.restore(saved)
        self.assertEqual(restored.export(),saved)
        invalid=copy.deepcopy(saved);invalid['layers'][0]['chords'][0]['note']=128
        with self.assertRaises(ValueError): restored.restore(invalid)
        self.assertEqual(restored.export(),saved)
        with self.assertRaises(ValueError): restored.configure({'bars':8})

    def test_record_count_in_channel_isolation_auto_loop_and_cleanup(self):
        # Deterministic two-cycle run, including release after the recording boundary.
        sent=[];reports=[];clock=[0.]
        l=Looper(sent.append,reports.append)
        l.config={'bars':1,'grid':.5,'count_in':4};l.perform=settings({'bpm':120,'mode':'off'})
        l._input_name='Orchid';l.take={'slot':0,'start':0,'active':{},'notes':[],
                                     'settings':l.perform,'started':False}
        packets=[(2.09,[0x92,60,64]),(2.10,[0x92,64,64]),(2.1,[0x90,99,64]),
                 (2.4,[0x82,60,0]),(2.42,[0x82,64,0]),(3.6,[0x92,67,64]),(4.1,[0x82,67,0])]
        source=Mock();source.get_ports.return_value=['Orchid']
        def get_message():
            if packets and clock[0]>=packets[0][0]:
                return packets.pop(0)[1],0
        source.get_message.side_effect=get_message
        class Stop:
            def is_set(self):return clock[0]>=6.1
            def wait(self,dt):clock[0]+=dt
        l.stop_event=Stop();l._run(source,3,1,clock=lambda:clock[0])
        self.assertEqual({n['note'] for n in l.layers[0]['chords']},{60,64,67})
        self.assertEqual(l.layers[0]['chords'][0]['beat'],0)
        self.assertEqual(l.layers[0]['chords'][-1]['beat'],3)
        self.assertEqual(l.layers[0]['chords'][-1]['duration'],1)
        self.assertGreaterEqual(sent.count([0x90,60,64]),2) # monitored then replayed
        self.assertTrue(any(r['event']=='loop_take_complete' for r in reports))
        self.assertFalse(any(r['event']=='playback_error' for r in reports),reports)
        self.assertIn([0xB0,64,0],sent);source.close_port.assert_called_once()

    def test_api_roundtrip_and_invalid_commands(self):
        c=Controller(lambda m:None,lambda r:None)
        try:
            self.assertEqual(c.execute({'command':'loop-configure','settings':{'grid':.5}})['status'],'ok')
            self.assertEqual(c.execute({'command':'loop-step','slot':1,'beat':0,'notes':[60,64,67]})['status'],'ok')
            doc=c.execute({'command':'loop-export'})['document']
            self.assertEqual(c.execute({'command':'loop-import','document':doc})['status'],'ok')
            for req in ({'command':'loop-configure','settings':{'grid':True}},
                        {'command':'loop-step','slot':1,'beat':16,'notes':[60]},
                        {'command':'loop-record','slot':1},
                        {'command':'loop-start','input':'Orchid Studio Playback','chord_channel':3},
                        {'command':'loop-mute','slot':1,'muted':'yes'}):
                self.assertEqual(c.execute(req)['status'],'error',req)
            self.assertEqual(c.execute({'command':'loop-export'})['document'],doc)
        finally:c.close()


class ComposeTests(unittest.TestCase):
    def test_a_composition_replaces_a_layer_now_when_stopped_and_on_the_next_boundary_while_playing(self):
        events=[];l=Looper(lambda m:None,events.append)
        l.configure({'bars':4})
        chords=[{'beat':0,'duration':4,'notes':[60,64,67],'velocity':70},{'beat':8,'duration':12,'notes':[57,60,64]}]
        done=l.edit('compose',{'slot':2,'chords':chords})
        self.assertIsNone(done['applies_at_beat'])
        self.assertEqual(len(l.layers[1]['chords']),6)
        self.assertEqual(max(c['beat']+c['duration'] for c in l.layers[1]['chords']),16)  # held to the loop's end at most
        playing=Mock();playing.is_alive.return_value=True;l.worker=playing;l.beat=21.5  # second pass, beat 5.5
        done=l.edit('compose',{'slot':2,'chords':[{'beat':0,'duration':2,'notes':[62]}]})
        self.assertEqual(done['applies_at_beat'],32)  # the next loop boundary: the pass in progress plays on
        self.assertEqual(len(l.layers[1]['chords']),6)
        l.beat=31.9;l._land_compose();self.assertEqual(len(l.layers[1]['chords']),6)
        l.beat=32.0;l._land_compose()
        self.assertEqual([c['note'] for c in l.layers[1]['chords']],[62])
        self.assertEqual(events[-1],{'event':'loop_composed','slot':2,'beat':32})
        for bad in ({'slot':5,'chords':chords},{'slot':1,'chords':[]},{'slot':1,'chords':[{'beat':16,'notes':[60]}]},
                    {'slot':1,'chords':[{'beat':0,'notes':[]}]}):
            with self.assertRaises(ValueError):l.edit('compose',bad)

