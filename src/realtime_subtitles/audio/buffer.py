"""
Audio buffer management for streaming transcription.

Implements a sliding window buffer that accumulates audio and triggers
transcription based on speech activity and buffer thresholds.
"""

import threading
import time
from typing import Callable, Optional, List
from dataclasses import dataclass
from collections import deque
import numpy as np


@dataclass
class AudioSegment:
    """A segment of audio with metadata."""
    audio: np.ndarray
    timestamp: float
    is_speech: bool
    

class StreamingAudioBuffer:
    """
    Manages audio buffering for real-time transcription.
    
    Features:
    - Accumulates audio chunks into a buffer
    - Uses VAD to detect speech segments
    - Triggers transcription when:
      1. Speech ends (silence detected)
      2. Buffer exceeds max duration
      3. Speech exceeds min duration
    
    Example:
        >>> buffer = StreamingAudioBuffer(
        ...     on_segment_ready=lambda audio: transcribe(audio),
        ...     min_segment_duration=1.0,
        ...     max_segment_duration=10.0,
        ... )
        >>> buffer.add_audio(audio_chunk)  # Called repeatedly
    """
    
    SAMPLE_RATE = 16000
    
    def __init__(
        self,
        on_segment_ready: Callable[[np.ndarray], None],
        min_segment_duration: float = 1.0,
        max_segment_duration: float = 10.0,
        speech_pad_ms: int = 200,  # Reduced for lower latency
        use_vad: bool = True,
    ):
        """
        Initialize the streaming buffer.
        
        Args:
            on_segment_ready: Callback when a segment is ready for transcription.
                             Called with (audio: np.ndarray)
            min_segment_duration: Minimum audio duration before triggering (seconds)
            max_segment_duration: Maximum audio duration before forcing trigger (seconds)
            speech_pad_ms: Padding before/after speech segments (milliseconds)
            use_vad: Whether to use VAD for speech detection
        """
        self.on_segment_ready = on_segment_ready
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
        self.speech_pad_ms = speech_pad_ms
        self.use_vad = use_vad
        
        # Buffer state
        self._buffer: List[np.ndarray] = []
        self._buffer_samples = 0
        self._lock = threading.Lock()
        
        # Speech tracking
        self._speech_started = False
        self._speech_start_time: Optional[float] = None
        self._silence_start_time: Optional[float] = None
        
        # VAD
        self._vad = None
        if use_vad:
            from .vad import VoiceActivityDetector
            self._vad = VoiceActivityDetector(
                threshold=0.4,  # Lower threshold = more sensitive
                min_speech_duration_ms=150,  # Faster trigger
                min_silence_duration_ms=300,  # Faster end detection
            )
        
        # Pre-buffer for speech padding (reduced for lower latency)
        self._pre_buffer: deque = deque(
            maxlen=int(self.SAMPLE_RATE * speech_pad_ms / 1000)
        )
        
        print(f"[Buffer] Initialized: min={min_segment_duration}s, max={max_segment_duration}s, VAD={use_vad}")
    
    def _get_buffer_duration(self) -> float:
        """Get current buffer duration in seconds."""
        return self._buffer_samples / self.SAMPLE_RATE
    
    def _flush_buffer_unlocked(self) -> Optional[np.ndarray]:
        """Flush the buffer and return accumulated audio. Caller must hold lock."""
        if not self._buffer:
            return None
        
        audio = np.concatenate(self._buffer)
        self._buffer = []
        self._buffer_samples = 0
        
        return audio
    
    def _trigger_transcription(self) -> None:
        """Trigger transcription with current buffer."""
        with self._lock:
            audio = self._flush_buffer_unlocked()
        if audio is not None and len(audio) > 0:
            # Add padding from pre-buffer if available
            if self._pre_buffer:
                pre_audio = np.array(list(self._pre_buffer), dtype=np.float32)
                audio = np.concatenate([pre_audio, audio])
            
            self.on_segment_ready(audio)
    
    def add_audio(self, audio: np.ndarray) -> None:
        """
        Add audio chunk to the buffer.
        
        This method is called continuously with small audio chunks.
        It manages buffering and triggers transcription when appropriate.
        
        Args:
            audio: Audio chunk as float32 numpy array (16kHz)
        """
        current_time = time.time()
        
        # Check VAD if enabled
        is_speech = True
        if self._vad is not None:
            is_speech = self._vad.is_speech(audio)
        
        with self._lock:
            if is_speech:
                # Speech detected
                if not self._speech_started:
                    self._speech_started = True
                    self._speech_start_time = current_time
                    print("[Buffer] Speech started")
                
                self._silence_start_time = None
                self._buffer.append(audio)
                self._buffer_samples += len(audio)
                
            else:
                # Silence detected
                if self._speech_started:
                    # Still accumulate some silence for natural trailing
                    self._buffer.append(audio)
                    self._buffer_samples += len(audio)
                    
                    if self._silence_start_time is None:
                        self._silence_start_time = current_time
                    
                    # Check if silence duration exceeds threshold
                    silence_duration = current_time - self._silence_start_time
                    if silence_duration > (self.speech_pad_ms / 1000):
                        # Speech ended, trigger transcription
                        self._speech_started = False
                        self._speech_start_time = None
                        duration = self._get_buffer_duration()
                        audio_to_process = self._flush_buffer_unlocked()
                        # Release lock before print/callback to avoid blocking
                        
                        if audio_to_process is not None:
                            print(f"[Buffer] Speech ended, triggering transcription ({duration:.1f}s)")
                            threading.Thread(
                                target=self.on_segment_ready,
                                args=(audio_to_process,),
                                daemon=True,
                            ).start()
                        return
                else:
                    # Update pre-buffer with recent silence (for padding)
                    for sample in audio:
                        self._pre_buffer.append(sample)
        
        # Check max duration (outside lock)
        buffer_duration = self._get_buffer_duration()
        if buffer_duration >= self.max_segment_duration:
            with self._lock:
                self._speech_started = False
                self._speech_start_time = None
                audio_to_process = self._flush_buffer_unlocked()
            
            if audio_to_process is not None:
                print(f"[Buffer] Max duration reached, triggering transcription ({buffer_duration:.1f}s)")
                threading.Thread(
                    target=self.on_segment_ready,
                    args=(audio_to_process,),
                    daemon=True,
                ).start()
            return  # Important: stop processing this chunk
        
        # Note: Removed interim results logic to reduce queue buildup
        # Transcription now only triggers on:
        # 1. Speech end (silence detected)
        # 2. Max duration reached
    
    def reset(self) -> None:
        """Reset buffer state."""
        with self._lock:
            self._buffer = []
            self._buffer_samples = 0
            self._speech_started = False
            self._speech_start_time = None
            self._silence_start_time = None
            self._pre_buffer.clear()
            
        if self._vad is not None:
            self._vad.reset()
        
        print("[Buffer] Reset")


class SimpleAudioBuffer:
    """
    Simple time-based audio buffer without VAD.
    
    Triggers transcription at fixed intervals for simpler use cases.
    """
    
    SAMPLE_RATE = 16000
    
    def __init__(
        self,
        on_segment_ready: Callable[[np.ndarray], None],
        segment_duration: float = 3.0,
    ):
        """
        Initialize simple buffer.
        
        Args:
            on_segment_ready: Callback when segment is ready
            segment_duration: Duration before triggering (seconds)
        """
        self.on_segment_ready = on_segment_ready
        self.segment_duration = segment_duration
        
        self._buffer: List[np.ndarray] = []
        self._buffer_samples = 0
        self._target_samples = int(self.SAMPLE_RATE * segment_duration)
        self._lock = threading.Lock()
    
    def add_audio(self, audio: np.ndarray) -> None:
        """Add audio chunk to buffer."""
        with self._lock:
            self._buffer.append(audio)
            self._buffer_samples += len(audio)
            
            if self._buffer_samples >= self._target_samples:
                audio_data = np.concatenate(self._buffer)
                self._buffer = []
                self._buffer_samples = 0
                
                # Trigger in background thread
                threading.Thread(
                    target=self.on_segment_ready,
                    args=(audio_data,),
                    daemon=True,
                ).start()
    
    def reset(self) -> None:
        """Reset buffer."""
        with self._lock:
            self._buffer = []
            self._buffer_samples = 0
