import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from orchid_studio.api import Controller
from orchid_studio.drum_library import DrumLibrary
from test_pistil_host import host


class MixerAutomationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.c = Controller(Mock(), Mock(), drum_library=DrumLibrary(folder.name))
        self.c.sounds.host = host()
        self.c.transport.drums = Mock()
        self.c.transport.drums.command.return_value = {'status': 'ok'}
        self.c.sounds.recovery_path = Path(folder.name) / 'recovery.json'
        self.now = 0
        self.c.mixer.clock = lambda: self.now
        self.c.mixer.worker = Mock()  # Advance the same worker logic with a deterministic clock.
        self.addCleanup(self.c.close)

    def command(self, name='mixer-set', **fields):
        result = self.c.execute({'command': name, **fields})
        self.assertIn(result['status'], ('ok', 'queued'), result)
        return result

    def advance(self, now):
        self.now = now
        with self.c.lock:
            self.c.mixer.advance()

    def test_get_schema_and_batch_validation_do_not_touch_audio(self):
        before = copy.deepcopy(self.c.sounds.mix)
        result = self.command('mixer-get')
        self.assertEqual(result['mixer'], before)
        result['mixer']['live']['volume'] = 0
        schema = self.command('capabilities')['mixer_schema']
        self.assertEqual(set(schema['channels']), set(before))
        self.c.sounds.host.call.assert_not_called()
        invalid = [
            {'channels': {'live': {'volume': .2}, 'drums': {'pan': 2}}},
            {'channels': {}}, {'channels': {'live': {}}},
            {'channels': {'live': {'mute': True}}},
            {'channel': 'master', 'volume': 1},
            {'channel': 'live', 'volume': True},
            {'channel': 'live', 'pan': float('nan')},
            {'channel': 'live', 'volume': .5, 'transition_seconds': -1},
            {'channel': 'live', 'volume': .5, 'transition_seconds': 121},
            {'channel': 'live', 'volume': .5, 'curve': 'unknown'},
            {'channel': 'live', 'channels': {'live': {'volume': .5}}},
        ]
        for fields in invalid:
            with self.subTest(fields=fields):
                self.assertEqual(self.c.execute({'command': 'mixer-set', **fields})['status'], 'error')
                self.assertEqual(self.c.sounds.mix, before)
        self.c.sounds.host.call.assert_not_called()
        self.assertFalse(self.c.mixer.jobs)

    def test_crossfade_and_pan_sweep_share_timing_and_finish_exactly(self):
        self.command(channels={'layer-1': {'volume': .8}, 'layer-2': {'volume': 0}})
        before = copy.deepcopy(self.c.sounds.mix)
        result = self.command(channels={'layer-1': {'volume': 0}, 'layer-2': {'volume': .8, 'pan': 1}},
                              transition_seconds=4)
        self.assertEqual(result['status'], 'queued')
        self.assertFalse(self.c.transport.playing)
        self.advance(2)
        self.assertEqual(self.c.sounds.mix['layer-1']['volume'], .4)
        self.assertEqual(self.c.sounds.mix['layer-2'], {'volume': .4, 'pan': .5})
        self.assertEqual(self.c.sounds.mix['live'], before['live'])
        self.assertEqual(self.c.mixer.snapshot()['channels']['layer-1']['progress'], .5)
        self.advance(5)
        self.assertEqual(self.c.sounds.mix['layer-1']['volume'], 0)
        self.assertEqual(self.c.sounds.mix['layer-2'], {'volume': .8, 'pan': 1})
        self.assertFalse(self.c.mixer.jobs)
        self.assertEqual(self.c.events[-1]['event'], 'mixer_transition_completed')

    def test_smoothstep_retarget_manual_override_and_cancel_preserve_current_values(self):
        self.command(channels={'live': {'volume': 0}, 'layer-1': {'volume': 0}},
                     transition_seconds=4, curve='smoothstep')
        self.advance(1)
        self.assertAlmostEqual(self.c.sounds.mix['live']['volume'], .84375)
        self.command(channel='live', volume=.5, transition_seconds=2)
        self.advance(2)
        self.assertAlmostEqual(self.c.sounds.mix['live']['volume'], (.84375 + .5) / 2)
        self.command(channel='live', pan=-.5)
        self.assertNotIn('live', self.c.mixer.jobs)
        self.assertIn('layer-1', self.c.mixer.jobs)
        before = copy.deepcopy(self.c.sounds.mix)
        result = self.command('mixer-cancel', channels=['layer-1'])
        self.assertEqual(result['cancelled'], ['layer-1'])
        self.advance(20)
        self.assertEqual(self.c.sounds.mix, before)

    def test_invalid_commands_do_not_interrupt_existing_fade(self):
        self.command(channel='live', volume=0, transition_seconds=5)
        original = self.c.mixer.snapshot()
        self.assertEqual(self.c.execute({'command':'mixer-set','channel':'live','volume':2})['status'], 'error')
        self.assertEqual(self.c.execute({'command':'mixer-cancel','channels':['live','bad']})['status'], 'error')
        self.assertEqual(self.c.mixer.snapshot(), original)

    def test_drums_stay_in_sync_and_legacy_volume_cancels_their_fade(self):
        self.command(channels={'drums': {'volume': .9, 'pan': -.5}, 'live': {'volume': .2}}, transition_seconds=2)
        self.advance(1)
        self.assertAlmostEqual(self.c.sounds.mix['drums']['volume'], .6)
        self.assertAlmostEqual(self.c.drum_state['volume'], .6)
        self.c.transport.drums.command.assert_called_with('volume', self.c.drum_state['volume'])
        self.c.sounds.host.call.assert_any_call('mix', target='drums', slot=5,
                                              volume=self.c.drum_state['volume'], pan=-.25)
        self.command('drums', action='volume', value=.4)
        self.advance(2)
        self.assertEqual(self.c.sounds.mix['drums']['volume'], .4)
        self.assertEqual(self.c.sounds.mix['live']['volume'], .2)

    def test_pause_continues_fades_stop_panic_cancel_and_error_is_visible(self):
        self.c.transport.worker = Mock()
        self.c.transport.worker.is_alive.return_value = True
        self.c.transport.timeline.reset(96)
        self.command(channel='play-along', volume=0, transition_seconds=2)
        self.command('pause')
        self.advance(1)
        self.assertEqual(self.c.sounds.mix['play-along']['volume'], .5)
        self.command('stop')
        self.advance(3)
        self.assertEqual(self.c.sounds.mix['play-along']['volume'], .5)
        self.command(channel='play-along', volume=1, transition_seconds=2)
        self.command('panic')
        self.assertFalse(self.c.mixer.jobs)
        self.command(channel='play-along', volume=1, transition_seconds=2)
        self.c.sounds.host.error = 'disconnected'
        self.advance(4)
        snapshot = self.command('mixer-get')['mixer_automation']
        self.assertFalse(snapshot['active'])
        self.assertIn('unavailable', snapshot['error'])
        self.assertEqual(self.c.events[-1]['event'], 'mixer_error')

    def test_real_worker_completes_without_api_polling_or_transport(self):
        self.c.mixer.worker = None
        self.c.mixer.clock = time.monotonic
        self.command(channel='live', volume=.25, transition_seconds=.05)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with self.c.lock:
                if not self.c.mixer.jobs:
                    break
            time.sleep(.01)
        with self.c.lock:
            self.assertFalse(self.c.mixer.jobs)
            self.assertEqual(self.c.sounds.mix['live']['volume'], .25)
        self.c.close()
        self.assertFalse(self.c.mixer.worker.is_alive())

    def test_scene_restore_cancels_fades_and_export_saves_only_applied_values(self):
        self.command(channel='live', volume=.4)
        document = self.command('loop-export')['document']
        self.command(channel='live', volume=0, transition_seconds=2)
        self.advance(1)
        midway = self.command('loop-export')['document']
        self.assertEqual(midway['instruments']['mixer']['live']['volume'], .2)
        self.command('loop-import', document=document)
        self.advance(3)
        self.assertFalse(self.c.mixer.jobs)
        self.assertEqual(self.c.sounds.mix['live']['volume'], .4)
