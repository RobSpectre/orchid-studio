import unittest
from unittest.mock import Mock
from orchid_studio.looper import Looper
from orchid_studio.timeline import Timeline
from orchid_studio.perform import settings
from orchid_studio.api import Controller

class KeyStartTests(unittest.TestCase):
    def test_only_fresh_raw_chord_attacks_resume(self):
        reports=[];l=Looper(lambda m:None,reports.append);l.timeline=Timeline();l.timeline.reset(108);l.timeline.pause(True)
        l.clock_output=Mock();l.start_on_key=True;l.held={60:70}
        source=Mock();source.get_message.side_effect=[([0x90,64,80],0),([0x91,64,80],0),([0xB2,64,127],0),([0x92,60,80],0),([0x92,67,0],0),None]
        self.assertEqual(l._paused_input(source,3),[]);self.assertTrue(l.timeline.paused)
        source.get_message.side_effect=[([0x82,60,0],0),([0x92,60,80],0)]
        self.assertEqual(l._paused_input(source,3),[[0x92,60,80]])
        self.assertFalse(l.timeline.paused);l.clock_output.pause.assert_called_once_with(False)
        self.assertEqual(len(reports),1)
        l.stop();self.assertFalse(l.start_on_key)

    def test_disabled_does_not_wake(self):
        l=Looper(lambda m:None,lambda e:None);l.timeline=Timeline();l.timeline.reset(108);l.timeline.pause(True)
        source=Mock();source.get_message.side_effect=[([0x92,60,80],0),None]
        self.assertEqual(l._paused_input(source,3),[]);self.assertTrue(l.timeline.paused)

    def test_wait_starts_at_zero_and_keeps_trigger_note_once(self):
        now=[0.];sent=[];reports=[]
        l=Looper(lambda m:sent.append((now[0],m)),reports.append)
        l.timeline=Timeline(clock=lambda:now[0]);l.start_on_key=l.wait_for_key=True
        l.perform=settings({'bpm':120,'mode':'off'});l._input_name='Orchid';l.config['count_in']=8
        l.layers[0]['notes']=[{'beat':0,'duration':1,'note':36,'velocity':64}]
        l.drums=Mock();l.drum_config={'pattern':0,'volume':.3}
        packets=[(.1,[0x90,99,64]),(.2,[0x91,88,64]),(.5,[0x92,60,70]),(.6,[0x82,60,0])]
        source=Mock();source.get_ports.return_value=['Orchid']
        def receive():
            if packets and now[0]>=packets[0][0]:return packets.pop(0)[1],0
        source.get_message.side_effect=receive
        class Stop:
            def is_set(self):return now[0]>=.8
            def wait(self,dt):now[0]+=dt
        l.stop_event=Stop();l._run(source,3,1,clock=lambda:now[0])
        attacks=[(t,m) for t,m in sent if m[0]==0x90 and m[2]]
        self.assertEqual([m for t,m in attacks if m[1]==60],[[0x90,60,70]])
        self.assertEqual([m for t,m in attacks if m[1]==36],[[0x90,36,64]])
        self.assertGreaterEqual(attacks[0][0],.5);self.assertLess(attacks[0][0],.53)
        self.assertLess(l.beat,1);l.drums.start.assert_called_once()
        self.assertEqual(l.drums.client.command.call_count,1) # Pause stop happens once, not on every input poll.
        self.assertLess(l.key_start_timing['midi_to_live_send_ms'],15)
        self.assertLess(l.key_start_timing['midi_to_loop_send_ms'],15)
        self.assertTrue(any(e['event']=='key_live_dispatched' for e in reports))
        self.assertFalse(any(e['event']=='playback_error' for e in reports),reports)
        self.assertIn([0x80,60,0],[m for t,m in sent])

    def test_playing_existing_loops_has_no_recording_count_in(self):
        now=[0.];sent=[];l=Looper(lambda m:sent.append((now[0],m)),lambda e:None)
        l.timeline=Timeline(clock=lambda:now[0]);l._input_name='Orchid'
        l.config['count_in']=8;l.perform=settings({'bpm':108,'mode':'off'})
        l.layers[0]['notes']=[{'beat':0,'duration':1,'note':36,'velocity':70}]
        source=Mock();source.get_message.return_value=None;source.get_ports.return_value=['Orchid']
        class Stop:
            def is_set(self):return now[0]>=.05
            def wait(self,dt):now[0]+=dt
        l.stop_event=Stop();l._run(source,3,1,clock=lambda:now[0])
        self.assertEqual([(t,m) for t,m in sent if m[0]==0x90 and m[2]],[(0.,[0x90,36,70])])

    def test_api_enables_existing_paused_loop_and_rejects_bad_flag(self):
        c=Controller(lambda m:None,lambda e:None)
        try:
            l=c.transport.looper;l.worker=Mock();l.worker.is_alive.return_value=True
            self.assertEqual(c.execute({'command':'key-start','enabled':True})['status'],'ok')
            self.assertTrue(l.start_on_key)
            self.assertEqual(c.execute({'command':'key-start','enabled':'yes'})['status'],'error')
            l.take={'slot':0}
            self.assertEqual(c.execute({'command':'key-start','enabled':False})['status'],'error')
            l.take=None;l.worker=None
            self.assertEqual(c.execute({'command':'key-start','enabled':False})['status'],'ok')
        finally:c.close()
