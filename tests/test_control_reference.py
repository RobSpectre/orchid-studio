import copy
import unittest
from unittest.mock import Mock
from orchid_studio.api import Controller, COMMANDS
from orchid_studio.control_reference import reference, UI_MAP, BEAT_EDITOR
from orchid_studio.beat_edit import edit, ACTIONS
from orchid_studio.catalog import sounds
from orchid_studio.perform import options


class ControlReferenceTests(unittest.TestCase):
    def test_discovery_covers_commands_modes_patterns_and_every_ui_group(self):
        self.assertEqual(set(reference()),set(COMMANDS))
        self.assertEqual(set(BEAT_EDITOR['actions']),set(ACTIONS))
        for group in UI_MAP.values():self.assertTrue(set(group['commands'])<=set(COMMANDS))
        o=options();self.assertEqual(set(o['mode_map']),set(o['modes']))
        self.assertEqual(set(o['pattern_descriptions']),set(o['patterns']))
        entries=sounds()['sounds'];self.assertEqual([x['number'] for x in entries],list(range(1,101)))
        self.assertTrue(all(x['description'] and x['description_basis'] for x in entries))
        self.assertEqual(sum(x['kind']=='factory' for x in entries),70)

    def test_api_discovery_and_sound_follow_does_not_disable_playalong(self):
        c=Controller(Mock(),Mock());c.play_along.stop=Mock()
        try:
            self.assertEqual(set(c.execute({'command':'command-help'})['commands']),set(COMMANDS))
            self.assertEqual(list(c.execute({'command':'command-help','name':'layer-preset'})['commands']),['layer-preset'])
            self.assertEqual(c.execute({'command':'command-help','name':'unknown'})['status'],'error')
            self.assertEqual(len(c.execute({'command':'sounds-list'})['sounds']),100)
            self.assertEqual(c.execute({'command':'sound-follow','enabled':False})['status'],'ok')
            c.play_along.stop.assert_not_called()
        finally:c.close()

    def test_per_layer_sound_change_targets_only_requested_au(self):
        c=Controller(Mock(),Mock());c.sounds.host=Mock();c.sounds.host.error=None
        c.sounds.host.process.poll.return_value=None
        try:
            c.execute({'command':'loop-step','slot':2,'beat':0,'notes':[60,64]})
            before=copy.deepcopy(c.transport.looper.layers);labels=list(c.sounds.labels)
            self.assertEqual(c.execute({'command':'layer-preset','slot':2,'preset':13})['status'],'ok')
            c.sounds.host.call.assert_called_once_with('sound',slot=2,message=[176,102,12])
            self.assertEqual(c.transport.looper.layers,before)
            self.assertEqual(c.sounds.labels[1],'Sound 013')
            self.assertEqual(c.sounds.labels[:1]+c.sounds.labels[2:],labels[:1]+labels[2:])
        finally:c.close()


class BeatEditTests(unittest.TestCase):
    def setUp(self):
        self.sounds={'kick':{},'hat':{}}
        self.doc={'kind':'orchid-beat','version':1,'id':'source','name':'Source','bars':2,'lanes':[{'id':'kick','name':'Kick','sound':'kick'}],
                  'hits':[{'lane':'kick','beat':.1,'velocity':.6,'probability':.8},{'lane':'kick','beat':5,'velocity':.7}]}
    def run_edit(self,action,document=None,**kwargs):return edit(document or self.doc,{'action':action,**kwargs},self.sounds)
    def test_clone_new_resize_copy_repeat_and_undo_do_not_mutate_source(self):
        before=copy.deepcopy(self.doc)
        clone=self.run_edit('clone',new_id='copy',name='Copy');self.assertFalse(clone['saved'])
        self.assertEqual(clone['document']['id'],'copy');self.assertEqual(clone['undo_document']['id'],'source')
        self.assertEqual(self.run_edit('new',new_id='blank',name='Blank')['document']['hits'],[])
        resized=self.run_edit('resize',bars=4)['document'];self.assertEqual([h['beat'] for h in resized['hits']],[.1,5,8.1,13])
        copied=self.run_edit('copy-bar',bar=1,target_bar=2)['document'];self.assertEqual([h['beat'] for h in copied['hits']],[.1,4.1])
        self.assertEqual(self.run_edit('repeat-bar',bar=1)['document']['hits'],copied['hits'])
        self.assertEqual(self.doc,before)
    def test_step_toggle_accent_set_remove_and_lane_changes(self):
        accented=self.run_edit('step',lane='kick',bar=1,step=1,mode='accent')['document']
        self.assertEqual(accented['hits'][0]['beat'],.1);self.assertEqual(accented['hits'][0]['velocity'],.9)
        removed=self.run_edit('step',lane='kick',bar=1,step=1)['document']
        self.assertEqual(len(removed['hits']),1)
        added=self.run_edit('step',lane='kick',bar=2,step=16,mode='set',velocity=.3,probability=.4)['document']
        self.assertEqual(added['hits'][-1],{'lane':'kick','beat':7.75,'velocity':.3,'probability':.4})
        lane=self.run_edit('lane-set',lane='kick',settings={'muted':True,'sound':'hat'})['document']['lanes'][0]
        self.assertTrue(lane['muted']);self.assertEqual(lane['sound'],'hat')
        self.assertEqual(len(self.run_edit('clear-bar',bar=1)['document']['hits']),1)
        for kwargs in ({'bar':0,'step':1,'lane':'kick'},{'bar':1,'step':17,'lane':'kick'},{'bar':1,'step':1,'lane':'missing'}):
            with self.assertRaises(ValueError):self.run_edit('step',**kwargs)
    def test_api_draft_does_not_publish(self):
        c=Controller(Mock(),Mock())
        try:
            original=c.execute({'command':'beat-get','beat':'glass-house'})['document']
            # Beat edits need sound IDs, not the developer's locally installed audio.
            c.library.sounds={lane['sound']:{} for lane in original['lanes']}
            r=c.execute({'command':'beat-edit','beat':'glass-house','action':'clear-bar','bar':1})
            self.assertEqual(r['status'],'ok');self.assertFalse(r['saved'])
            self.assertTrue(all(h['beat']>=4 for h in r['document']['hits']))
            self.assertEqual(c.execute({'command':'beat-get','beat':'glass-house'})['document'],original)
        finally:c.close()
