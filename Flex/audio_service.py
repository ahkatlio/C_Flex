import os
import threading
import time
import numpy as np
import pyaudio
from pydub import AudioSegment

# Import from config if you need local ffmpeg references:
from config import FFMPEG_FOLDER

# Because we've appended the PATH, PyDub can see local ffmpeg
LOCAL_FFMPEG = os.path.join(FFMPEG_FOLDER, "ffmpeg.exe")
LOCAL_FFPROBE = os.path.join(FFMPEG_FOLDER, "ffprobe.exe")


class AudioService:
    """
    Handles audio decoding (via pydub), playback (via PyAudio),
    and real-time FFT-based visualization data.
    """
    def __init__(self, chunk_size=2048):
        self.current_file = None
        self.is_playing = False
        self.is_paused = False

        self.volume = 50            # [0..200], 100 = normal
        self.duration_s = 0.0       # total track duration in seconds

        # Visualization
        self.visualizer_data = np.zeros(50, dtype=np.float32)
        self.last_spectrum = np.zeros(50, dtype=np.float32)
        self.smoothing = 0.3
        self.bass_boost = 2.0
        self.beat_threshold = 0.6

        # PyAudio
        self.pyaudio_instance = pyaudio.PyAudio()
        self.audio_stream = None

        # Threading / concurrency
        self.stop_event = threading.Event()
        self.play_thread = None
        self.lock = threading.Lock()

        # Audio buffer metadata
        self.audio_segment = None
        self.frame_rate = 44100
        self.channels = 2
        self.sample_width = 2
        self.bytes_per_frame = self.channels * self.sample_width
        self.chunk_size = chunk_size
        self.playhead_frames = 0

    def load_and_play(self, file_path: str) -> bool:
        """
        Decode MP3 via PyDub, open a PyAudio stream, and start background playback + FFT.
        """
        self.stop()  # stop previous playback
        try:
            self.current_file = os.path.abspath(file_path)
            self.audio_segment = AudioSegment.from_file(
                self.current_file,
                format="mp3",
                ffmpeg_path=LOCAL_FFMPEG,
                ffprobe_path=LOCAL_FFPROBE
            )

            # Extract metadata
            self.channels = self.audio_segment.channels
            self.frame_rate = self.audio_segment.frame_rate
            self.sample_width = self.audio_segment.sample_width
            self.bytes_per_frame = self.channels * self.sample_width
            self.duration_s = len(self.audio_segment) / 1000.0

            # Open PyAudio stream
            pyaudio_format = self._get_pyaudio_format(self.sample_width)
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio_format,
                channels=self.channels,
                rate=self.frame_rate,
                output=True
            )

            self.is_playing = True
            self.is_paused = False
            self.playhead_frames = 0
            self.stop_event.clear()

            # Start background thread
            self.play_thread = threading.Thread(
                target=self._playback_loop,
                daemon=True
            )
            self.play_thread.start()

            return True

        except Exception as exc:
            print(f"Error loading file {file_path}:\n{exc}")
            return False

    def stop(self):
        """Stop playback if active."""
        if self.is_playing or self.is_paused:
            self.stop_event.set()
            if self.play_thread:
                self.play_thread.join()
            self._close_stream()
            self.is_playing = False
            self.is_paused = False
            with self.lock:
                self.visualizer_data[:] = 0

    def pause(self):
        """Toggle pause."""
        if self.is_playing:
            self.is_paused = not self.is_paused

    def set_volume(self, volume: int):
        """Volume in [0..200]."""
        self.volume = max(0, min(200, volume))

    def get_playback_position(self) -> float:
        """Returns current playback time in seconds."""
        if not self.is_playing and not self.is_paused:
            return 0.0
        return float(self.playhead_frames) / float(self.frame_rate)

    def cleanup(self):
        """Cleanup resources on shutdown."""
        self.stop()
        if self.pyaudio_instance is not None:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None

    def _playback_loop(self):
        raw_data = self.audio_segment.raw_data
        total_frames = len(raw_data) // self.bytes_per_frame

        while not self.stop_event.is_set():
            if self.is_paused:
                time.sleep(0.05)
                continue

            if self.playhead_frames >= total_frames:
                # End of audio
                break

            # Next chunk
            start_frame = self.playhead_frames
            end_frame = min(self.playhead_frames + self.chunk_size, total_frames)
            chunk_frames = end_frame - start_frame

            start_byte = start_frame * self.bytes_per_frame
            end_byte = end_frame * self.bytes_per_frame
            data_chunk = raw_data[start_byte:end_byte]

            # Convert to float for volume scaling + FFT
            chunk_array = self._raw_to_float_array(data_chunk)

            # Scale volume
            volume_scale = self.volume / 100.0
            chunk_array *= volume_scale

            # Write scaled chunk
            scaled_bytes = self._float_array_to_raw_bytes(chunk_array)
            if self.audio_stream:
                self.audio_stream.write(scaled_bytes)

            # Visualization: if stereo, downmix to mono
            if self.channels == 2:
                chunk_array = chunk_array.reshape(-1, 2).mean(axis=1)

            # FFT
            half_spectrum = np.abs(np.fft.fft(chunk_array)[: len(chunk_array)//2])
            bins_50 = half_spectrum[:50]
            if bins_50.size > 0 and np.max(bins_50) > 0:
                bins_50 = bins_50 / np.max(bins_50)

            # Smooth
            smoothed = (bins_50 * self.smoothing) + (self.last_spectrum * (1 - self.smoothing))
            self.last_spectrum = smoothed.copy()
            smoothed[:15] *= self.bass_boost

            # Basic beat detection
            if np.mean(smoothed[:10]) > self.beat_threshold:
                smoothed *= 1.2

            with self.lock:
                self.visualizer_data = smoothed

            self.playhead_frames += chunk_frames

        self.is_playing = False
        self.is_paused = False
        self._close_stream()

    def _close_stream(self):
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio_stream = None

    def _get_pyaudio_format(self, sample_width: int) -> int:
        """
        Map sample_width to pyaudio format. Fallback if 24-bit is not supported.
        """
        if sample_width == 3:
            # Typically we fallback to 32-bit if paInt24 is unavailable
            return pyaudio.paInt32
        return self.pyaudio_instance.get_format_from_width(sample_width)

    def _raw_to_float_array(self, data_chunk: bytes) -> np.ndarray:
        """Interpret raw PCM bytes as float32 array."""
        # Basic approach: handle 1/2/4 byte widths directly.
        if self.sample_width == 1:
            dtype = np.int8
        elif self.sample_width == 2:
            dtype = np.int16
        elif self.sample_width == 3:
            return self._from_24bit_to_float(data_chunk)
        elif self.sample_width == 4:
            dtype = np.int32
        else:
            dtype = np.int16

        return np.frombuffer(data_chunk, dtype=dtype).astype(np.float32)

    def _from_24bit_to_float(self, data_chunk: bytes) -> np.ndarray:
        """
        Convert 3-byte samples to float32 by sign-extending to 32-bit.
        """
        sample_count = len(data_chunk) // 3
        raw_3bytes = np.frombuffer(data_chunk, dtype=np.uint8).reshape(sample_count, 3)

        # sign extension
        sign_extended = np.zeros((sample_count, 4), dtype=np.uint8)
        sign_extended[:, :3] = raw_3bytes
        # detect negatives
        neg_mask = (raw_3bytes[:, 2] & 0x80) != 0
        sign_extended[neg_mask, 3] = 0xFF

        as_int32 = sign_extended.view(np.int32)
        return as_int32.astype(np.float32)

    def _float_array_to_raw_bytes(self, float_array: np.ndarray) -> bytes:
        """
        Convert float32 samples back to the original sample_width (int8, int16, etc.)
        """
        if self.sample_width == 3:
            # We fallback to 32-bit stream
            return float_array.astype(np.int32).tobytes()
        elif self.sample_width == 1:
            return float_array.astype(np.int8).tobytes()
        elif self.sample_width == 2:
            return float_array.astype(np.int16).tobytes()
        elif self.sample_width == 4:
            return float_array.astype(np.int32).tobytes()
        return float_array.astype(np.int16).tobytes()
