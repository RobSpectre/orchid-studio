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

    def test_direct_keys_ignore_transport_but_stop_and_panic_release_notes(self):
        import queue
        import time
        import tempfile
        from unittest.mock import Mock,patch
        from orchid_studio.api import Controller
        from orchid_studio.drum_library import DrumLibrary
        packets=queue.Queue();sent=[]
        source=Mock();source.get_ports.return_value=['Orchid']
        def get_message():
            try:return packets.get_nowait(),0
            except queue.Empty:return None
        source.get_message.side_effect=get_message
        def until(predicate):
            deadline=time.monotonic()+1
            while not predicate() and time.monotonic()<deadline:time.sleep(.002)
            self.assertTrue(predicate())
        with tempfile.TemporaryDirectory() as directory, patch('orchid_studio.play_along.backend') as backend:
            backend.return_value.MidiIn.return_value=source
            controller=Controller(lambda m:None,lambda e:None,drum_library=DrumLibrary(directory))
            controller.sounds.healthy=Mock(return_value=True)
            controller.sounds.send_layer=lambda slot,message:sent.append((slot,message))
            controller.sounds.panic=Mock()
            monitor=controller.play_along
            def command(name,**kwargs):
                result=controller.execute({'command':name,**kwargs})
                self.assertEqual(result['status'],'ok',result)
            def press(note):
                packets.put([146,note,70]);until(lambda:(6,[144,note,70]) in sent)
            command('play-along',enabled=True,input='Orchid',chord_channel=3)
            try:
                self.assertFalse(controller.transport.playing)
                press(60)  # Immediately after launch, before any transport starts.
                controller.transport.worker=Mock()
                controller.transport.worker.is_alive.return_value=True
                controller.transport.timeline.reset(96)
                press(62)
                command('pause')
                press(64)
                self.assertNotIn((6,[128,60,0]),sent)  # Pause leaves held direct notes alone.
                controller.sounds.panic.assert_not_called()
                command('resume');press(65)
                for action,note in (('stop',67),('panic',69)):
                    packets.put([178,64,127]);packets.put([178,66,127])
                    until(lambda:(6,[176,66,127]) in sent)
                    held=set(monitor.voice.player.active)
                    command(action)
                    for _,pitch in held:self.assertIn((6,[128,pitch,0]),sent)
                    for cc in (64,66):self.assertIn((6,[176,cc,0]),sent)
                    self.assertFalse(monitor.voice.player.active)
                    self.assertTrue(monitor.state['enabled'])
                    self.assertFalse(controller.transport.playing)
                    sent.clear();press(note)
                command('play-along',enabled=False)
                self.assertIn((6,[128,69,0]),sent)
                self.assertFalse(monitor.state['enabled'])
                self.assertIsNone(monitor.worker)
            finally:controller.close()
        source.close_port.assert_called_once();source.delete.assert_called_once()
        self.assertIn((6,[176,64,0]),sent)

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
