import base64
import copy
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock
import wave

from orchid_studio.drum_library import DrumLibrary, validate
from orchid_studio.drum_sequencer import StudioDrums
from orchid_studio.sequencer import Player, Event


def document():
    return {'kind':'orchid-beat','version':1,'id':'test-beat','name':'Test','bars':12,
            'lanes':[{'id':'kick','name':'Kick','sound':'test-kick'}],
            'hits':[{'lane':'kick','beat':i,'velocity':.6} for i in range(48)]}


class DrumTests(unittest.TestCase):
    def setup_drums(self, folder):
        library=DrumLibrary(folder)
        library.sounds={'test-kick':{'id':'test-kick'}}
        d=library.save(document())
        client=Mock();client.command.return_value={'status':'sent','confirmed':False}
        drums=StudioDrums(client,library);drums.loaded=True
        index=next(b['pattern'] for b in library.catalog() if b['id']==d['id'])
        drums.start(137,{'pattern':index,'volume':.2})
        return drums,client,library

    def test_long_run_300_twelve_bar_cycles_no_accumulated_phase_error(self):
        with tempfile.TemporaryDirectory() as folder:
            drums,client,_=self.setup_drums(folder)
            # Irregular worker visits, representing six thousand seconds at 137 BPM.
            observed=[]
            for beat in range(48*300):
                drums.advance(beat+.002)
                count=drums.hits_sent
                drums.advance(beat+.13)
                self.assertEqual(drums.hits_sent,count)
                observed.append(count)
            self.assertEqual(observed,list(range(1,14401)))
            self.assertFalse(any(c.args[0]=='play' for c in client.command.call_args_list))
            self.assertEqual(drums.dropped,0)

    def test_stall_skips_stale_attacks_stop_and_bar_boundary_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            drums,client,library=self.setup_drums(folder)
            drums.advance(0);drums.advance(10)
            self.assertEqual(drums.hits_sent,2)
            self.assertGreater(drums.dropped,0)
            second=document();second['id']='alternate';second['hits']=[{'lane':'kick','beat':0,'velocity':.8}]
            library.save(second)
            self.assertEqual(drums.select('alternate')['at_beat'],12)
            drums.advance(11);self.assertEqual(drums.document['id'],'test-beat')
            drums.advance(12);self.assertEqual(drums.document['id'],'alternate')
            self.assertEqual(client.command.call_args.args,('note-on',.8,36))
            drums.stop();count=drums.hits_sent;drums.advance(60)
            self.assertEqual(drums.hits_sent,count)
            self.assertEqual(client.command.call_args.args,('mute',))

    def test_swing_probability_gain_and_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            drums,client,library=self.setup_drums(folder)
            d=document();d['swing']=.4;d['lanes'][0]['gain']=.5
            d['hits']=[{'lane':'kick','beat':.25,'velocity':.8},{'lane':'kick','beat':1,'probability':0}]
            library.save(d);drums.running=False;drums.select(d['id']);drums.running=True
            drums.advance(.25);self.assertEqual(drums.hits_sent,0)
            drums.advance(.351);self.assertEqual(client.command.call_args.args,('note-on',.4,36))
            drums.advance(1);self.assertEqual(drums.hits_sent,1)
            recalled=DrumLibrary(folder).get(d['id'])
            self.assertEqual(recalled['swing'],.4)

    def test_invalid_document_does_not_replace_saved_beat(self):
        with tempfile.TemporaryDirectory() as folder:
            _,_,library=self.setup_drums(folder);original=library.get('test-beat')
            for change in ({'bars':0},{'swing':float('nan')},{'hits':[{'lane':'unknown','beat':0}]},
                           {'hits':[{'lane':'kick','beat':48}]},{'id':'../escape'}):
                with self.assertRaises(ValueError):library.save({**original,**change})
                self.assertEqual(library.get('test-beat'),original)

    def test_even_loop_lengths_crop_repeat_and_preserve_source(self):
        with tempfile.TemporaryDirectory() as folder:
            drums,client,library=self.setup_drums(folder)
            original=library.get('test-beat');drums.stop()
            for bars in (2,6,12,14,32,64):
                drums.set_length(bars,'test-beat')
                self.assertEqual(drums.document['bars'],bars)
                self.assertEqual([h['beat'] for h in drums.document['hits']],list(range(bars*4)))
                self.assertEqual(library.get('test-beat'),original)
            for bars in (0,1,3,65,2.5,True):
                with self.assertRaises(ValueError):drums.set_length(bars)
                self.assertEqual(drums.loop_bars,64)
            drums.set_length(None)
            self.assertEqual(drums.document,original)

    def test_length_switch_queues_and_loops_exactly_at_new_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            drums,client,_=self.setup_drums(folder)
            drums.advance(0)
            self.assertEqual(drums.set_length(2)['at_beat'],4)
            self.assertEqual(drums.snapshot()['bars'],12)
            self.assertEqual(drums.snapshot()['pending_bars'],2)
            for beat in range(1,29):drums.advance(beat)
            self.assertEqual(drums.hits_sent,29)
            self.assertEqual(drums.document['bars'],2)
            self.assertEqual(drums.anchor,4)
            self.assertEqual(drums.dropped,0)

    def test_api_drum_length_survives_session_recall(self):
        from orchid_studio.api import Controller
        with tempfile.TemporaryDirectory() as folder:
            _,client,library=self.setup_drums(folder)
            c=Controller(Mock(),Mock(),drums=client,drum_library=library)
            try:
                c.selected_beat='test-beat'
                self.assertEqual(c.execute({'command':'drums-length','bars':32})['status'],'ok')
                saved=c.execute({'command':'loop-export'})['document']
                self.assertEqual(saved['drums']['loop_bars'],32)
                c.execute({'command':'drums-length','bars':2})
                self.assertEqual(c.execute({'command':'loop-import','document':saved})['status'],'ok')
                self.assertEqual(c.transport.drums.document['bars'],32)
                bad=copy.deepcopy(saved);bad['drums']['loop_bars']=3
                self.assertEqual(c.execute({'command':'loop-import','document':bad})['status'],'error')
                self.assertEqual(c.transport.drums.loop_bars,32)
            finally:c.close()

    def test_sample_upload_kit_mapping_and_archive_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            library=DrumLibrary(folder);buf=io.BytesIO()
            with wave.open(buf,'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\0\0'*441)
            kit=library.upload('Click',base64.b64encode(buf.getvalue()).decode(),'CC0')
            self.assertEqual(kit['license'],'CC0');self.assertEqual(len(library.sounds),1)
            sound=next(iter(library.sounds.values()))
            self.assertIn('/assets/',sound['instrument'])
            archive=Path(folder)/'bad.h2drumkit'
            with tarfile.open(archive,'w:gz') as tar:
                info=tarfile.TarInfo('../escape');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):library.import_kit(archive)
            self.assertEqual(len(library.sounds),1)

    def test_clip_ticks_share_midi_origin_and_do_not_fire_end_boundary(self):
        now=[100.];notes=[];ticks=[]
        def sleep(delta):now[0]+=delta
        player=Player(lambda m:notes.append((now[0],m)),{0},clock=lambda:now[0],sleep=sleep)
        player.play([Event(0,(0x90,60,60),'a'),Event(1,(0x80,60,0),'a')],120,4,tick=ticks.append)
        self.assertEqual(notes[0][0],100.)
        self.assertAlmostEqual(notes[1][0],100.5)
        self.assertEqual(ticks[0],0)
        self.assertTrue(all(0<=t<4 for t in ticks))
        self.assertGreater(len(ticks),500)

class NativeBackendTests(unittest.TestCase):
    def test_native_load_hits_and_volume_never_start_hydrogen(self):
        from orchid_studio.drum_audio import NativeDrumAudio
        with tempfile.TemporaryDirectory() as folder:
            library=DrumLibrary(folder)
            library.ensure_stock=Mock()
            library.sounds={'hit':{'id':'hit','name':'Hit','kit':'local','instrument':'<instrument><volume>0.5</volume><filename>/tmp/hit.wav</filename></instrument>'}}
            router=Mock();router.host.error=None;backend=NativeDrumAudio(router,library)
            self.assertEqual(backend.load()['engine'],'studio-native')
            spec=router.host.call.call_args.kwargs['sounds'][0]
            self.assertEqual(spec['gain'],.5)
            backend.command('note-on',.4,36)
            router.host.call.assert_called_with('drum-hit',sound='hit',velocity=.4,wait=False)
            backend.command('mute');router.host.call.assert_called_with('drum-volume',volume=0)
            backend.command('volume',.5);router.host.call.assert_called_with('drum-volume',volume=0)
            backend.command('unmute');router.host.call.assert_called_with('drum-volume',volume=.5)
            with self.assertRaises(ValueError):backend.command('play')

    def test_native_rejects_unsupported_kit_before_replacing_audio_bank(self):
        from orchid_studio.drum_audio import NativeDrumAudio
        with tempfile.TemporaryDirectory() as folder:
            library=DrumLibrary(folder);library.ensure_stock=Mock()
            library.sounds={'hit':{'id':'hit','name':'Hit','instrument':'<instrument><layer><filename>/tmp/a.wav</filename></layer><layer><filename>/tmp/b.wav</filename></layer></instrument>'}}
            router=Mock();router.host.error=None;backend=NativeDrumAudio(router,library)
            with self.assertRaises(ValueError):backend.load()
            router.host.call.assert_not_called()

    def test_api_kit_failure_rolls_back_library_and_native_bank(self):
        from orchid_studio.api import Controller
        with tempfile.TemporaryDirectory() as folder:
            library=DrumLibrary(folder);library.ensure_stock=Mock()
            c=Controller(lambda m:None,lambda e:None,drums=Mock(),drum_library=library)
            c.transport.drums.load=Mock(side_effect=ValueError('unsupported format'))
            def fail_import(path):
                library.sounds['bad']={'id':'bad'};library.kits.append({'id':'bad'})
                return {'id':'bad'}
            library.import_kit=fail_import
            result=c.execute({'command':'kits-import','path':'/tmp/test'})
            self.assertEqual(result['status'],'error')
            self.assertEqual(library.sounds,{})
            self.assertEqual(DrumLibrary(folder).sounds,{})
            c.close()
