import base64
import copy
import plistlib
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from orchid_studio.api import Controller
from orchid_studio.looper import LayerVoices
from orchid_studio.pistil_host import SoundRouter, validate_states


def state(value):
    return base64.b64encode(plistlib.dumps({'manufacturer':int.from_bytes(b'Tptp','big'),
        'subtype':int.from_bytes(b'Pitl','big'),'data':bytes([value])})).decode()


def host():
    h=Mock();h.error=None;h.process.poll.return_value=None;h.states=[state(i) for i in range(4)]
    def call(command,**kwargs):
        if command=='capture':return {'states':list(h.states)}
        if command=='restore':h.states=list(kwargs['states'])
        return {'status':'ok'}
    h.call.side_effect=call
    return h


class InstrumentTests(unittest.TestCase):
    def test_sound_dial_routes_selected_layer_and_playalong_and_latches_pair(self):
        fallback=Mock();r=SoundRouter(fallback);r.host=host();r.select(2)
        r.sound([176,102,50]);r.select(3)
        report=[240,0,34,12,52]+[50]+[0]*135+[247]
        self.assertEqual(len(report),142)
        r.sound(report)
        self.assertEqual([c.kwargs['slot'] for c in r.host.call.call_args_list],[2,6,2,6])
        self.assertEqual(r.labels,['Pistil','Sound 051','Pistil','Pistil','Pistil','Sound 051'])
        fallback.assert_not_called()
        with self.assertRaises(ValueError):r.sound([0xF8])

    def test_six_voice_capture_and_legacy_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            r=SoundRouter(Mock());r.host=host();r.recovery_path=Path(directory)/'state.json'
            legacy={'format':'pistil-au-v2','selected_slot':5,'states':[state(i) for i in range(5)],'labels':['Pistil']*5}
            r.restore(legacy)
            self.assertEqual(len(r.labels),6)
            r.host.states=[state(i) for i in range(6)]
            r.select(6);doc=r.capture();self.assertEqual(doc['format'],'pistil-au-v3')
            self.assertEqual(len(doc['states']),6);r.validate(doc)
            r.set_mix('play-along',{'volume':.6,'pan':.2})
            r.host.call.assert_called_with('mix',target='play-along',slot=6,volume=.6,pan=.2)
            r.host.call.reset_mock();r.sound([176,102,50])
            self.assertEqual([c.kwargs['slot'] for c in r.host.call.call_args_list],[6])

    def test_same_pitch_in_two_layers_has_independent_lifetime(self):
        r=SoundRouter(Mock());r.host=host();bus=LayerVoices(r)
        bus.receive(0,[144,60,64]);bus.receive(1,[144,60,72]);bus.release(0)
        calls=r.host.call.call_args_list
        self.assertEqual([(c.kwargs['slot'],c.kwargs['message'][0]) for c in calls],[(1,144),(2,144),(1,128)])
        r.select(2);bus.receive('monitor',[144,60,64]);bus.release('monitor')
        self.assertEqual(len(r.host.call.call_args_list),5) # Live channel has its own note lifetime.
        self.assertEqual(r.host.call.call_args_list[-1].kwargs['slot'],5)
        bus.panic()
        self.assertTrue(any(c.kwargs.get('slot')==2 and c.kwargs.get('message')==[128,60,0] for c in r.host.call.call_args_list))

    def test_state_validation_and_atomic_loop_import(self):
        c=Controller(Mock(),Mock());c.sounds.host=host()
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        c.sounds.recovery_path=Path(folder.name)/"recovery.json"
        try:
            self.assertEqual(c.execute({'command':'loop-step','slot':1,'beat':0,'notes':[60]})['status'],'ok')
            saved=c.execute({'command':'loop-export'})['document']
            self.assertIn('instruments',saved)
            c.sounds.host.states=[state(i+10) for i in range(4)]
            self.assertEqual(c.execute({'command':'loop-import','document':saved})['status'],'ok')
            self.assertEqual(c.execute({'command':'loop-export'})['document'],saved)
            before=copy.deepcopy(saved)
            for bad in ('not base64',base64.b64encode(plistlib.dumps({'manufacturer':0,'subtype':0})).decode()):
                invalid=copy.deepcopy(saved);invalid['instruments']['states'][0]=bad
                self.assertEqual(c.execute({'command':'loop-import','document':invalid})['status'],'error')
                self.assertEqual(c.execute({'command':'loop-export'})['document'],before)
            invalid=copy.deepcopy(saved);invalid['layers'][0]['chords'][0]['note']=900
            self.assertEqual(c.execute({'command':'loop-import','document':invalid})['status'],'error')
            self.assertEqual(c.execute({'command':'loop-export'})['document'],before)
        finally:c.close()

    def test_import_with_sounds_requires_host_and_never_discards_existing_notes(self):
        c=Controller(Mock(),Mock())
        try:
            c.execute({'command':'loop-step','slot':1,'beat':0,'notes':[60]})
            before=c.execute({'command':'loop-export'})['document']
            doc=copy.deepcopy(before);doc['instruments']={'format':'pistil-au-v1','selected_slot':1,'labels':['Pistil']*4,'states':[state(i) for i in range(4)]}
            self.assertEqual(c.execute({'command':'loop-import','document':doc})['status'],'error')
            self.assertEqual(c.execute({'command':'loop-export'})['document'],before)
        finally:c.close()

    def test_standalone_fallback_and_idempotent_selected_layer(self):
        fallback=Mock();r=SoundRouter(fallback);r.sound([176,102,50]);r.send([144,60,50])
        self.assertEqual(fallback.call_count,2)
        c=Controller(Mock(),Mock())
        c.transport.looper.bus=Mock()
        try:
            c.execute({'command':'layer-select','slot':1})
            c.transport.looper.bus.release.assert_not_called()
            c.execute({'command':'layer-select','slot':2})
            c.transport.looper.bus.release.assert_called_once_with('monitor')
        finally:c.close()

    def test_dead_host_enable_recreates_and_restores_checkpoint(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            r=SoundRouter(Mock());r.recovery_path=Path(folder)/'recovery.json'
            old=host();r.host=old;saved=r.capture()
            old.error='host exited';old.process.poll.return_value=-9
            new=host()
            with patch('orchid_studio.pistil_host.NativeHost',return_value=new):
                self.assertTrue(r.enable('/mock/host'))
            old.close.assert_called_once()
            new.call.assert_any_call('restore',states=saved['states'])
            self.assertEqual(r.capture(),saved)
            self.assertFalse(r.enable('/mock/host'))
