import threading
import unittest
from unittest.mock import Mock, patch

from orchid_studio.perform import Arpeggiator, LivePerformance, settings


class PerformTests(unittest.TestCase):
    def engine(self, **settings):
        sent = []
        return Arpeggiator(sent.append, 3, 1, {"bpm": 120, "chord_window_ms": 0, **settings}), sent

    def chord(self, engine):
        for pitch in (60, 64, 67):
            engine.receive([0x92, pitch, 96])

    def test_raw_channel_only_and_gate(self):
        e, sent = self.engine(gate=.5)
        e.receive([0x90, 40, 90])  # Performed stream must not become a chord.
        e.receive([0x91, 36, 90])  # Bass stays separate.
        self.chord(e)
        e.advance(0)
        e.advance(.125)
        e.advance(.25)
        self.assertEqual(sent, [[144, 60, 80], [128, 60, 0], [144, 64, 80]])

    def test_two_octaves_and_pitch_range(self):
        e, sent = self.engine(mode="arp2")
        self.chord(e)
        for i in range(7):
            e.advance(i * .25)
        self.assertEqual([m[1] for m in sent if m[0] == 144], [60, 64, 67, 72, 76, 79, 60])
        e.receive([146, 125, 96])
        self.assertTrue(all(p <= 127 for p, _ in e.pitches()))

    def test_release_stops_immediately_and_clears_chord(self):
        e, sent = self.engine()
        self.chord(e)
        e.advance(0)
        for p in (60, 64, 67):
            e.receive([130, p, 0])
        self.assertEqual(sent[-1], [128, 60, 0])
        e.advance(1)
        self.assertEqual(len(sent), 2)

    def test_sustain_retains_released_chord_until_pedal_up(self):
        e, sent = self.engine()
        self.chord(e)
        e.receive([178, 64, 127])
        for p in (60, 64, 67):
            e.receive([130, p, 0])
        e.advance(0)
        self.assertEqual(sent[-1], [144, 60, 80])
        e.receive([178, 64, 0])
        self.assertFalse(e.held)
        self.assertEqual(sent[-1], [128, 60, 0])

    def test_software_tempo_change_preserves_phase_and_ignores_hardware_clock(self):
        e, sent = self.engine()
        self.chord(e)
        e.advance(0)
        e.receive([248])
        e.receive([250])
        e.update({"bpm": 60}, .1)  # .2 beats elapsed; next step at .5 beats.
        e.advance(.39)
        self.assertEqual(len([m for m in sent if m[0] == 144]), 1)
        e.advance(.4)
        self.assertEqual(sent[-1], [144, 64, 80])

    def test_scheduler_stall_does_not_burst_notes(self):
        e, sent = self.engine()
        self.chord(e)
        e.advance(0)
        e.advance(4)
        self.assertEqual(len([m for m in sent if m[0] == 144]), 2)

    def test_panic_cleans_generated_notes_and_pedals(self):
        e, sent = self.engine()
        self.chord(e)
        e.advance(0)
        e.panic()
        self.assertEqual(sent[1], [128, 60, 0])
        self.assertEqual(sent[-4:], [[176, cc, 0] for cc in (64, 66, 123, 120)])
        self.assertFalse(e.held)

    def test_invalid_settings_rejected_without_changing_running_engine(self):
        e, sent = self.engine()
        for bad in ({"bpm": 0}, {"mode": "unknown"}, {"gate": 2}, {"velocity_limit": True}, {"step_beats": 0}, {"unknown": 1}, {"pattern": []}, {"harp_octaves": 5}, {"spread_beats": -1}, {"slop": 2}, {"seed": True}, {"chord_window_ms": 51}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                e.update(bad, 0)
        self.assertEqual(e.config["bpm"], 120)
        with self.assertRaises(ValueError):
            settings([])

    def test_live_runtime_opens_only_input_and_closes_on_stop(self):
        source, stop, reports, sent = Mock(), threading.Event(), [], []
        source.get_ports.return_value = ["Orchid"]
        source.get_message.return_value = None
        def report(value):
            reports.append(value)
            stop.set()
        with patch("orchid_studio.perform.backend") as backend:
            backend.return_value.MidiIn.return_value = source
            LivePerformance(sent.append, report, stop, input_name="Orchid", chord_channel=3).run()
            backend.return_value.MidiOut.assert_not_called()
        source.open_port.assert_called_once_with(0)
        source.close_port.assert_called_once()
        self.assertEqual(reports[0]["event"], "perform_ready")
        self.assertEqual(sent[-1], [176, 120, 0])

    def test_block_chord_holds_until_release(self):
        e, sent = self.engine(mode="off")
        self.chord(e)
        e.advance(0)
        e.advance(10)
        self.assertEqual(sent, [[144, p, 80] for p in (60, 64, 67)])
        e.receive([130, 64, 0])
        self.assertEqual(sent[-1], [128, 64, 0])
        e.panic()
        self.assertFalse(e.player.active)

    def test_strum_runs_once_and_two_octaves_expand(self):
        for mode, expected in (("strum", [60, 64, 67]), ("strum2", [60, 64, 67, 72, 76, 79])):
            e, sent = self.engine(mode=mode, spread_beats=.4)
            self.chord(e)
            for i in range(401):
                e.advance(i / 1000)
            self.assertEqual([m[1] for m in sent if m[0] == 144], expected)
            self.assertEqual(len(e.voices), len(expected))
            e.advance(10)
            self.assertEqual(len(sent), len(expected))

    def test_input_packets_coalesce_across_poll_iterations(self):
        e, sent = self.engine(mode="strum", chord_window_ms=8, spread_beats=0)
        e.receive([146, 60, 96], 0)
        e.advance(.002)
        e.receive([146, 64, 96], .003)
        e.advance(.007)
        e.receive([146, 67, 96], .007)
        e.advance(.014)
        self.assertFalse(sent)
        e.advance(.015)
        self.assertEqual(sent, [[144, p, 80] for p in (60, 64, 67)])

    def test_release_and_mode_change_cancel_pending_sweep(self):
        e, sent = self.engine(mode="strum", spread_beats=1)
        self.chord(e)
        e.advance(0)
        e.receive([130, 64, 0])
        e.advance(.25)
        self.assertEqual(sent, [[144, 60, 80]])
        e.update({"mode": "arp"}, .3)
        self.assertFalse(e.pending)
        e.advance(.5)
        self.assertEqual(sent, [[144, 60, 80], [128, 60, 0], [144, 60, 80]])

    def test_sweep_tempo_change_preserves_beat_positions(self):
        e, sent = self.engine(mode="strum", spread_beats=1)
        self.chord(e)
        e.advance(0)
        e.update({"bpm": 60}, .1)
        e.advance(.399)
        self.assertEqual(len(sent), 1)
        e.advance(.4)
        self.assertEqual(sent[-1], [144, 64, 80])
        e.advance(.9)
        self.assertEqual(sent[-1], [144, 67, 80])

    def test_harp_sweeps_three_octaves_and_releases_tails(self):
        e, sent = self.engine(mode="harp", spread_beats=.5)
        self.chord(e)
        for i in range(501):
            e.advance(i / 1000)
        self.assertEqual([m[1] for m in sent if m[0] == 144], [60, 64, 67, 72, 76, 79, 84, 88, 91])
        self.assertFalse(e.voices)
        self.assertFalse(e.player.active)

    def test_slop_is_repeatable_and_changes_timing(self):
        schedules = []
        for seed in (3, 3, 4):
            e, sent = self.engine(mode="slop", slop=1, seed=seed, spread_beats=1)
            self.chord(e)
            e.advance(0)
            schedules.append(list(e.pending))
        self.assertEqual(schedules[0], schedules[1])
        self.assertNotEqual(schedules[0], schedules[2])
        self.assertNotEqual(schedules[0][0][0], .5)

    def test_all_patterns_keep_rhythm_independent_of_chord_size(self):
        from orchid_studio.perform import PATTERNS
        for pattern in PATTERNS:
            timings = []
            for chord in ((60, 64, 67), (60, 64, 67, 71)):
                e, sent = self.engine(mode="pattern", pattern=pattern)
                for p in chord:
                    e.receive([146, p, 96])
                onsets = []
                for i in range(4000):
                    before = len(sent)
                    e.advance(i / 1000)
                    if any(m[0] == 144 for m in sent[before:]):
                        onsets.append(i)
                timings.append(onsets)
            with self.subTest(pattern=pattern):
                self.assertEqual(timings[0], timings[1])
                self.assertEqual(len(timings[0]), len(PATTERNS[pattern]) * 2)

    def test_pending_sweep_stall_drops_overdue_attacks(self):
        e, sent = self.engine(mode="strum", spread_beats=1)
        self.chord(e)
        e.advance(0)
        e.advance(2)
        self.assertEqual(sent, [[144, 60, 80]])
        self.assertFalse(e.pending)

    def test_sustained_sweep_panic_cancels_every_voice_and_future_attack(self):
        e, sent = self.engine(mode="strum2", spread_beats=1)
        self.chord(e)
        e.receive([178, 64, 127])
        e.advance(0)
        e.advance(.1)
        self.assertEqual(len(e.voices), 2)
        e.panic()
        count = len(sent)
        e.advance(1)
        self.assertEqual(len(sent), count)
        self.assertFalse(e.pending)
        self.assertFalse(e.player.active)

    def test_failed_note_send_is_registered_for_panic(self):
        sent = []
        def send(message):
            if message[0] == 144:
                raise RuntimeError("disconnected")
            sent.append(message)
        e = Arpeggiator(send, 3, 1, {"mode": "off", "chord_window_ms": 0})
        self.chord(e)
        with self.assertRaises(RuntimeError):
            e.advance(0)
        e.panic()
        self.assertIn([128, 60, 0], sent)
        self.assertFalse(e.pending)
