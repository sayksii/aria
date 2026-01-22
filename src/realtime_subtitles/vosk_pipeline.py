"""
Unified Streaming Pipeline for real-time transcription.

Uses the best engine for each language:
- Chinese (zh): Sherpa-ONNX (high accuracy)
- English (en): Sherpa-ONNX (high accuracy)
- Japanese (ja): Vosk (Sherpa doesn't support Japanese)
"""

import threading
import queue
import time
from typing import Optional, Callable, Union
import numpy as np

from .audio.capture import AudioCapture
from .pipeline import SubtitleEvent
from .logger import info, debug, warning, error

# Import transcribers with fallbacks
try:
    from .transcription.sherpa_transcriber import SherpaTranscriber, SHERPA_AVAILABLE
except ImportError:
    SHERPA_AVAILABLE = False
    SherpaTranscriber = None

try:
    from .transcription.vosk_transcriber import VoskTranscriber, VOSK_AVAILABLE
except ImportError:
    VOSK_AVAILABLE = False
    VoskTranscriber = None

# Translation support (optional)
try:
    from .translation.translator import create_translator, CTRANSLATE2_AVAILABLE, GOOGLETRANS_AVAILABLE
    TRANSLATION_AVAILABLE = CTRANSLATE2_AVAILABLE or GOOGLETRANS_AVAILABLE
    debug(f"Translation module loaded, CTRANSLATE2={CTRANSLATE2_AVAILABLE}, GOOGLE={GOOGLETRANS_AVAILABLE}")
except ImportError as e:
    warning(f"Translation import failed: {e}")
    TRANSLATION_AVAILABLE = False
    create_translator = None


class StreamingPipeline:
    """
    Unified streaming transcription pipeline.
    
    Automatically selects the best engine for each language:
    - zh/en: Sherpa-ONNX (better accuracy)
    - ja: Vosk (Sherpa doesn't have Japanese model)
    """
    
    # Engine selection by language
    ENGINE_MAP = {
        "zh": "sherpa",
        "en": "sherpa",
        "ja": "vosk",
    }
    
    def __init__(
        self,
        language: str = "zh",
        on_subtitle: Optional[Callable[[SubtitleEvent], None]] = None,
        max_lines: int = 4,
        # Translation settings
        enable_translation: bool = False,
        translation_engine: str = "google",
        target_language: str = "zh",
    ):
        """
        Initialize the streaming pipeline.
        
        Args:
            language: Language code (zh, en, ja)
            on_subtitle: Callback for subtitle events
            max_lines: Maximum lines to display
            enable_translation: Whether to enable translation
            translation_engine: "google" or "nllb"
            target_language: Target language for translation
        """
        self.language = language
        self.on_subtitle = on_subtitle or self._default_callback
        self.max_lines = max_lines
        self.enable_translation = enable_translation
        self.translation_engine = translation_engine
        self.target_language = target_language
        
        # Determine which engine to use
        engine = self.ENGINE_MAP.get(language, "sherpa")
        
        # Create transcriber based on engine
        if engine == "sherpa":
            if not SHERPA_AVAILABLE:
                raise ImportError("sherpa-onnx is required. Run: pip install sherpa-onnx")
            self._transcriber = SherpaTranscriber(language=language)
            self._engine_name = "Sherpa"
        else:  # vosk
            if not VOSK_AVAILABLE:
                raise ImportError("Vosk is required. Run: pip install vosk")
            self._transcriber = VoskTranscriber(language=language)
            self._engine_name = "Vosk"
        
        # Translation (optional)
        self._translator = None
        if enable_translation and TRANSLATION_AVAILABLE:
            try:
                self._translator = create_translator(
                    engine=translation_engine,
                    target_language=target_language,
                )
            except Exception as e:
                warning(f"Translation init failed: {e}")
                self._translator = None
        
        # Audio capture
        self._audio_capture = AudioCapture()
        
        # Display state
        self._lines: list = []  # History of final results
        self._translation_lines: list = []  # History of translation results
        self._current_partial = ""
        
        # State
        self._running = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._process_thread: Optional[threading.Thread] = None
        
        trans_status = "enabled" if self._translator else "disabled"
        info(f"Using {self._engine_name} for {language}, translation={trans_status}")
    
    def _default_callback(self, event: SubtitleEvent) -> None:
        """Default subtitle callback."""
        debug(f"[{event.language}] {event.text}")
    
    def _on_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """Callback from AudioCapture."""
        self._audio_queue.put(audio)
    
    def _process_loop(self) -> None:
        """Background thread for audio processing."""
        while self._running:
            try:
                audio = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Process with transcriber
            text, is_final = self._transcriber.process_audio(audio)
            
            if not text:
                continue
            
            translated_text = None
            if is_final:
                # Final result - add to history
                if text and text != (self._lines[-1] if self._lines else ""):
                    self._lines.append(text)
                    # Keep only recent lines
                    if len(self._lines) > self.max_lines:
                        self._lines = self._lines[-self.max_lines:]
                    
                    # Translate this line and add to translation history
                    if self._translator:
                        try:
                            line_translation = self._translator.translate(text)
                            if line_translation:
                                self._translation_lines.append(line_translation)
                                # Keep translation lines in sync with original
                                if len(self._translation_lines) > self.max_lines:
                                    self._translation_lines = self._translation_lines[-self.max_lines:]
                                debug(f"Translated: {text[:30]}... -> {line_translation[:30]}...")
                        except Exception as e:
                            warning(f"Translation error: {e}")
                
                self._current_partial = ""
            else:
                # Partial result - no translation for partial
                self._current_partial = text
            
            # Build display text
            display_text = self._get_display_text()
            
            # Build translation display (join all translation lines) - only if translation enabled
            if self._translator and self._translation_lines:
                translated_text = "\n".join(self._translation_lines[-self.max_lines:])
            
            if display_text:
                event = SubtitleEvent(
                    text=display_text,
                    language=self.language,
                    confidence=1.0,
                    timestamp=time.time(),
                    is_partial=not is_final,
                    translated_text=translated_text,
                    target_language=self.target_language if translated_text else None,
                )
                self.on_subtitle(event)
    
    def _get_display_text(self) -> str:
        """Get full display text with history + partial."""
        lines = self._lines.copy()
        if self._current_partial:
            lines.append(self._current_partial)
        
        # Keep only last N lines
        lines = lines[-self.max_lines:]
        
        return "\n".join(lines)
    
    def start(self) -> None:
        """Start the streaming pipeline."""
        if self._running:
            return
        
        self._running = True
        self._lines.clear()
        self._current_partial = ""
        
        # Start processing thread
        self._process_thread = threading.Thread(
            target=self._process_loop,
            daemon=True,
        )
        self._process_thread.start()
        
        # Start audio capture
        self._audio_capture.start(callback=self._on_audio)
        
        info(f"StreamingPipeline started ({self._engine_name})")
    
    def stop(self) -> None:
        """Stop the pipeline."""
        self._running = False
        
        self._audio_capture.stop()
        
        if self._process_thread:
            self._process_thread.join(timeout=2.0)
        
        # Clear queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Get any final result
        final = self._transcriber.get_final_result()
        if final:
            self._lines.append(final)
        
        info("StreamingPipeline stopped")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


# Backward compatibility alias
VoskStreamingPipeline = StreamingPipeline
