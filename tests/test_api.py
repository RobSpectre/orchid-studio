import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from orchid_studio.api import Controller, HttpAPI
from orchid_studio.drum_library import DrumLibrary
from orchid_studio.api_client import request
from orchid_studio.beats import catalog, patterns
from orchid_studio.drum_song import write_electronic_song, validate_beat_bank
from orchid_studio.perform import DEFAULTS, settings


def make_bank(folder):
    voices = sorted({n['instrument'] for p in patterns() for n in p['notes']})
    kit = Path(folder) / 'drumkit.xml'
    kit.write_text('<drumkit_info><name>Test</name><instrumentList>' + ''.join(
        f'<instrument><id>{i}</id><name>{v}</name></instrument>' for i, v in enumerate(voices)) +
        '</instrumentList></drumkit_info>')
    song = Path(folder) / 'electronic.h2song'
    write_electronic_song(song, folder)
    return song


class BeatBankTests(unittest.TestCase):
    def test_twelve_distinct_twelve_bar_arrangements_have_variations_and_balanced_hits(self):
        bank = patterns()
        self.assertEqual(len(bank), 12)
        from collections import Counter
        self.assertEqual(Counter(b['genre'] for b in catalog()), {'drum-and-bass': 4, 'house': 4, 'trance': 4})
        self.assertTrue(all(b['kit'] == 'TR808EmulationKit' for b in catalog()))
        self.assertEqual(len({b['id'] for b in catalog()}), 12)
        self.assertEqual(len({json.dumps(p['notes']) for p in bank}), 12)
        for p in bank:
            with self.subTest(pattern=p['name']):
                self.assertEqual(p['size'], 48 * 48)
                self.assertTrue(all(0 <= n['position'] < p['size'] and 0 < n['velocity'] <= .8 for n in p['notes']))
                self.assertEqual(len({(n['position'], n['instrument']) for n in p['notes']}), len(p['notes']))
                self.assertEqual({n['position'] // 192 for n in p['notes']}, set(range(12)))
                phrases = [{(n['position'] % 384, n['instrument'], n['velocity']) for n in p['notes']
                            if n['position'] // 384 == i} for i in range(6)]
                self.assertNotEqual(phrases[0], phrases[1])
                self.assertNotEqual(phrases[4], phrases[5])
        self.assertTrue(all(b['bars'] == 12 and b['length_beats'] == 48 for b in catalog()))

    def test_arrangements_exclude_tuned_accents_and_use_quiet_grid_aligned_fills(self):
        core = {"Kick Short", "Kick Long", "Snare 1", "Snare 2", "Clap", "Closed Hat", "Open Hat"}
        for pattern in patterns():
            with self.subTest(pattern=pattern["name"]):
                self.assertLessEqual({n["instrument"] for n in pattern["notes"]}, core)
                for phrase in (3, 5):
                    fills = [n for n in pattern["notes"] if n["instrument"] == "Snare 2"
                             and phrase * 384 + 360 <= n["position"] < (phrase + 1) * 384]
                    self.assertEqual(len(fills), 2)
                    self.assertTrue(all(n["position"] % 12 == 0 and n["velocity"] <= .20 for n in fills))

    def test_song_xml_matches_catalog_and_disables_midi_output(self):
        with tempfile.TemporaryDirectory() as folder:
            song = make_bank(folder)
            self.assertEqual(validate_beat_bank(song), str(song.resolve()))
            root = ET.parse(song).getroot()
            self.assertEqual([p.findtext('name') for p in root.findall('patternList/pattern')], [b['name'] for b in catalog()])
            self.assertTrue(all(p.findtext('size') == '2304' for p in root.findall('patternList/pattern')))
            self.assertTrue(all(i.findtext('midiOutChannel') == '-1' for i in root.findall('instrumentList/instrument')))
            root.find('patternList/pattern/size').text = '384'
            ET.ElementTree(root).write(song)
            with self.assertRaises(ValueError):
                validate_beat_bank(song)


class APITests(unittest.TestCase):
    def controller(self, **kwargs):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        library=DrumLibrary(folder.name)
        library.kits=[{'id':'tr808emulationkit'}]
        for d in library.documents.values():
            for lane in d['lanes']:
                library.sounds[lane['sound']]={'id':lane['sound'],'name':lane['name'],
                                              'instrument':'<instrument><id>0</id></instrument>'}
        return Controller(lambda m: None, lambda e: None, drum_library=library, **kwargs)

    def test_every_setting_discoverable_and_configurable_without_midi(self):
        c = self.controller()
        schema = c.execute({'command': 'capabilities'})['settings_schema']['properties']
        self.assertEqual(set(schema), set(DEFAULTS))
        alternate = dict(bpm=84, mode='harp', step_beats=1, gate=.5, velocity_limit=64,
                         spread_beats=.75, harp_octaves=4, slop=.6, seed=42,
                         pattern='shuffle', chord_window_ms=12)
        self.assertEqual(c.execute({'command': 'perform-configure', 'settings': alternate})['settings'], settings(alternate))
        previous = c.snapshot()['performance_defaults']
        self.assertEqual(c.execute({'command': 'perform-configure', 'settings': {'bpm': -1}})['status'], 'error')
        self.assertEqual(c.snapshot()['performance_defaults'], previous)

    def test_live_updates_apply_all_fields_and_leave_routing_isolated(self):
        c = self.controller()
        source = Mock()
        source.get_ports.return_value = ['Orchid']
        source.get_message.return_value = None
        with patch('orchid_studio.perform.backend') as backend:
            backend.return_value.MidiIn.return_value = source
            try:
                response = c.execute({'command': 'perform', 'input': 'Orchid', 'chord_channel': 3})
                self.assertEqual(response['status'], 'ok')
                updated = dict(bpm=88, mode='harp', pattern='falling', harp_octaves=4,
                               step_beats=1, gate=.6, velocity_limit=72, spread_beats=.75,
                               slop=.8, seed=19, chord_window_ms=12)
                self.assertEqual(c.execute({'command': 'perform-update', 'settings': updated})['status'], 'queued')
                deadline = time.monotonic() + 1
                while any(c.transport.live.config[k]!=v for k,v in updated.items() if k!='bpm') and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertEqual(c.snapshot()['performance']['settings'], updated)
                self.assertEqual(c.snapshot()['performance']['chord_channel'], 3)
                self.assertIn('perform_updated', [e['event'] for e in c.execute({'command': 'events'})['events']])
                backend.return_value.MidiOut.assert_not_called()
            finally:
                c.close()
        source.close_port.assert_called_once()

    def test_named_beats_require_bank_and_preserve_tempo_on_selection(self):
        drums = Mock()
        drums.command.return_value = {'status': 'sent', 'confirmed': False}
        with tempfile.TemporaryDirectory() as folder:
            c = self.controller(drums=drums, drum_bank=make_bank(folder))
            self.assertEqual(c.execute({'command': 'beats-select', 'beat': 'liquid-circuit'})['status'], 'error')
            self.assertEqual(c.execute({'command': 'beats-load'})['status'], 'sent')
            drums.command.reset_mock()
            self.assertEqual(c.execute({'command': 'beats-select', 'beat': 'daybreak-rush'})['beat']['pattern'], 11)
            drums.command.assert_not_called()
            self.assertEqual(c.transport.drums.document['id'], 'daybreak-rush')
            c.execute({'command': 'beats-play', 'beat': 'liquid-circuit', 'bpm': 78, 'volume': .2})
            deadline=time.monotonic()+1
            while c.transport.drums.hits_sent == 0 and time.monotonic()<deadline: time.sleep(.005)
            self.assertGreater(c.transport.drums.hits_sent,0)
            self.assertFalse(any(call.args[0]=='play' for call in drums.command.call_args_list))
            self.assertEqual(c.execute({'command': 'beats-load'})['status'], 'error')
            c.execute({'command': 'stop'})
            self.assertFalse(c.snapshot()['drums']['playing_requested'])

    def test_unknown_beat_and_invalid_setting_do_not_interrupt_playback(self):
        c = self.controller()
        try:
            c.execute({'command': 'demo'})
            self.assertTrue(c.transport.playing)
            result = c.execute({'command': 'perform', 'input': 'Orchid', 'chord_channel': 3,
                                'drums': {'engine': 'hydrogen', 'beat': 'nonexistent'}})
            self.assertEqual(result['status'], 'error')
            self.assertTrue(c.transport.playing)
            self.assertEqual(c.execute({'command': 'perform', 'input': 'Orchid', 'chord_channel': 3,
                                        'settings': {'mode': 'bad'}})['status'], 'error')
            self.assertTrue(c.transport.playing)
        finally:
            c.close()

    def test_event_cursor_and_bounded_history(self):
        c = self.controller()
        for i in range(300):
            c.report({'event': 'test', 'value': i})
        r = c.execute({'command': 'events', 'after': 0})
        self.assertEqual(len(r['events']), 256)
        self.assertTrue(r['truncated'])
        self.assertEqual(len(c.execute({'command': 'events', 'after': 299})['events']), 1)


class HTTPTests(unittest.TestCase):
    def test_real_http_client_ui_json_validation_and_origin_boundary(self):
        import http.client
        # OS chooses a free loopback port. No hardware MIDI or OSC involved.
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        controller = Controller(lambda m: None, lambda e: None)
        try:
            with HttpAPI(controller, port):
                self.assertEqual(request({'command': 'status'}, port)['status'], 'ok')
                self.assertEqual(request({'command': 'perform-configure', 'settings': {'bpm': 82}}, port)['settings']['bpm'], 82)
                conn = http.client.HTTPConnection('127.0.0.1', port)
                conn.request('GET', '/')
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn(b'Orchid Studio', response.read())
                conn.close()
                for body, extra, expected in [('{}', {'Origin': 'https://example.org'}, 403),
                                               ('{}', {'Host': 'example.org'}, 403),
                                               ('{"command":"status","id":NaN}', {}, 400),
                                               ('[]', {}, 400), ('bad', {}, 400)]:
                    conn = http.client.HTTPConnection('127.0.0.1', port)
                    conn.request('POST', '/command', body, {'Content-Type': 'application/json', **extra})
                    response = conn.getresponse()
                    self.assertEqual(response.status, expected)
                    response.read()
                    conn.close()
        finally:
            controller.close()
