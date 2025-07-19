import os
import time
import numpy as np
import pyaudio
import logging
import threading
import queue
import random
from pydub import AudioSegment
import pyfftw  # For faster FFT operations

try:
    from .config import FFMPEG_FOLDER
except ImportError:
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

        # Shuffle feature
        self.shuffle_enabled = False
        self.current_folder = None
        self.playlist = []  # List of audio files in current folder
        self.current_track_index = 0
        self.auto_advance = True  # Automatically play next track when current ends
        self.track_finished_callback = None  # Callback for when track finishes

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

        # Set up playlist from the folder containing this file
        self.set_playlist_from_folder(file_path)

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
            # Stop playing and trigger auto-advance if enabled
            self.is_playing = False
            if self.auto_advance and self.track_finished_callback:
                # Schedule callback to run in main thread
                try:
                    self.track_finished_callback()
                except Exception as e:
                    self.logger.error(f"Error in track finished callback: {e}")
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
            # Pad with silence if needed
            silence_frames = frame_count - frames_to_read
            silence = np.zeros((silence_frames, self.channels), dtype=np.float32)
            silence_bytes = self._float_array_to_raw_bytes(silence.ravel())
            out_bytes += silence_bytes
            
            # Mark as ending and trigger callback
            self.is_playing = False
            if self.auto_advance and self.track_finished_callback:
                try:
                    self.track_finished_callback()
                except Exception as e:
                    self.logger.error(f"Error in track finished callback: {e}")
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
         - Normalization uses several parameters to dynamically adjust what is considered the
           upper bound for use in normalization

        Notes on Normalization:
        - Normalization ensures that the amplitude of audio signals is scaled appropriately to fit within
          a consistent visual range, allowing the visualizer to display meaningful and proportionate
          representations of the audio's frequency spectrum, regardless of the song's inherent
          volume variations.
        - Key Components and Parameters:
            - Persistent Maximum (persistent_max)
            - Baseline Value (baseline_value)
            - Noise Threshold (noise_threshold)
            - Smoothing Factor (alpha)
            - Fast Attack/Slow Release Mechanism
        - Interplay between components:
          1. Normalization Flow
            - Compute maximum amplitude (current_max) from the selected FFT bins (bins_50)
            - Update persistent_max using the Fast Attack / Slow Release mechanism
            - Determine effective_max to ensure that normalization does not amplify signals below the baseline_value
            - Apply the noise_threshold to decide whether to normalize or consider the chunk as silence
          2. Handling Different Audio Scenarios
            - Quiet Beginnings:
              - Challenge: Initial persistent_max is low, risking over-amplification of faint audio
              - Solution: baseline_value ensures that normalization does not excessively scale up low-amplitude signals
            - Loud Starts:
              - Challenge: Sudden high amplitudes can skew normalization, making subsequent quieter passages
                appear too quiet
              - Solution:
                  - Fast Attack quickly updates persistent_max to the high amplitude, preventing the
                  over-amplification of subsequent low-amplitude chunks
                  - Slow Release then gradually lowers persistent_max as the audio returns to quieter levels
            - Dynamic Range in Audio:
              - Challenge: Songs with varying temporal dynamics can cause inconsistent visual representations
              - Solution: The combination of persistent_max, baseline_value, noise_threshold, and the
                Fast Attack/Slow Release mechanism maintains a balanced normalization, aiming to reflect the
                audio's dynamic range without erratic visual spikes or dips
        - Additional Notable Parameters:
          - smoothing: Affects how much the current FFT data influences the visualizer compared to previous
            states, contributing to the overall stability of the visualization
          - bass_boost: enhances lower frequencies, making bass lines more visible
          - beat_threshold: works in tandem with bass frequencies to detect beats, influencing dynamic
            visual effects like pulsating bars
        - Design Rationale:
          1. Dynamic Normalization:
            - Flexibility: Adapts to varying audio levels, ensuring the visualizer remains responsive and accurate
              across different songs with diverse dynamics
            - Stability: Prevents erratic visual behavior by maintaining consistent scaling, avoiding spikes during
              quiet sections and ensuring that loud passages do not cause subsequent quiet sections to appear too
              subdued
          2. Preventing Over-Amplification:
            - Baseline Enforcement: By introducing a baseline_value, the system avoids excessive scaling of
              low-amplitude signals, which can make quiet audio misleadingly prominent in the visualization
            - Noise Suppression: The noise_threshold filters out insignificant signals, ensuring that the
              visualizer focuses on meaningful audio data
          3. Enhanced Visualization Features:
            - Smoothing: Provides a more aesthetically pleasing and les jittery visual output by averaging
              changes over time
            - Bass Boost and Beat Detection: Adds depth and dynamism to the visualization, making it more engaging
              by highlighting bass frequencies and rhythmic elements
          4. Performance Considerations:
            - Thread-Safe Updates: Using locks (self.lock) ensures that the visualizer data is updated safely across
              multiple threads without race conditions
            - Efficient Computation: Using pyFFTW for FFT operations and minimizing computational overhead
              in the callback ensures low-latency and real-time performance

        Normalization Flow Diagram:
        [FFT Computation]
                |
                V
        [Select 50 Frequency Bins (bins_50)]
                |
                V
        [Compute current_max]
                |
                V
        [Update persistent_max]
                |        \
              Fast     Slow
              Attack   Release
                |        |
                V        V
        [Determine effective_max = max(persistent_max, baseline_value)]
                |
                V
        [Check if effective_max > noise_threshold]
                / \
              Yes   No
              /       \
        [Normalize] [Set bins_50 to 0]
              |
              V
        [Smoothing & Visualization Processing]
              |
              V
        [Update visualizer_data]
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
                # Slow release: gradually decrease persistent_max towards current_max
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
                    smoothed *= 1.24

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

    def toggle_shuffle(self):
        """Toggle shuffle mode on/off"""
        self.shuffle_enabled = not self.shuffle_enabled
        self.logger.info(f"Shuffle {'enabled' if self.shuffle_enabled else 'disabled'}")
        return self.shuffle_enabled

    def set_playlist_from_folder(self, file_path):
        """Set up playlist from the folder containing the current file"""
        folder_path = os.path.dirname(file_path)
        if folder_path != self.current_folder:
            self.current_folder = folder_path
            self.playlist = []
            
            try:
                # Get all audio files in the folder
                for file in os.listdir(folder_path):
                    if file.lower().endswith(('.mp3', '.wav', '.flac', '.m4a', '.ogg')):
                        self.playlist.append(os.path.join(folder_path, file))
                
                self.playlist.sort()  # Sort alphabetically
                self.logger.info(f"Playlist created with {len(self.playlist)} files from {folder_path}")
                
                # Find current file index
                try:
                    self.current_track_index = self.playlist.index(file_path)
                except ValueError:
                    self.current_track_index = 0
                    
            except Exception as e:
                self.logger.error(f"Error creating playlist: {e}")
                self.playlist = [file_path]
                self.current_track_index = 0

    def get_next_track(self):
        """Get the next track based on shuffle setting"""
        if not self.playlist:
            return None
            
        if self.shuffle_enabled:
            # Get a random track that's not the current one
            available_tracks = [track for i, track in enumerate(self.playlist) if i != self.current_track_index]
            if available_tracks:
                next_track = random.choice(available_tracks)
                self.current_track_index = self.playlist.index(next_track)
                return next_track
            else:
                return self.playlist[0] if self.playlist else None
        else:
            # Sequential mode
            self.current_track_index = (self.current_track_index + 1) % len(self.playlist)
            return self.playlist[self.current_track_index]

    def get_previous_track(self):
        """Get the previous track based on shuffle setting"""
        if not self.playlist:
            return None
            
        if self.shuffle_enabled:
            # In shuffle mode, just pick a random track
            available_tracks = [track for i, track in enumerate(self.playlist) if i != self.current_track_index]
            if available_tracks:
                prev_track = random.choice(available_tracks)
                self.current_track_index = self.playlist.index(prev_track)
                return prev_track
            else:
                return self.playlist[0] if self.playlist else None
        else:
            # Sequential mode
            self.current_track_index = (self.current_track_index - 1) % len(self.playlist)
            return self.playlist[self.current_track_index]

    def is_shuffle_enabled(self):
        """Return current shuffle state"""
        return self.shuffle_enabled

    def set_track_finished_callback(self, callback):
        """Set callback to be called when track finishes"""
        self.track_finished_callback = callback

    def set_auto_advance(self, enabled):
        """Enable/disable auto-advance to next track"""
        self.auto_advance = enabled
        self.logger.info(f"Auto-advance {'enabled' if enabled else 'disabled'}")

    def get_auto_advance(self):
        """Get current auto-advance state"""
        return self.auto_advance
