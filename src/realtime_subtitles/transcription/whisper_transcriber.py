"""
Whisper-based speech recognition using faster-whisper.

Provides real-time speech-to-text using optimized Whisper models.
"""

import time
from typing import Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path
import numpy as np

try:
    from faster_whisper import WhisperModel
except ImportError:
    raise ImportError(
        "faster-whisper is required. Install it with: pip install faster-whisper"
    )


@dataclass
class TranscriptionResult:
    """Result of a transcription."""
    text: str
    language: str
    confidence: float
    duration: float  # Processing duration in seconds
    

class WhisperTranscriber:
    """
    Real-time speech transcription using Faster-Whisper.
    
    Faster-Whisper uses CTranslate2 for optimized inference,
    providing 4x faster transcription than OpenAI's original implementation.
    
    Example:
        >>> transcriber = WhisperTranscriber(model_size="base")
        >>> result = transcriber.transcribe(audio_array)
        >>> print(result.text)
    """
    
    # Available model sizes (speed vs accuracy trade-off)
    # Updated for 2024 - includes turbo and distil variants
    MODEL_SIZES = [
        # Standard models
        "tiny", "base", "small", "medium", "large-v3",
        # Turbo model (Oct 2024) - 8x faster than large-v3
        "deepdml/faster-whisper-large-v3-turbo-ct2",
        # Distil models - faster with similar accuracy
        "distil-large-v3", "distil-medium.en", "distil-small.en",
    ]
    
    # Map friendly names to HuggingFace model paths
    MODEL_ALIASES = {
        "large-v3-turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
    }
    
    # Known Whisper hallucinations to filter out
    HALLUCINATION_PATTERNS = [
        # Japanese
        "ご視聴ありがとうございました",
        "ご視聴ありがとうございます",
        "チャンネル登録よろしくお願いします",
        "チャンネル登録お願いします",
        "また次の動画でお会いしましょう",
        "次の動画でお会いしましょう",
        "いいねボタンを押してください",
        "高評価お願いします",
        # English
        "Thank you for watching",
        "Thanks for watching",
        "Please subscribe",
        "Subscribe to my channel",
        "Don't forget to subscribe",
        "Like and subscribe",
        "See you in the next video",
        # Chinese
        "感謝您的觀看",
        "感谢您的观看",
        "請訂閱我的頻道",
        "请订阅我的频道",
        "謝謝收看",
        "谢谢收看",
        # Korean
        "시청해 주셔서 감사합니다",
        "구독과 좋아요 부탁드립니다",
    ]
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: Optional[str] = None,
    ):
        """
        Initialize the Whisper transcriber.
        
        Args:
            model_size: Model size - "tiny", "base", "small", "medium", "large-v3",
                       "large-v3-turbo", "distil-large-v3"
                       Smaller = faster but less accurate
            device: "cuda", "cpu", or "auto" (auto-detect)
            compute_type: "float16", "int8", "float32", or "auto"
            language: Language code (e.g., "en", "zh", "ja") or None for auto-detect
        """
        # Resolve model alias if needed
        actual_model = self.MODEL_ALIASES.get(model_size, model_size)
        
        self.model_size = model_size  # Keep original name for display
        self._actual_model = actual_model  # Use this for loading
        self.language = language
        self._model: Optional[WhisperModel] = None
        
        # Determine device and compute type
        if device == "auto":
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
            
        self._device = device
        self._compute_type = compute_type
        
        print(f"[WhisperTranscriber] Initializing {model_size} model on {device}")
        print(f"[WhisperTranscriber] Compute type: {compute_type}")
        
    def _ensure_model_loaded(self) -> None:
        """Lazy load the model on first use."""
        if self._model is None:
            print(f"[WhisperTranscriber] Loading model (this may take a moment)...")
            start = time.time()
            
            # Try to load from project directory first
            model_path = self._get_local_model_path()
            if model_path:
                print(f"[WhisperTranscriber] Using local model: {model_path}")
                self._model = WhisperModel(
                    str(model_path),
                    device=self._device,
                    compute_type=self._compute_type,
                )
            else:
                # Fall back to HuggingFace download (will auto-download)
                print(f"[WhisperTranscriber] Model not found locally, using HuggingFace...")
                self._model = WhisperModel(
                    self._actual_model,
                    device=self._device,
                    compute_type=self._compute_type,
                )
            print(f"[WhisperTranscriber] Model loaded in {time.time() - start:.1f}s")
    
    def _get_local_model_path(self) -> Optional[Path]:
        """Get path to local model in project directory if exists."""
        # Map model sizes to local folder names
        model_folder_map = {
            "large-v3": "faster-whisper-large-v3",
            "large-v3-turbo": "faster-whisper-large-v3-turbo-ct2",
            "medium": "faster-whisper-medium",
        }
        
        folder_name = model_folder_map.get(self.model_size)
        if not folder_name:
            return None
        
        # Find project root
        current = Path(__file__).resolve()
        project_root = current.parent.parent.parent.parent
        model_path = project_root / "models" / folder_name
        
        # Check if model exists
        if model_path.exists() and any(model_path.glob("*.bin")):
            return model_path
        
        return None
    
    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.
        
        Args:
            audio: Audio data as float32 numpy array, normalized to [-1, 1]
            sample_rate: Sample rate in Hz (should be 16000 for Whisper)
            
        Returns:
            TranscriptionResult with transcribed text and metadata
        """
        self._ensure_model_loaded()
        
        # Ensure correct sample rate
        if sample_rate != 16000:
            raise ValueError("Audio must be 16kHz for Whisper")
        
        # Ensure float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        start_time = time.time()
        
        # Transcribe
        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,  # Built-in VAD to skip silence
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )
        
        # Collect all segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())
        
        full_text = " ".join(text_parts)
        
        # Filter out hallucinations
        full_text = self._filter_hallucinations(full_text)
        
        duration = time.time() - start_time
        
        return TranscriptionResult(
            text=full_text,
            language=info.language,
            confidence=info.language_probability,
            duration=duration,
        )
    
    def _filter_hallucinations(self, text: str) -> str:
        """Filter out known Whisper hallucinations."""
        if not text:
            return text
        
        # Check if entire text is a hallucination
        text_stripped = text.strip()
        for pattern in self.HALLUCINATION_PATTERNS:
            if text_stripped == pattern or text_stripped.lower() == pattern.lower():
                print(f"[Whisper] Filtered hallucination: {text_stripped}")
                return ""
            # Also check if text starts/ends with hallucination
            if text_stripped.startswith(pattern) or text_stripped.endswith(pattern):
                text_stripped = text_stripped.replace(pattern, "").strip()
        
        return text_stripped
    
    def transcribe_stream(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> Tuple[str, bool]:
        """
        Transcribe audio for streaming use case.
        
        Returns partial results quickly for lower latency.
        
        Args:
            audio: Audio chunk as float32 numpy array
            sample_rate: Sample rate (must be 16000)
            
        Returns:
            Tuple of (transcribed text, is_final)
            is_final indicates if this is a complete sentence
        """
        self._ensure_model_loaded()
        
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # For streaming, use faster settings
        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=1,  # Faster, slightly less accurate
            best_of=1,
            temperature=0,
            condition_on_previous_text=False,
            vad_filter=True,
        )
        
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())
        
        text = " ".join(text_parts)
        
        # Simple heuristic: if text ends with punctuation, it's likely final
        is_final = text.endswith((".", "!", "?", "。", "！", "？"))
        
        return text, is_final


# Quick test
if __name__ == "__main__":
    import wave
    import sys
    
    print("Whisper Transcriber Test")
    print("=" * 40)
    
    # Create test audio (silence with a beep)
    duration = 2.0
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))
    # Generate a simple sine wave as test audio
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    
    print(f"Test audio: {duration}s at {sample_rate}Hz")
    
    # Test transcriber
    transcriber = WhisperTranscriber(model_size="tiny")
    
    print("\nTranscribing test audio...")
    result = transcriber.transcribe(audio)
    
    print(f"\nResult:")
    print(f"  Text: '{result.text}'")
    print(f"  Language: {result.language} (confidence: {result.confidence:.2%})")
    print(f"  Processing time: {result.duration:.2f}s")
    print(f"  RTF: {result.duration / duration:.2f}")
