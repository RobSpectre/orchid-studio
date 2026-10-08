import unittest
from orchid_studio.play_along import DirectVoice


class PlayAlongTests(unittest.TestCase):
    def test_only_raw_chord_channel_notes_and_sustain_reach_separate_voice(self):
        sent=[];voice=DirectVoice(sent.append,3,70)
        for msg in ([144,60,100],[145,48,90],[0xF8],[0xB2,102,20],[240,1,247]):voice.receive(msg)
        self.assertEqual(sent,[])
        voice.receive([146,60,100]);voice.receive([146,64,60]);voice.receive([178,64,127])
        self.assertEqual(sent,[[144,60,70],[144,64,60],[176,64,127]])
        voice.receive([146,60,0]);voice.panic()
        self.assertIn([128,60,0],sent);self.assertIn([128,64,0],sent)
        self.assertIn([176,64,0],sent);self.assertFalse(voice.player.active)

    def test_worker_releases_on_pause_and_drains_notes_while_paused(self):
        import queue
        import time
        from unittest.mock import Mock,patch
        from orchid_studio.play_along import PlayAlong
        packets=queue.Queue();sent=[];active=[True]
        source=Mock();source.get_ports.return_value=['Orchid']
        def get_message():
            try:return packets.get_nowait(),0
            except queue.Empty:return None
        source.get_message.side_effect=get_message
        def until(predicate):
            deadline=time.monotonic()+1
            while not predicate() and time.monotonic()<deadline:time.sleep(.002)
            self.assertTrue(predicate())
        monitor=PlayAlong(sent.append,lambda e:None,lambda:active[0])
        with patch('orchid_studio.play_along.backend') as backend:
            backend.return_value.MidiIn.return_value=source
            monitor.configure(True,'Orchid',3)
            try:
                packets.put([146,60,70]);until(lambda:[144,60,70] in sent)
                active[0]=False;until(lambda:[128,60,0] in sent)
                packets.put([146,64,70]);until(packets.empty)
                self.assertNotIn([144,64,70],sent)
            finally:monitor.stop()
        source.close_port.assert_called_once();source.delete.assert_called_once()
        self.assertIn([176,64,0],sent)

    def test_perform_and_direct_voice_have_independent_note_lifetimes(self):
        from orchid_studio.perform import PerformanceEngine
        direct=[];performed=[];voice=DirectVoice(direct.append,3)
        engine=PerformanceEngine(performed.append,3,1,{'mode':'arp','bpm':60,'chord_window_ms':0})
        for msg in ([146,60,70],[146,64,70]):voice.receive(msg);engine.receive(msg,0)
        engine.advance(0);engine.advance(.5)
        self.assertEqual(direct,[[144,60,70],[144,64,70]])
        self.assertGreater(len(performed),2)
        engine.panic();self.assertEqual(voice.player.active,{(0,60),(0,64)})
        voice.panic();self.assertFalse(voice.player.active)
