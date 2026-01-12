"""
Vosk Streaming Transcriber for real-time speech recognition.

Provides true streaming transcription with incremental output,
no repetition issues unlike sliding window approaches.
"""

import json
import os
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional, Callable
import numpy as np

# Vosk import with error handling
try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    Model = None
    KaldiRecognizer = None


class VoskTranscriber:
    """
    Vosk-based streaming transcriber.
    
    Features:
    - True streaming: outputs text incrementally
    - No repetition: only outputs new content
    - Low latency: <0.5 second delay
    - Offline: no internet required
    """
    
    # Model URLs - using best models for each language
    MODELS = {
        # Chinese - best accuracy model
        "zh": {
            "name": "vosk-model-cn-kaldi-multicn-0.15",
            "url": "https://alphacephei.com/vosk/models/vosk-model-cn-kaldi-multicn-0.15.zip",
            "size": "1.5GB",
        },
        "zh-small": {
            "name": "vosk-model-small-cn-0.22",
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip",
            "size": "42MB",
        },
        # Japanese - best accuracy model
        "ja": {
            "name": "vosk-model-ja-0.22",
            "url": "https://alphacephei.com/vosk/models/vosk-model-ja-0.22.zip",
            "size": "1GB",
        },
        # English - best accuracy model
        "en": {
            "name": "vosk-model-en-us-0.22",
            "url": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
            "size": "1.8GB",
        },
        "en-small": {
            "name": "vosk-model-small-en-us-0.15",
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            "size": "40MB",
        },
    }
    
    SAMPLE_RATE = 16000
    
    def __init__(
        self,
        language: str = "zh",
        model_path: Optional[str] = None,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Vosk transcriber.
        
        Args:
            language: Language code (zh, zh-small, en, en-small)
            model_path: Custom model path (overrides language)
            on_partial: Callback for partial results
            on_final: Callback for final results
        """
        if not VOSK_AVAILABLE:
            raise ImportError("Vosk is not installed. Run: pip install vosk")
        
        self.language = language
        self.on_partial = on_partial
        self.on_final = on_final
        
        # Suppress Vosk logging
        SetLogLevel(-1)
        
        # Load model
        if model_path:
            self._model_path = model_path
        else:
            self._model_path = self._get_or_download_model(language)
        
        print(f"[VoskTranscriber] Loading model from {self._model_path}")
        self._model = Model(self._model_path)
        self._recognizer = KaldiRecognizer(self._model, self.SAMPLE_RATE)
        self._recognizer.SetWords(False)  # We don't need word-level timestamps
        
        # State
        self._partial_text = ""
        self._final_text = ""
        
        print(f"[VoskTranscriber] Initialized with language={language}")
    
    def _get_model_dir(self) -> Path:
        """Get the model directory (project directory)."""
        # Use project directory for portability
        current = Path(__file__).resolve()
        project_root = current.parent.parent.parent.parent
        models_dir = project_root / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir
    
    def _get_or_download_model(self, language: str) -> str:
        """Get model path, downloading if necessary."""
        if language not in self.MODELS:
            raise ValueError(f"Unknown language: {language}. Available: {list(self.MODELS.keys())}")
        
        model_info = self.MODELS[language]
        model_dir = self._get_model_dir()
        model_path = model_dir / model_info["name"]
        
        if model_path.exists():
            print(f"[VoskTranscriber] Using local model: {model_path}")
            return str(model_path)
        
        # Need to download
        print(f"[VoskTranscriber] Downloading model: {model_info['name']} ({model_info['size']})")
        print(f"[VoskTranscriber] This may take a while...")
        
        zip_path = model_dir / f"{model_info['name']}.zip"
        
        # Download with progress
        def report_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(100, downloaded * 100 // total_size)
            print(f"\r[VoskTranscriber] Downloading: {percent}%", end="", flush=True)
        
        urllib.request.urlretrieve(model_info["url"], zip_path, report_progress)
        print()  # New line after progress
        
        # Extract
        print(f"[VoskTranscriber] Extracting model...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(model_dir)
        
        # Remove zip file
        zip_path.unlink()
        
        print(f"[VoskTranscriber] Model ready: {model_path}")
        return str(model_path)
    
    def process_audio(self, audio: np.ndarray) -> tuple[str, bool]:
        """
        Process audio data and get transcription.
        
        Args:
            audio: Audio samples (float32, 16kHz mono)
        
        Returns:
            Tuple of (text, is_final)
        """
        # Convert to int16 for Vosk
        audio_int16 = (audio * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()
        
        # Process
        if self._recognizer.AcceptWaveform(audio_bytes):
            # Final result
            result = json.loads(self._recognizer.Result())
            text = result.get("text", "")
            if text:
                self._final_text = text
                if self.on_final:
                    self.on_final(text)
                return text, True
        else:
            # Partial result
            result = json.loads(self._recognizer.PartialResult())
            text = result.get("partial", "")
            if text:
                self._partial_text = text
                if self.on_partial:
                    self.on_partial(text)
                return text, False
        
        return self._partial_text or self._final_text, False
    
    def reset(self) -> None:
        """Reset the recognizer state."""
        self._recognizer = KaldiRecognizer(self._model, self.SAMPLE_RATE)
        self._partial_text = ""
        self._final_text = ""
    
    def get_final_result(self) -> str:
        """Get any remaining final result."""
        result = json.loads(self._recognizer.FinalResult())
        return result.get("text", "")


# Quick test
if __name__ == "__main__":
    print("Testing Vosk Transcriber...")
    
    try:
        transcriber = VoskTranscriber(language="zh-small")
        print("Transcriber initialized successfully!")
        
        # Test with silence
        silence = np.zeros(16000, dtype=np.float32)
        text, is_final = transcriber.process_audio(silence)
        print(f"Test result: '{text}', is_final={is_final}")
        
    except Exception as e:
        print(f"Error: {e}")
