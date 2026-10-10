import copy
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from orchid_studio.timeline import Timeline
from orchid_studio.sequencer import Player, Event
from orchid_studio.api import Controller
from orchid_studio.clock_output import ClockOutput
from test_pistil_host import host, state

class SharedTempoTests(TestCase):
    def test_tempo_preserves_phase_and_pause_freezes_time(self):
        now=[10.];t=Timeline(clock=lambda:now[0]);t.reset(120,-4)
        now[0]+=1.;self.assertEqual(t.position(),-2.)
        t.tempo(60,0);self.assertEqual(t.position(),-2.)
        now[0]+=3.;self.assertEqual(t.position(),1.)
        t.pause(True);now[0]+=100.;t.tempo(180,0)
        self.assertEqual(t.position(),1.)
        t.pause(False);now[0]+=2.;self.assertEqual(t.position(),7.)
        t.stop();self.assertFalse(t.running);self.assertEqual(t.position(),0)

    def test_clip_and_drum_ticks_follow_same_changing_tempo(self):
        now=[0.];t=Timeline(clock=lambda:now[0]);t.reset(120)
        sent=[];ticks=[];changed=[False]
        def sleep(delta):
            now[0]+=delta
            if now[0]>=.25 and not changed[0]:t.tempo(60,0);changed[0]=True
        p=Player(lambda m:sent.append((now[0],m)),{0},clock=lambda:now[0],sleep=sleep)
        p.play([Event(0,(144,60,70),'live'),Event(1,(128,60,0),'live')],120,2,tick=ticks.append,timeline=t)
        release=next(at for at,msg in sent if msg==[128,60,0])
        self.assertAlmostEqual(release,.75,delta=.005)
        self.assertAlmostEqual(now[0],1.75,delta=.005)
        self.assertEqual(ticks,sorted(ticks));self.assertTrue(all(x<2 for x in ticks))

    def test_bezier_tempo_integral_retarget_and_pause(self):
        now=[0.];t=Timeline(clock=lambda:now[0]);t.reset(120)
        t.tempo(60)
        now[0]=.5
        self.assertAlmostEqual(t.bpm,110.625)
        now[0]=1
        self.assertAlmostEqual(t.bpm,90)
        self.assertAlmostEqual(t.position(),1.8125)
        t.pause(True);beat=t.position();now[0]=100
        self.assertEqual(t.position(),beat);self.assertEqual(t.bpm,90)
        t.pause(False);now[0]=101
        self.assertEqual(t.bpm,60);self.assertAlmostEqual(t.position(),3)
        t.tempo(180);now[0]=102
        self.assertEqual(t.bpm,120)
        beat=t.position();t.tempo(80)
        self.assertEqual(t.bpm,120);self.assertEqual(t.position(),beat)
        now[0]=104
        self.assertEqual(t.bpm,80);self.assertAlmostEqual(t.position()-beat,10/3)
        self.assertFalse(t.snapshot()['transitioning'])

    def test_bezier_clock_pulses_follow_integrated_beat(self):
        now=[0.];t=Timeline(clock=lambda:now[0]);t.reset(120)
        output=Mock();clock=ClockOutput(clock=lambda:now[0]);clock.output=output
        clock.begin();t.tempo(60)
        for n in range(1001):
            now[0]=n*.002
            clock.advance(t.position(),t.bpm);clock.flush()
        now[0]+= .05;clock.flush()
        self.assertIsNone(clock.error)
        self.assertEqual(clock.pulses,73) # beats 0 through 3 inclusive at 24 PPQN
        self.assertEqual(t.target_bpm,60)

    def test_api_ramp_updates_native_tempo_and_drums_with_current_rate(self):
        now=[0.];c=Controller(Mock(),Mock(),drums=Mock());c.sounds.host=host()
        t=Timeline(clock=lambda:now[0]);c.transport.timeline=t;t.reset(120)
        try:
            r=c.execute({'command':'tempo','bpm':60})
            self.assertEqual(r['tempo']['bpm'],120)
            self.assertEqual(r['tempo']['target_bpm'],60)
            c.sounds.host.call.assert_called_with('tempo',bpm=120)
            now[0]=1;c.transport.sync_tempo()
            c.sounds.host.call.assert_called_with('tempo',bpm=90,wait=False)
            self.assertEqual(c.transport.drums.bpm,90)
            now[0]=2;c.transport.last_tempo_at=0;c.transport.sync_tempo()
            c.sounds.host.call.assert_called_with('tempo',bpm=60,wait=False)
            before=t.snapshot()
            self.assertEqual(c.execute({'command':'tempo','bpm':100,'transition_seconds':-1})['status'],'error')
            self.assertEqual(t.snapshot(),before)
        finally:c.close()

    def test_clock_reports_the_beat_at_a_monotonic_time_other_processes_share(self):
        now=[50.];c=Controller(Mock(),Mock())
        t=Timeline(clock=lambda:now[0]);c.transport.timeline=t
        try:
            stopped=c.execute({'command':'clock'})['clock']
            self.assertEqual((stopped['running'],stopped['t']),(False,50.))
            t.reset(120);now[0]=51.5
            clock=c.execute({'command':'clock'})['clock']
            self.assertEqual((clock['bpm'],clock['beat'],clock['t'],clock['running']),(120,3.,51.5,True))
        finally:c.close()

    def test_fx_sets_one_voices_delay_and_reverb_with_beats_at_the_current_tempo(self):
        c=Controller(Mock(),Mock())
        try:
            self.assertEqual(c.execute({'command':'fx','reverb':{'mix':30}})['status'],'error')  # no native host yet
            c.sounds.host=host();c.transport.timeline.reset(120)
            r=c.execute({'command':'fx','delay':{'mix':25,'beats':0.5,'feedback':40},'reverb':{'mix':30,'room':'cathedral'}})
            self.assertEqual(r['status'],'ok')
            self.assertEqual(r['fx']['delay'],{'mix':25,'time':0.25,'feedback':40})  # an eighth at 120 BPM
            c.sounds.host.call.assert_called_with('fx',slot=5,delay={'mix':25,'time':0.25,'feedback':40},
                                                  reverb={'mix':30,'room':'cathedral'})
            c.execute({'command':'fx','reverb':{'mix':0}})  # partial: the delay stays; reverb off
            self.assertEqual(c.execute({'command':'status'})['fx'][5],{'delay':{'mix':25,'time':0.25,'feedback':40},'reverb':{'mix':0,'room':'cathedral'}})
            for bad in ({'reverb':{'room':'garage'}},{'delay':{'mix':120}},{'delay':{'speed':1}},{},{'slot':7,'reverb':{'mix':1}}):
                self.assertEqual(c.execute({'command':'fx',**bad})['status'],'error')
        finally:c.close()

    def test_api_global_tempo_updates_defaults_loops_drums_and_native_au(self):
        c=Controller(Mock(),Mock(),drums=Mock());c.sounds.host=host()
        try:
            r=c.execute({'command':'tempo','bpm':137});self.assertEqual(r['status'],'ok')
            s=c.snapshot();self.assertEqual([s['tempo']['bpm'],s['performance_defaults']['bpm'],s['looper']['bpm'],s['drums']['bpm']],[137]*4)
            c.sounds.host.call.assert_called_with('tempo',bpm=137)
            c.execute({'command':'perform-configure','settings':{'bpm':111,'mode':'harp'}})
            self.assertEqual(c.snapshot()['tempo']['bpm'],111)
            before=c.snapshot()['tempo']['bpm']
            self.assertEqual(c.execute({'command':'tempo','bpm':float('nan')})['status'],'error')
            self.assertEqual(c.snapshot()['tempo']['bpm'],before)
        finally:c.close()

    def test_midi_pause_drains_pulses_and_continues_without_new_start(self):
        now=[0.];out=Mock();c=ClockOutput(clock=lambda:now[0]);c.output=out;c.offset_ms=40
        c.begin();c.advance(0,120);now[0]=.01;c.pause(True)
        now[0]=.06;c.flush();c.advance(.1,120)
        self.assertEqual([x.args[0] for x in out.send_message.call_args_list],[[250],[248],[252]])
        c.pause(False);now[0]=.11;c.flush()
        self.assertEqual(out.send_message.call_args.args[0],[251])
        self.assertEqual(c.next_tick,1);c.stop()

class MixerTests(TestCase):
    def test_live_and_layer_mixes_are_independent_and_validate_before_apply(self):
        c=Controller(Mock(),Mock());c.sounds.host=host()
        try:
            original=copy.deepcopy(c.sounds.mix)
            r=c.execute({'command':'mixer-set','channel':'live','volume':.6,'pan':-.75})
            self.assertEqual(r['status'],'ok');c.sounds.host.call.assert_called_with('mix',target='live',slot=5,volume=.6,pan=-.75)
            self.assertEqual(c.sounds.mix['layer-1'],original['layer-1'])
            self.assertEqual(c.execute({'command':'mixer-set','channel':'live','pan':2})['status'],'error')
            self.assertEqual(c.sounds.mix['live']['pan'],-.75)
            c.software_send([144,60,70]);c.sounds.host.call.assert_called_with('midi',slot=5,message=[144,60,70],wait=False)
        finally:c.close()

    def test_five_states_and_mixer_recall_with_four_state_migration(self):
        c=Controller(Mock(),Mock());c.sounds.host=host();c.sounds.host.states.append(state(4))
        with tempfile.TemporaryDirectory() as folder:
            c.sounds.recovery_path=Path(folder)/'state.json'
            try:
                c.sounds.set_mix('layer-2',{'volume':.45,'pan':.7})
                saved=c.sounds.capture();self.assertEqual(len(saved['states']),5)
                c.sounds.set_mix('layer-2',{'pan':-1});c.sounds.restore(saved)
                self.assertEqual(c.sounds.mix['layer-2'],{'volume':.45,'pan':.7})
                legacy=copy.deepcopy(saved);legacy['format']='pistil-au-v1';legacy['states']=legacy['states'][:4];legacy['labels']=legacy['labels'][:4]
                c.sounds.restore(legacy);self.assertEqual(len(c.sounds.labels),6)
            finally:c.close()
