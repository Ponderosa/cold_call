"""Tests for audio subsystem (mocked — no ALSA devices needed)."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_audio.py: importing unittest.mock...")
from unittest.mock import patch, MagicMock
_log.info("test_audio.py: importing cold_call.audio (triggers alsaaudio + ctypes)...")
from cold_call.audio import SoundPlayer, CrossRoute
_log.info("test_audio.py: imports complete")


class TestSoundPlayer:
    def test_initial_state(self):
        player = SoundPlayer()
        assert not player.is_playing()
        assert player._proc is None

    def test_stop_when_nothing_playing(self):
        player = SoundPlayer()
        player.stop()  # should not raise

    @patch("cold_call.audio.subprocess.Popen")
    def test_play_starts_aplay(self, mock_popen, side_a):
        player = SoundPlayer()
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        player.play(side_a, "/tmp/test.wav")

        mock_popen.assert_called_once()
        args = mock_popen.call_args
        cmd = args[0][0]
        assert "aplay" in cmd
        assert f"plughw:{side_a.card},0" in cmd

    @patch("cold_call.audio.subprocess.Popen")
    def test_play_stops_previous(self, mock_popen, side_a):
        player = SoundPlayer()
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        player.play(side_a, "/tmp/a.wav")
        player.play(side_a, "/tmp/b.wav")

        # Should have been called twice (two plays)
        assert mock_popen.call_count == 2


class TestCrossRoute:
    def test_initial_state(self):
        route = CrossRoute()
        assert not route.is_active()

    def test_stop_when_not_started(self):
        route = CrossRoute()
        route.stop()  # should not raise
        assert route._procs == []
