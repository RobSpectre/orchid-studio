import unittest
from unittest.mock import Mock
from orchid_studio.clock_output import ClockOutput


class ClockTests(unittest.TestCase):
    def publisher(self,offset=0):
        now=[10.0];sent=[];output=Mock()
        output.send_message.side_effect=lambda msg:sent.append((now[0],msg))
        c=ClockOutput(clock=lambda:now[0]);c.output=output;c.offset_ms=offset
        self.addCleanup(c.close)
        return c,now,sent

    def test_24_pulses_per_beat_start_stop_and_count_in(self):
        c,now,sent=self.publisher()
        c.begin();c.advance(-4,120);c.flush();self.assertEqual(sent,[])
        for tick in range(96):
            now[0]=10+tick/48;c.advance(tick/24,120);c.flush()
        c.stop()
        self.assertEqual([msg for _,msg in sent],[[0xFA]]+[[0xF8]]*96+[[0xFC]])
        self.assertEqual(c.snapshot()['pulses_sent'],96)

    def test_tempo_change_uses_shared_beat_and_no_phase_reset(self):
        c,now,sent=self.publisher();c.begin()
        for tick in range(48):
            bpm=120 if tick<24 else 90
            now[0]=10+tick/48 if tick<24 else 10.5+(tick-24)/36
            c.advance(tick/24,bpm);c.flush()
        pulses=[t for t,m in sent if m==[0xF8]]
        self.assertEqual(len(pulses),48)
        self.assertAlmostEqual(pulses[2]-pulses[1],1/48)
        self.assertAlmostEqual(pulses[26]-pulses[25],1/36)
        self.assertEqual(sum(m==[0xFA] for _,m in sent),1)

    def test_audio_offset_stop_cancels_pending_ticks_and_stall_stops_follower(self):
        c,now,sent=self.publisher(40);c.begin();c.advance(0,120);c.flush()
        self.assertEqual(sent,[])
        now[0]+=.04;c.flush();self.assertEqual([m for _,m in sent],[[0xFA],[0xF8]])
        c.advance(.1,120);c.stop();now[0]+=.04;c.flush()
        self.assertEqual(sent[-1][1],[0xFC]);self.assertEqual(len(sent),3)
        c.begin();c.advance(0,120);now[0]+=.04;c.flush()
        c.advance(3,120)
        self.assertIsNotNone(c.error);self.assertFalse(c.started);self.assertEqual(sent[-1][1],[0xFC])
        c.begin();self.assertIsNone(c.error)

    def test_only_fixed_virtual_source_is_opened(self):
        output=Mock();c=ClockOutput(factory=lambda:output)
        try:
            c.configure(True)
            output.open_virtual_port.assert_called_once_with('Orchid Studio Clock')
            output.open_port.assert_not_called()
            c.configure(False)
            output.close_port.assert_called_once()
        finally:c.close()
