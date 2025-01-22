import os
import time
import numpy as np
import pyaudio
import logging
import threading
import queue
from pydub import AudioSegment
import pyfftw  # For faster FFT operations

from config import FFMPEG_FOLDER

LOCAL_FFMPEG = os.path.join(FFMPEG_FOLDER, "ffmpeg.exe")
LOCAL_FFPROBE = os.path.join(FFMPEG_FOLDER, "ffprobe.exe")


class AudioService:
    """
    AudioService handles:
      - Decoding an MP3 file to float32 PCM data using pydub.
      - Audio playback using PyAudio's callback mode for low-latency, non-blocking I/O.
      - Real-time FFT analysis using pyFFTW for visualization or beat detection.

    Design decisions:
      - **Callback Mode**: Uses PyAudio's callback mode for non-blocking audio streaming to reduce latency.
      - **PyFFTW**: Offloads FFT computations to pyFFTW, which is faster than NumPy's FFT.
      - **Separate Analysis Thread**: The FFT and visualization computations are offloaded to a
        separate thread, ensuring the audio callback remains lightweight.
      - **In-place Operations**: Volume scaling is done in-place to minimize memory overhead.
      - **Minimal Logging in Critical Path**: Logging is minimized in hot loops (e.g., the callback)
        to reduce performance impact.
    """

    def __init__(self,
                 chunk_size=2048,
                 logger=None,
                 fft_threads=1):
        # Initialize logging and state variables.
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Playback state
        self.current_file = None
        self.is_playing = False
        self.is_paused = False

        # Introduce separate audio callback and analysis thread events
        self.callback_stop_event = threading.Event()
        self.analysis_stop_event = threading.Event()

        # Audio parameters
        self.volume = 50  # Volume percentage (0 to 200); 100 is normal.
        self.duration_s = 0.0
        self.chunk_size = int(chunk_size)
        self.frame_rate = 44100  # Default sample rate.
        self.channels = 2  # Stereo by default.
        self.sample_width = 2  # In bytes (16-bit samples).
        self.bytes_per_frame = self.channels * self.sample_width

        # Decoded float audio data and playback pointers.
        self.float_data = None  # Full decoded audio as a float32 numpy array.
        self.total_frames = 0  # Total number of frames in the loaded audio.
        self.playhead_frames = 0  # Current playback frame pointer used by the callback.

        # Visualization and FFT smoothing parameters.
        self.visualizer_data = np.zeros(50, dtype=np.float32)
        self.last_spectrum = np.zeros(50, dtype=np.float32)
        self.smoothing = 0.3
        self.bass_boost = 2.1
        self.beat_threshold = 0.6

        # Initialize PyAudio instance.
        self.pyaudio_instance = pyaudio.PyAudio()
        self.audio_stream = None

        # Lock for synchronizing access to visualization data.
        self.lock = threading.Lock()

        # Queue for passing audio chunks from the callback to the analysis thread.
        self.analysis_queue = queue.Queue()

        # Start the separate thread that handles FFT analysis.
        self.analysis_thread = threading.Thread(target=self._analysis_loop,
                                                daemon=True)
        self.analysis_thread.start()

        # Setup pyFFTW for efficient FFT processing.
        self.fft_threads = fft_threads
        # Allocate aligned arrays for FFT input and output for performance.
        self.fft_input = pyfftw.empty_aligned((self.chunk_size,), dtype='float32')
        # Pre-build the FFT plan for the given chunk size.
        # This plan will be reused for each FFT computation.
        self.fft_plan = pyfftw.builders.rfft(self.fft_input,
                                            # self.fft_output,
                                            n=self.chunk_size,
                                            threads=self.fft_threads,
                                            overwrite_input=True)

        self.logger.debug("AudioService initialized with callback + pyFFTW.")

    def load_and_play(self, file_path: str) -> bool:
        """
        Loads an MP3 file, decodes it to float32 PCM data, and starts playback
        using PyAudio's callback mode.

        Steps:
         1. Stop any previous playback.
         2. Use pydub to load and decode the MP3 file.
         3. Convert the entire audio data to a float32 numpy array and reshape
            to (total_frames, channels).
         4. Initialize PyAudio stream in callback mode.
         5. Start playback.
        """
        self.logger.info(f"Loading file: {file_path}")
        self.stop()  # Stop any previous playback.

        try:
            # Load and decode the MP3 file using pydub.
            self.current_file = os.path.abspath(file_path)
            audio_segment = AudioSegment.from_file(
                self.current_file,
                ffmpeg_path=LOCAL_FFMPEG,
                ffprobe_path=LOCAL_FFPROBE
            )

            # Extract metadata from the audio segment.
            self.channels = audio_segment.channels
            self.frame_rate = audio_segment.frame_rate
            self.sample_width = audio_segment.sample_width
            self.duration_s = len(audio_segment) / 1000.0
            self.bytes_per_frame = self.channels * self.sample_width

            # Convert the entire audio to a float32 numpy array.
            raw_data = audio_segment.raw_data
            float_array = self._raw_to_float_array(raw_data)
            num_samples = float_array.shape[0]
            self.total_frames = num_samples // self.channels
            # Reshape the flat float array into (frames, channels)
            self.float_data = float_array.reshape(self.total_frames, self.channels)

            # Reset playback pointer and clear stop signal.
            self.playhead_frames = 0
            self.callback_stop_event.clear()

            # Setup PyAudio stream in callback mode.
            pyaudio_format = self._get_pyaudio_format(self.sample_width)
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio_format,
                channels=self.channels,
                rate=self.frame_rate,
                output=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback  # Non-blocking callback.
            )

            self.is_playing = True
            self.is_paused = False
            # Start the stream. PyAudio will now invoke _audio_callback when needed.
            self.audio_stream.start_stream()

            self.logger.info("Playback started (callback mode).")
            return True

        except Exception as exc:
            self.logger.error(f"Error loading file {file_path}: {exc}", exc_info=True)
            return False

    def stop(self):
        """
        Stops the audio playback and cleans up the audio stream.
        Signals threads to stop and resets playback state.
        """
        if self.is_playing or self.is_paused:
            self.logger.info("Stopping playback.")
            # Signal all loops/threads that they should stop.
            self.callback_stop_event.set()

            # Stop and close the PyAudio stream if it's open.
            if self.audio_stream is not None:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
                self.audio_stream = None

            # Reset playback flags.
            self.is_playing = False
            self.is_paused = False

            # Clear visualization data safely.
            with self.lock:
                self.visualizer_data[:] = 0

    def pause(self):
        """
        Toggle pause/resume state.
        The callback function checks self.is_paused to decide whether to output sound.
        """
        if self.is_playing:
            self.is_paused = not self.is_paused
            self.logger.info(f"{'Paused' if self.is_paused else 'Resumed'} playback.")

    def set_volume(self, volume: int):
        """
        Adjusts playback volume.
        Volume is a percentage of the original amplitude (0-200).
        """
        old_volume = self.volume
        self.volume = max(0, min(200, volume))
        # Minimal logging here; not called per frame.
        self.logger.debug(f"Volume changed from {old_volume} to {self.volume}.")

    def get_playback_position(self) -> float:
        """
        Returns the current approximate playback position in seconds.
        """
        if not self.is_playing and not self.is_paused:
            return 0.0
        position = float(self.playhead_frames) / float(self.frame_rate)
        return position

    def cleanup(self):
        """
        Cleanup method to free resources. Stops playback and terminates PyAudio.
        """
        self.logger.info("Cleaning up AudioService resources.")
        self.stop()
        # Signal analysis thread to terminate.
        self.analysis_stop_event.set()
        if self.pyaudio_instance is not None:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None

    # ---------------------
    # PyAudio Callback Mode
    # ---------------------
    def _audio_callback(self, in_data, frame_count, time_info, status_flags):
        """
        PyAudio callback function. This function is called by PyAudio when it
        needs more audio data. It should return a tuple (audio_data, flag).

        Design decisions in this callback:
         - It remains lightweight, avoiding heavy operations like FFT.
         - It handles pause by providing silence.
         - It performs in-place volume scaling to minimize overhead.
         - It enqueues data for separate FFT analysis.
         - It minimizes logging to maintain real-time performance.
        """
        # If a stop has been requested for callback, end the stream.
        if self.callback_stop_event.is_set():
            return (None, pyaudio.paComplete)

        # If paused, return silence.
        if self.is_paused:
            silence = np.zeros((frame_count, self.channels), dtype=np.float32)
            silence_bytes = self._float_array_to_raw_bytes(silence.ravel())
            return (silence_bytes, pyaudio.paContinue)

        # Calculate remaining frames.
        frames_left = self.total_frames - self.playhead_frames
        if frames_left <= 0:
            # End of file reached.
            self.logger.info("Reached end of audio (callback).")
            return (None, pyaudio.paComplete)

        # Determine how many frames to send in this callback.
        frames_to_read = min(frame_count, frames_left)

        # Extract the current chunk of audio data to send.
        start_frame = self.playhead_frames
        end_frame = start_frame + frames_to_read
        # Get a view into the main float_data array for these frames.
        chunk_view = self.float_data[start_frame:end_frame, :]  # shape: (frames_to_read, channels)

        # In-place volume scaling:
        # Copy the chunk to avoid altering original audio data, then scale.
        scaled_chunk = chunk_view.copy()
        volume_scale = self.volume / 100.0
        scaled_chunk *= volume_scale

        # Convert scaled audio chunk to raw bytes for PyAudio output.
        out_bytes = self._float_array_to_raw_bytes(scaled_chunk.ravel())

        # Update playhead position.
        self.playhead_frames += frames_to_read

        # Downmix stereo to mono for FFT analysis if necessary.
        if self.channels > 1:
            mono_chunk = scaled_chunk.mean(axis=1)  # Average channels for mono.
        else:
            mono_chunk = scaled_chunk

        # Enqueue mono_chunk for analysis.
        try:
            self.analysis_queue.put_nowait(mono_chunk)
        except queue.Full:
            # If the queue is full, skip this chunk's analysis.
            pass

        # Check if we've provided fewer frames than requested (end-of-file scenario).
        if frames_to_read < frame_count:
            return (out_bytes, pyaudio.paComplete)
        else:
            return (out_bytes, pyaudio.paContinue)

    # ------------------------
    # Separate Analysis Thread
    # ------------------------
    def _analysis_loop(self):
        """
        This loop runs in a separate thread. It continuously:
         - Retrieves mono audio chunks from the analysis_queue.
         - Performs FFT using a pre-built pyFFTW plan.
         - Updates visualization data based on the FFT results.

        Design Decisions:
         - Offloading FFT to a separate thread prevents blocking the audio callback.
         - Uses pyFFTW for speed.
         - Smooths FFT results and applies bass boost/beat detection for visualization.
        """
        self.logger.debug("Analysis thread started.")

        # Normalization constants
        alpha = 0.88  # Smoothing factor for persistent_max
        noise_threshold = 1e-1  # Threshold for noise floor
        # Normalization variables
        persistent_max = 1e-6  # Initialize with a small value to avoid division by zero.
        baseline_value = 1e-3  # Adjust this value based on testing and preference.
        while not self.analysis_stop_event.is_set():
            try:
                # Wait for the next mono chunk for analysis.
                mono_chunk = self.analysis_queue.get(timeout=0.1)
            except queue.Empty:
                continue  # No chunk available, check stop_event and loop again.

            chunk_size = len(mono_chunk)
            if chunk_size == 0:
                continue

            # If the current chunk is smaller than the expected chunk_size,
            # zero-pad the remainder of the fft_input.
            if chunk_size < self.chunk_size:
                self.fft_input[:chunk_size] = mono_chunk
                self.fft_input[chunk_size:] = 0
            else:
                # Copy enough data to fill fft_input.
                self.fft_input[:] = mono_chunk[:self.chunk_size]

            # Execute the FFT using the pre-planned plan.
            self.fft_plan()

            # Use only the first half of the FFT output (real signal symmetry).
            half_size = self.chunk_size // 2
            spectrum = np.abs(self.fft_input[:half_size])
            spectrum /= (self.chunk_size / 2.0)  # scale down if needed

            # Select 50 evenly distributed frequency bins across the spectrum
            indices = np.linspace(0, half_size - 1, 50).astype(int)
            bins_50 = spectrum[indices]

            # Update the persistent maximum using exponential smoothing.
            current_max = np.max(bins_50)
            if current_max > persistent_max:
                # Fast attack: immediately adapt to a louder signal.
                persistent_max = current_max
            else:
                # Slow release: gradually decrease persistent_max.
                persistent_max = alpha * persistent_max + (1 - alpha) * current_max

            # Use baseline_value to avoid over-amplification
            effective_max = max(persistent_max, baseline_value)

            if effective_max > noise_threshold:
                # Only normalize if the maximum exceeds the noise threshold.
                bins_50 = bins_50 / effective_max
            else:
                # If below the threshold, consider it silence.
                bins_50 = np.zeros_like(bins_50)

            if bins_50.size > 0:
                # Smooth the spectrum using the previous spectrum.
                smoothed = (bins_50 * self.smoothing) + \
                           (self.last_spectrum[:bins_50.size] * (1 - self.smoothing))
                # Update the last_spectrum for next iteration.
                self.last_spectrum[:bins_50.size] = smoothed

                # Apply a bass boost to the first 15 bins.
                smoothed[:15] *= self.bass_boost

                # Simple beat detection: if the mean of the first 10 bins exceeds a threshold,
                # amplify the spectrum.
                if np.mean(smoothed[:10]) > self.beat_threshold:
                    smoothed *= 1.3

                # Update visualizer data in a thread-safe way.
                with self.lock:
                    self.visualizer_data[:bins_50.size] = smoothed
                    # Zero out the remainder if fewer than 50 bins.
                    if bins_50.size < 50:
                        self.visualizer_data[bins_50.size:] = 0

        self.logger.debug("Analysis thread exiting.")

    # -------------------------
    # Internal Utility Functions
    # -------------------------
    def _close_stream(self):
        """Closes the PyAudio stream if open."""
        if self.audio_stream:
            self.logger.debug("Closing audio stream.")
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio_stream = None

    def _get_pyaudio_format(self, sample_width: int) -> int:
        """
        Returns the appropriate PyAudio format for a given sample width.
        For 24-bit audio, falls back to 32-bit since paInt24 might not be supported.
        """
        if sample_width == 3:
            self.logger.debug("24-bit sample width detected, falling back to 32-bit.")
            return pyaudio.paInt32
        return self.pyaudio_instance.get_format_from_width(sample_width)

    def _raw_to_float_array(self, data_chunk: bytes) -> np.ndarray:
        """
        Converts raw PCM bytes from the MP3 file into a float32 numpy array.
        This is done only once when the file is loaded.
        """
        if self.sample_width == 1:
            dtype = np.int8
        elif self.sample_width == 2:
            dtype = np.int16
        elif self.sample_width == 3:
            # Special handling for 24-bit audio
            return self._from_24bit_to_float(data_chunk)
        elif self.sample_width == 4:
            dtype = np.int32
        else:
            dtype = np.int16  # Fallback for unknown widths.

        return np.frombuffer(data_chunk, dtype=dtype).astype(np.float32)

    def _from_24bit_to_float(self, data_chunk: bytes) -> np.ndarray:
        """
        Converts 24-bit PCM audio (3 bytes per sample) to float32.
        It sign-extends 3-byte samples to 4 bytes then converts them.
        """
        sample_count = len(data_chunk) // 3
        raw_3bytes = np.frombuffer(data_chunk, dtype=np.uint8).reshape(sample_count, 3)

        # Create a 4-byte array for sign extension.
        sign_extended = np.zeros((sample_count, 4), dtype=np.uint8)
        sign_extended[:, :3] = raw_3bytes
        # If the most significant bit is set, fill the 4th byte with 0xFF for negative values.
        neg_mask = (raw_3bytes[:, 2] & 0x80) != 0
        sign_extended[neg_mask, 3] = 0xFF

        # View the extended array as int32 and cast to float32.
        as_int32 = sign_extended.view(np.int32)
        return as_int32.astype(np.float32)

    def _float_array_to_raw_bytes(self, float_array: np.ndarray) -> bytes:
        """
        Converts a float32 numpy array of audio samples back to raw bytes using
        the original sample width. Supports common widths.
        """
        if self.sample_width == 3:
            # Fallback for 24-bit: convert to int32 representation.
            return float_array.astype(np.int32).tobytes()
        elif self.sample_width == 1:
            return float_array.astype(np.int8).tobytes()
        elif self.sample_width == 2:
            return float_array.astype(np.int16).tobytes()
        elif self.sample_width == 4:
            return float_array.astype(np.int32).tobytes()

        # Default to 16-bit conversion.
        return float_array.astype(np.int16).tobytes()
