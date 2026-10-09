"""Persistent virtual MIDI session controlled by one JSON object per line."""

import json
import threading
import time

from .sequencer import Player, compile_session, demo_session
from .hydrogen import command_message, session_drums


class PlaybackStopped(Exception):
    pass


class Transport:
    def __init__(self, send, report, drums=None):
        self.send = send
        self.report = report
        self.stop_requested = threading.Event()
        self.worker = None
        self.drums = drums
        self.live = None
        from .timeline import Timeline
        self.timeline=Timeline()
        self.tempo_sink=None
        self.last_tempo_sent=None
        self.last_tempo_at=0
        from .clock_output import ClockOutput
        self.clock_output=ClockOutput()
        from .looper import Looper
        self.looper = Looper(send, report, drums)
        self.looper.clock_output=self.clock_output
        self.looper.timeline=self.timeline
        self.looper.tempo_tick=self.sync_tempo

    @property
    def playing(self):
        return (self.worker is not None and self.worker.is_alive()) or self.looper.playing

    def stop(self):
        self.looper.stop()
        self.stop_requested.set()
        if self.worker is not None:
            self.worker.join()
            self.worker = None
        self.live = None
        self.clock_output.stop()
        self.timeline.stop()
        if self.drums is not None:
            self.drums.stop()

    def set_tempo(self,bpm,transition_seconds=2):
        self.timeline.tempo(bpm,transition_seconds)
        with self.looper.lock:
            self.looper.perform['bpm']=bpm
            if self.looper.live_config:self.looper.live_config['bpm']=bpm
            if self.looper.take:self.looper.take['settings']['bpm']=bpm
        if self.live:self.live.update({'bpm':bpm})
        if self.drums:self.drums.command('bpm',self.timeline.bpm)

    def sync_tempo(self):
        bpm=self.timeline.bpm
        if self.drums:self.drums.bpm=bpm
        now=time.monotonic()
        if self.tempo_sink and now-self.last_tempo_at>=.05 and bpm!=self.last_tempo_sent:
            self.tempo_sink(bpm)
            self.last_tempo_sent=bpm;self.last_tempo_at=now

    def pause(self,paused):
        if not self.playing:raise ValueError('start playback before pausing')
        if self.looper.take:raise ValueError('finish or cancel recording before pausing')
        self.timeline.pause(paused)
        self.clock_output.pause(paused)

    def panic(self):
        try:
            self.stop()
        finally:
            try:
                Player(self.send, range(16)).panic()
            finally:
                if self.drums is not None:
                    self.drums.panic()

    def play(self, session, *, bpm=None, transpose=0, repeats=1):
        # Validate before interrupting an existing performance.
        events, tempo, length, channels = compile_session(
            session, bpm=bpm, transpose=transpose, repeats=repeats,
        )
        drum_config = session_drums(session)
        if drum_config is not None:
            if self.drums is None:
                raise ValueError("session uses Hydrogen; start serve with --hydrogen")
            command_message("bpm", tempo)
            if hasattr(self.drums, "prepare"):
                self.drums.prepare(drum_config)
        self.stop()
        self.stop_requested.clear()
        self.timeline.reset(tempo)

        def sleep(seconds):
            if self.stop_requested.wait(seconds):
                raise PlaybackStopped

        def run():
            self.clock_output.begin()
            def tick(beat):
                self.sync_tempo()
                self.clock_output.advance(beat,self.timeline.bpm)
                if drum_config:self.drums.advance(beat)
            try:
                try:
                    if drum_config is not None:
                        self.drums.start(tempo, drum_config)
                    Player(self.send, channels, sleep=sleep).play(events, tempo, length,
                        tick=tick,timeline=self.timeline)
                finally:
                    self.clock_output.stop()
                    if drum_config is not None:
                        self.drums.stop()
                self.report({"event": "completed", "cleanup": "sent", "audibility": "requires listener confirmation"})
            except PlaybackStopped:
                self.report({"event": "stopped", "cleanup": "sent"})
            except Exception as exc:
                self.report({"event": "playback_error", "error": str(exc)})

        self.report({"event": "playing", "bpm": tempo, "length_beats": length,
                     "transpose": transpose, "channels": [c + 1 for c in sorted(channels)]})
        self.worker = threading.Thread(target=run, name="orchid-playback")
        self.worker.start()

    def play_drums(self, bpm, config):
        self.drums.prepare(config)
        self.stop()
        self.stop_requested.clear()
        self.timeline.reset(bpm)
        def run():
            try:
                self.drums.start(bpm, config)
                self.clock_output.begin()
                origin=time.monotonic()
                while not self.stop_requested.is_set():
                    if self.timeline.paused:
                        self.drums.client.command("stop");self.stop_requested.wait(.01);continue
                    self.sync_tempo()
                    beat=self.timeline.position()
                    self.clock_output.advance(beat,self.timeline.bpm)
                    self.drums.advance(beat)
                    self.stop_requested.wait(.002)
            except Exception as exc:
                self.report({'event':'playback_error','error':str(exc)})
            finally:
                self.clock_output.stop()
                self.drums.stop()
                self.report({'event':'stopped','cleanup':'sent'})
        self.worker=threading.Thread(target=run,name='orchid-drums')
        self.worker.start()

    def perform(self, request):
        from .perform import LivePerformance
        drum_config = session_drums(request)
        if drum_config is not None and self.drums is None:
            raise ValueError("drums require serve --hydrogen")
        if drum_config is not None and hasattr(self.drums, "prepare"):
            self.drums.prepare(drum_config)
        live = LivePerformance(self.send, self.report, self.stop_requested,
                               input_name=request.get("input"), chord_channel=request.get("chord_channel"),
                               output_channel=request.get("output_channel", 1), config=request.get("settings"),
                               drums=self.drums, drum_config=drum_config)
        self.stop()
        self.stop_requested.clear()
        self.live = live
        self.timeline.reset(live.config["bpm"])
        live.timeline=self.timeline
        live.tempo_tick=self.sync_tempo
        live.clock_output=self.clock_output
        def run():
            try:
                live.run()
                self.report({"event": "stopped", "cleanup": "sent"})
            except Exception as exc:
                self.report({"event": "playback_error", "error": str(exc)})
        self.worker = threading.Thread(target=run, name="orchid-live-perform")
        self.worker.start()


def serve(send, lines, report, drums=None, *, api_port=None, api_only=False, drum_bank=None, sound_input=None, pistil_host=False, chord_channel=3, session=None):
    """One controller owns MIDI/OSC for both JSON lines and the loopback HTTP API."""
    from contextlib import nullcontext
    from .api import Controller, HttpAPI
    controller = Controller(send, report, drums, drum_bank=drum_bank)
    from .midi_connection import MidiConnection
    controller.midi_connection = MidiConnection()
    controller.midi_connection.start()
    try:
        if pistil_host:
            result=controller.execute({"command":"pistil-enable"})
            if result["status"] == "error":
                raise RuntimeError(result["error"])
            report(result)
        if sound_input is not None:
            report(controller.execute({"command": "sound-follow", "input": sound_input, "enabled": True}))
            report(controller.execute({"command": "key-monitor", "input": sound_input, "chord_channel": chord_channel,
                                       "enabled": True}))
            if pistil_host:report(controller.execute({"command":"play-along","input":sound_input,"chord_channel":chord_channel,"enabled":True}))
        if session is not None:
            from pathlib import Path
            result=controller.execute({'command':'loop-import','document':json.loads(Path(session).read_text())})
            if result['status']=='error':raise RuntimeError(result['error'])
            report({'event':'session_restored','path':str(session),'playing':False})
        with (HttpAPI(controller, api_port) if api_port is not None else nullcontext()):
            if api_only:
                if api_port is None:
                    raise ValueError("--api-only requires --api-port")
                controller.closed.wait()
            else:
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        response = controller.execute(json.loads(line))
                    except ValueError as exc:
                        response = {"id": None, "status": "error", "error": str(exc)}
                    report(response)
                    if controller.closed.is_set():
                        break
    finally:
        controller.close()
