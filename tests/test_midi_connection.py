import unittest
from unittest.mock import Mock
from orchid_studio.midi_connection import MidiConnection


class ConnectionTests(unittest.TestCase):
    def test_disconnect_reconnect_and_no_confusion_with_virtual_ports(self):
        inventory=Mock(return_value={'available':True,'inputs':['Orchid Studio Playback','Orchid Studio Clock']})
        connection=MidiConnection(inventory)
        self.assertIsNone(connection.snapshot()['connected'])
        connection.refresh();self.assertFalse(connection.snapshot()['connected'])
        inventory.return_value={'available':True,'inputs':['Orchid']}
        connection.refresh();self.assertTrue(connection.snapshot()['connected'])
        inventory.return_value={'available':True,'inputs':[]}
        connection.refresh();self.assertFalse(connection.snapshot()['connected'])

    def test_failure_and_stale_data_are_unknown_not_false_connected(self):
        now=[1.0];inventory=Mock(return_value={'available':True,'inputs':['Orchid USB']})
        connection=MidiConnection(inventory,lambda:now[0]);connection.refresh()
        self.assertTrue(connection.snapshot('Orchid USB')['connected'])
        now[0]=5;self.assertIsNone(connection.snapshot('Orchid USB')['connected'])
        inventory.return_value={'available':True,'inputs':[],'inputs_error':'CoreMIDI unavailable'}
        connection.refresh();s=connection.snapshot();self.assertIsNone(s['connected']);self.assertEqual(s['error'],'CoreMIDI unavailable')
        inventory.side_effect=RuntimeError('offline');connection.refresh()
        self.assertIsNone(connection.snapshot()['connected'])

    def test_status_reports_connection_independently_of_transport(self):
        from orchid_studio.api import Controller
        controller=Controller(Mock(),Mock())
        controller.midi_connection=MidiConnection(lambda:{'available':True,'inputs':['Orchid']})
        controller.midi_connection.refresh()
        try:
            s=controller.execute({'command':'status'})
            self.assertFalse(s['playing']);self.assertTrue(s['orchid_connection']['connected'])
        finally:controller.close()
