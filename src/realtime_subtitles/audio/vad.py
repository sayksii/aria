"""
Voice Activity Detection (VAD) using Silero VAD.

Simplified implementation that works with any audio chunk size.
"""

import numpy as np
from typing import Optional
import torch


class VoiceActivityDetector:
    """
    Voice Activity Detection using Silero VAD.
    
    This is a simplified implementation that accumulates audio internally
    and processes in fixed 512-sample chunks as required by Silero VAD.
    """
    
    SAMPLE_RATE = 16000
    CHUNK_SIZE = 512  # Silero VAD requires exactly 512 samples for 16kHz
    
    def __init__(
        self,
        threshold: float = 0.4,
        min_speech_duration_ms: int = 150,
        min_silence_duration_ms: int = 300,
    ):
        """
        Initialize the VAD.
        
        Args:
            threshold: Speech probability threshold (0-1). Lower = more sensitive.
            min_speech_duration_ms: Minimum speech duration to trigger speech state.
            min_silence_duration_ms: Minimum silence duration to end speech state.
        """
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        
        # State
        self._is_speech = False
        self._speech_ms = 0
        self._silence_ms = 0
        
        # Audio buffer
        self._buffer = np.array([], dtype=np.float32)
        
        # Model
        self._model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load Silero VAD model."""
        print("[VAD] Loading Silero VAD model...")
        
        self._model, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
            trust_repo=True,
        )
        self._model.reset_states()
        
        print("[VAD] Silero VAD loaded")
    
    def _get_probability(self, chunk: np.ndarray) -> float:
        """Get speech probability for a 512-sample chunk."""
        if len(chunk) != self.CHUNK_SIZE:
            return 0.0
        
        tensor = torch.from_numpy(chunk.astype(np.float32))
        
        with torch.no_grad():
            prob = self._model(tensor, self.SAMPLE_RATE).item()
        
        return prob
    
    def is_speech(self, audio: np.ndarray) -> bool:
        """
        Check if audio contains speech.
        
        Accumulates audio internally and processes in 512-sample chunks.
        Uses hysteresis to avoid rapid state changes.
        
        Args:
            audio: Audio samples as float32 numpy array (any length)
            
        Returns:
            True if currently in speech state
        """
        # Accumulate audio
        self._buffer = np.concatenate([
            self._buffer,
            audio.astype(np.float32)
        ])
        
        # Process all complete chunks
        chunk_duration_ms = (self.CHUNK_SIZE / self.SAMPLE_RATE) * 1000  # 32ms
        
        while len(self._buffer) >= self.CHUNK_SIZE:
            chunk = self._buffer[:self.CHUNK_SIZE]
            self._buffer = self._buffer[self.CHUNK_SIZE:]
            
            prob = self._get_probability(chunk)
            
            if prob >= self.threshold:
                # Speech detected
                self._speech_ms += chunk_duration_ms
                self._silence_ms = 0
                
                if self._speech_ms >= self.min_speech_duration_ms:
                    self._is_speech = True
            else:
                # Silence detected
                self._silence_ms += chunk_duration_ms
                
                if self._silence_ms >= self.min_silence_duration_ms:
                    self._is_speech = False
                    self._speech_ms = 0
        
        return self._is_speech
    
    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speech = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._buffer = np.array([], dtype=np.float32)
        if self._model is not None:
            self._model.reset_states()
