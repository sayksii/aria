"""
Sherpa-ONNX Streaming Transcriber for real-time speech recognition.

Uses Sherpa-ONNX for high-accuracy streaming transcription.
Better than Vosk for Chinese and English.
"""

import os
import tarfile
import urllib.request
import time
from pathlib import Path
from typing import Optional, Callable
import numpy as np

from ..logger import info, debug, warning

# Sherpa import with error handling
try:
    import sherpa_onnx
    SHERPA_AVAILABLE = True
except ImportError:
    SHERPA_AVAILABLE = False


class SherpaTranscriber:
    """
    Sherpa-ONNX based streaming transcriber.
    
    Features:
    - True streaming: outputs text incrementally
    - High accuracy: uses latest Zipformer models
    - No repetition: proper streaming architecture
    - Offline: no internet required after model download
    """
    
    # Model configurations
    MODELS = {
        "zh": {
            "name": "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20",
            "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2",
            "encoder": "encoder-epoch-99-avg-1.onnx",
            "decoder": "decoder-epoch-99-avg-1.onnx",
            "joiner": "joiner-epoch-99-avg-1.onnx",
            "tokens": "tokens.txt",
        },
        "en": {
            # Use the same bilingual model (supports both Chinese and English)
            "name": "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20",
            "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2",
            "encoder": "encoder-epoch-99-avg-1.onnx",
            "decoder": "decoder-epoch-99-avg-1.onnx",
            "joiner": "joiner-epoch-99-avg-1.onnx",
            "tokens": "tokens.txt",
        },
    }
    
    SAMPLE_RATE = 16000
    
    def __init__(
        self,
        language: str = "zh",
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Sherpa transcriber.
        
        Args:
            language: Language code (zh, en)
            on_partial: Callback for partial results
            on_final: Callback for final results
        """
        if not SHERPA_AVAILABLE:
            raise ImportError("sherpa-onnx is not installed. Run: pip install sherpa-onnx")
        
        if language not in self.MODELS:
            raise ValueError(f"Unknown language: {language}. Available: {list(self.MODELS.keys())}")
        
        self.language = language
        self.on_partial = on_partial
        self.on_final = on_final
        
        # Get or download model
        model_path = self._get_or_download_model(language)
        model_info = self.MODELS[language]
        
        # Create recognizer config
        debug(f"SherpaTranscriber: Loading model from {model_path}")
        
        encoder = str(model_path / model_info["encoder"])
        decoder = str(model_path / model_info["decoder"])
        joiner = str(model_path / model_info["joiner"])
        tokens = str(model_path / model_info["tokens"])
        
        self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            tokens=tokens,
            num_threads=4,
            sample_rate=self.SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
        )
        
        # Create stream
        self._stream = self._recognizer.create_stream()
        
        # State
        self._last_text = ""
        self._last_change_time = time.time()
        self._stable_timeout = 0.8  # seconds of stable text before marking as final
        self._text_finalized = False
        self._max_segment_length = 80  # force new segment after this many characters
        
        info(f"SherpaTranscriber: Initialized with language={language}")
    
    def _get_model_dir(self) -> Path:
        """Get the model directory (project directory)."""
        # Use project directory for portability
        current = Path(__file__).resolve()
        project_root = current.parent.parent.parent.parent
        models_dir = project_root / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir
    
    def _get_or_download_model(self, language: str) -> Path:
        """Get model path, downloading if necessary."""
        model_info = self.MODELS[language]
        model_dir = self._get_model_dir()
        model_path = model_dir / model_info["name"]
        
        if model_path.exists():
            debug(f"SherpaTranscriber: Using local model: {model_path}")
            return model_path
        
        # Need to download
        info(f"SherpaTranscriber: Downloading model: {model_info['name']}")
        info("SherpaTranscriber: This may take a while...")
        
        tar_path = model_dir / f"{model_info['name']}.tar.bz2"
        
        # Download with progress
        def report_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(100, downloaded * 100 // total_size) if total_size > 0 else 0
            pass  # Suppress progress output
        
        urllib.request.urlretrieve(model_info["url"], tar_path, report_progress)
        
        # Extract
        info("SherpaTranscriber: Extracting model...")
        with tarfile.open(tar_path, "r:bz2") as tar:
            tar.extractall(model_dir)
        
        # Remove tar file
        tar_path.unlink()
        
        info(f"SherpaTranscriber: Model ready: {model_path}")
        return model_path
    
    def process_audio(self, audio: np.ndarray) -> tuple[str, bool]:
        """
        Process audio data and get transcription.
        
        Args:
            audio: Audio samples (float32, 16kHz mono)
        
        Returns:
            Tuple of (text, is_final)
        """
        # Feed audio to stream
        self._stream.accept_waveform(self.SAMPLE_RATE, audio)
        
        # Decode
        while self._recognizer.is_ready(self._stream):
            self._recognizer.decode_stream(self._stream)
        
        # Get result - sherpa returns string directly
        result = self._recognizer.get_result(self._stream)
        text = result.strip() if isinstance(result, str) else getattr(result, 'text', '').strip()
        
        is_final = False
        current_time = time.time()
        
        if text and text != self._last_text:
            # Text changed - update last change time, reset finalized flag
            self._last_change_time = current_time
            self._last_text = text
            self._text_finalized = False
            
            # Check if endpoint detected by recognizer OR text is too long
            should_finalize = (
                self._recognizer.is_endpoint(self._stream) or
                len(text) >= self._max_segment_length
            )
            
            if should_finalize:
                is_final = True
                self._text_finalized = True
                if self.on_final:
                    self.on_final(text)
                self._recognizer.reset(self._stream)
                self._last_text = ""
            else:
                if self.on_partial:
                    self.on_partial(text)
        elif text and text == self._last_text and not self._text_finalized:
            # Text is stable and not yet finalized - check if timeout reached
            if current_time - self._last_change_time >= self._stable_timeout:
                is_final = True
                self._text_finalized = True
                if self.on_final:
                    self.on_final(text)
                # Reset for next utterance
                self._recognizer.reset(self._stream)
                self._last_text = ""
        
        return text, is_final
    
    def reset(self) -> None:
        """Reset the recognizer state."""
        self._recognizer.reset(self._stream)
        self._last_text = ""
    
    def get_final_result(self) -> str:
        """Get any remaining final result."""
        # Flush the stream
        tail_paddings = np.zeros(int(self.SAMPLE_RATE * 0.5), dtype=np.float32)
        self._stream.accept_waveform(self.SAMPLE_RATE, tail_paddings)
        
        while self._recognizer.is_ready(self._stream):
            self._recognizer.decode_stream(self._stream)
        
        result = self._recognizer.get_result(self._stream)
        text = result.strip() if isinstance(result, str) else getattr(result, 'text', '').strip()
        return text


# Quick test
if __name__ == "__main__":
    print("Testing Sherpa Transcriber...")
    
    try:
        transcriber = SherpaTranscriber(language="zh")
        print("Transcriber initialized successfully!")
        
        # Test with silence
        silence = np.zeros(16000, dtype=np.float32)
        text, is_final = transcriber.process_audio(silence)
        print(f"Test result: '{text}', is_final={is_final}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
