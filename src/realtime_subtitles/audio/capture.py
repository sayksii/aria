"""
System audio capture using WASAPI loopback.

This module captures audio output from the system (what you hear through speakers)
using Windows Audio Session API (WASAPI) in loopback mode.
"""

import threading
import queue
from typing import Callable, Optional
import numpy as np

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    raise ImportError(
        "pyaudiowpatch is required for audio capture. "
        "Install it with: pip install PyAudioWPatch"
    )


class AudioCapture:
    """
    Captures system audio using WASAPI loopback mode.
    
    This allows capturing any audio playing through the system's
    default output device (speakers/headphones).
    
    Example:
        >>> capture = AudioCapture()
        >>> capture.start(callback=lambda audio, sr: print(f"Got {len(audio)} samples"))
        >>> # ... do something ...
        >>> capture.stop()
    """
    
    # Audio settings optimized for Whisper
    SAMPLE_RATE = 16000  # Whisper expects 16kHz
    CHANNELS = 1  # Mono
    CHUNK_DURATION_MS = 100  # 100ms chunks for low latency
    
    def __init__(self):
        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._is_running = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._callback: Optional[Callable[[np.ndarray, int], None]] = None
        self._capture_thread: Optional[threading.Thread] = None
        
    def _get_loopback_device(self) -> dict:
        """Find the WASAPI loopback device for the default output."""
        if self._pyaudio is None:
            self._pyaudio = pyaudio.PyAudio()
            
        # Get default WASAPI output device
        wasapi_info = self._pyaudio.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_output_idx = wasapi_info["defaultOutputDevice"]
        default_output = self._pyaudio.get_device_info_by_index(default_output_idx)
        
        # Find corresponding loopback device
        for i in range(self._pyaudio.get_device_count()):
            device = self._pyaudio.get_device_info_by_index(i)
            if (device.get("isLoopbackDevice", False) and 
                device["name"].startswith(default_output["name"].split(" (")[0])):
                return device
                
        # Fallback: return default output with loopback flag
        return default_output
    
    def _calculate_chunk_size(self, device_rate: int) -> int:
        """Calculate chunk size in frames based on device sample rate."""
        return int(device_rate * self.CHUNK_DURATION_MS / 1000)
    
    def _resample(self, audio: np.ndarray, original_rate: int) -> np.ndarray:
        """Resample audio to target sample rate using linear interpolation."""
        if original_rate == self.SAMPLE_RATE:
            return audio
            
        # Simple resampling using numpy interpolation
        duration = len(audio) / original_rate
        target_length = int(duration * self.SAMPLE_RATE)
        
        if target_length == 0:
            return np.array([], dtype=np.float32)
            
        indices = np.linspace(0, len(audio) - 1, target_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - runs in separate thread."""
        self._audio_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def _process_audio_loop(self, device_rate: int, channels: int):
        """Main loop for processing captured audio."""
        while self._is_running:
            try:
                raw_data = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
                
            # Convert bytes to numpy array
            audio = np.frombuffer(raw_data, dtype=np.float32)
            
            # Convert stereo to mono if needed
            if channels > 1:
                audio = audio.reshape(-1, channels).mean(axis=1)
            
            # Resample to 16kHz
            audio = self._resample(audio, device_rate)
            
            # Call user callback
            if self._callback and len(audio) > 0:
                self._callback(audio, self.SAMPLE_RATE)
    
    def start(self, callback: Callable[[np.ndarray, int], None]) -> None:
        """
        Start capturing system audio.
        
        Args:
            callback: Function called with (audio_chunk: np.ndarray, sample_rate: int)
                     for each captured audio chunk.
        """
        if self._is_running:
            return
            
        self._callback = callback
        self._is_running = True
        
        # Initialize PyAudio
        if self._pyaudio is None:
            self._pyaudio = pyaudio.PyAudio()
        
        # Get loopback device
        device = self._get_loopback_device()
        device_rate = int(device["defaultSampleRate"])
        channels = int(device["maxInputChannels"])
        chunk_size = self._calculate_chunk_size(device_rate)
        
        print(f"[AudioCapture] Using device: {device['name']}")
        print(f"[AudioCapture] Device rate: {device_rate}Hz, Channels: {channels}")
        print(f"[AudioCapture] Chunk size: {chunk_size} frames ({self.CHUNK_DURATION_MS}ms)")
        
        # Open stream
        self._stream = self._pyaudio.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=device_rate,
            input=True,
            input_device_index=device["index"],
            frames_per_buffer=chunk_size,
            stream_callback=self._audio_callback,
        )
        
        # Start processing thread
        self._capture_thread = threading.Thread(
            target=self._process_audio_loop,
            args=(device_rate, channels),
            daemon=True
        )
        self._capture_thread.start()
        
        self._stream.start_stream()
        print("[AudioCapture] Started capturing system audio")
    
    def stop(self) -> None:
        """Stop capturing audio."""
        self._is_running = False
        
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
            
        if self._capture_thread:
            self._capture_thread.join(timeout=1.0)
            self._capture_thread = None
            
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None
            
        # Clear queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
                
        print("[AudioCapture] Stopped")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


# Quick test
if __name__ == "__main__":
    import time
    
    def on_audio(audio: np.ndarray, sample_rate: int):
        # Calculate audio level (RMS)
        rms = np.sqrt(np.mean(audio ** 2))
        db = 20 * np.log10(max(rms, 1e-10))
        bars = int(max(0, (db + 60) / 2))  # -60dB to 0dB -> 0 to 30 bars
        print(f"\r[{'█' * bars}{' ' * (30 - bars)}] {db:6.1f} dB", end="", flush=True)
    
    print("Testing audio capture... Play some audio on your computer!")
    print("Press Ctrl+C to stop.\n")
    
    capture = AudioCapture()
    try:
        capture.start(callback=on_audio)
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        capture.stop()
