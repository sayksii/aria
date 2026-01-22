"""
Real-time transcription pipeline.

Combines audio capture, VAD, buffering, and transcription into
a seamless real-time subtitle generation system.
"""

import threading
import queue
import time
from typing import Optional, Callable
from dataclasses import dataclass
import numpy as np

from .audio.capture import AudioCapture
from .audio.buffer import StreamingAudioBuffer, SimpleAudioBuffer
from .transcription.whisper_transcriber import WhisperTranscriber, TranscriptionResult
from .logger import info, debug, warning, error

# Translation support (optional)
try:
    from .translation.translator import create_translator, CTRANSLATE2_AVAILABLE, GOOGLETRANS_AVAILABLE
    TRANSLATION_AVAILABLE = CTRANSLATE2_AVAILABLE or GOOGLETRANS_AVAILABLE
except ImportError:
    TRANSLATION_AVAILABLE = False
    create_translator = None


@dataclass
class SubtitleEvent:
    """A subtitle event with text and metadata."""
    text: str
    language: str
    confidence: float
    timestamp: float
    is_partial: bool = False
    translated_text: Optional[str] = None  # Translation (if enabled)
    target_language: Optional[str] = None  # Target language for translation


class RealtimePipeline:
    """
    Complete real-time transcription pipeline.
    
    Flow:
    1. AudioCapture -> captures system audio
    2. VAD/Buffer -> detects speech, manages buffering
    3. Whisper -> transcribes speech segments
    4. Callback -> delivers subtitle events
    
    Example:
        >>> def on_subtitle(event: SubtitleEvent):
        ...     print(f"[{event.language}] {event.text}")
        >>> 
        >>> pipeline = RealtimePipeline(
        ...     model="base",
        ...     language="en",
        ...     on_subtitle=on_subtitle,
        ... )
        >>> pipeline.start()
    """
    
    def __init__(
        self,
        model: str = "base",
        language: Optional[str] = None,
        on_subtitle: Optional[Callable[[SubtitleEvent], None]] = None,
        use_vad: bool = True,
        vad_silence_ms: int = 100,
        min_segment_duration: float = 1.0,
        max_segment_duration: float = 5.0,
        # Translation settings
        enable_translation: bool = False,
        translation_engine: str = "google",
        target_language: str = "zh",
    ):
        """
        Initialize the pipeline.
        
        Args:
            model: Whisper model size
            language: Language code or None for auto-detect
            on_subtitle: Callback for subtitle events
            use_vad: Whether to use VAD for speech detection
            vad_silence_ms: Silence duration to end speech (milliseconds)
            min_segment_duration: Minimum speech duration before transcribing
            max_segment_duration: Maximum speech duration before forcing transcription
            enable_translation: Whether to enable translation
            translation_engine: "google" or "nllb"
            target_language: Target language for translation
        """
        self.on_subtitle = on_subtitle or self._default_callback
        self.use_vad = use_vad
        self.enable_translation = enable_translation
        self.translation_engine = translation_engine
        self.target_language = target_language
        
        # Components
        self._audio_capture = AudioCapture()
        self._transcriber = WhisperTranscriber(
            model_size=model,
            language=language,
        )
        
        # Translation (optional)
        self._translator = None
        if enable_translation and TRANSLATION_AVAILABLE:
            try:
                self._translator = create_translator(
                    engine=translation_engine,
                    target_language=target_language,
                )
            except Exception as e:
                warning(f"Pipeline: Translation init failed: {e}")
                self._translator = None
        
        # Buffer - choose based on VAD setting
        if use_vad:
            self._buffer = StreamingAudioBuffer(
                on_segment_ready=self._on_audio_segment,
                min_segment_duration=min_segment_duration,
                max_segment_duration=max_segment_duration,
                speech_pad_ms=vad_silence_ms,  # Use VAD silence setting
                use_vad=True,
            )
        else:
            self._buffer = SimpleAudioBuffer(
                on_segment_ready=self._on_audio_segment,
                segment_duration=min_segment_duration,
            )
        
        # State
        self._running = False
        # Use a limited queue to prevent unbounded latency
        # If transcription can't keep up, old segments will be dropped
        self._transcription_queue: queue.Queue = queue.Queue(maxsize=3)
        self._transcription_thread: Optional[threading.Thread] = None
        self._dropped_segments = 0  # Track how many segments were dropped
        
        # Display state (like realtime mode)
        self.max_lines = 3  # Maximum lines to display
        self._lines: list = []  # History of lines
        self._translation_lines: list = []  # History of translation lines
        
        trans_status = "enabled" if self._translator else "disabled"
        info(f"Pipeline: Initialized model={model}, language={language or 'auto'}, VAD={use_vad}, translation={trans_status}")
    
    def _split_into_lines(self, text: str, max_chars_per_line: int = 55) -> list:
        """
        Split long text into multiple lines.
        
        Args:
            text: Text to split
            max_chars_per_line: Maximum characters per line
            
        Returns:
            List of lines
        """
        if len(text) <= max_chars_per_line:
            return [text]
        
        lines = []
        current_line = ""
        
        # Split by spaces for English, or character by character for CJK
        words = text.split(' ')
        
        for word in words:
            # Check if adding this word would exceed the limit
            test_line = current_line + (' ' if current_line else '') + word
            
            if len(test_line) <= max_chars_per_line:
                current_line = test_line
            else:
                # Current line is full
                if current_line:
                    lines.append(current_line)
                
                # Handle very long words (like CJK text without spaces)
                if len(word) > max_chars_per_line:
                    # Split long word into chunks
                    for i in range(0, len(word), max_chars_per_line):
                        chunk = word[i:i + max_chars_per_line]
                        if i + max_chars_per_line < len(word):
                            lines.append(chunk)
                        else:
                            current_line = chunk
                else:
                    current_line = word
        
        # Don't forget the last line
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _default_callback(self, event: SubtitleEvent) -> None:
        """Default subtitle callback - prints to console."""
        print(f"\r\033[K[{event.language}] {event.text}")
    
    def _on_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """Callback from AudioCapture - feeds into buffer."""
        self._buffer.add_audio(audio)
    
    def _on_audio_segment(self, audio: np.ndarray) -> None:
        """Callback from Buffer - queues for transcription."""
        debug(f"Pipeline: Audio segment received ({len(audio)/16000:.1f}s)")
        try:
            # Try to add to queue, but don't block if full
            self._transcription_queue.put_nowait(audio)
        except queue.Full:
            # Queue is full - drop the oldest segment and add new one
            try:
                self._transcription_queue.get_nowait()  # Remove oldest
                self._transcription_queue.put_nowait(audio)  # Add newest
                self._dropped_segments += 1
                if self._dropped_segments % 5 == 1:  # Log every 5 drops
                    warning(f"Pipeline: Dropped {self._dropped_segments} segments (transcription can't keep up)")
            except queue.Empty:
                pass
    
    def _transcription_loop(self) -> None:
        """Background thread for transcription."""
        while self._running:
            try:
                audio = self._transcription_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Check if we're falling behind and skip if too many queued
            queue_size = self._transcription_queue.qsize()
            if queue_size >= 2:
                warning(f"Pipeline: Queue backup ({queue_size} segments), skipping older audio")
                continue  # Skip this segment to catch up
            
            # Skip if too short
            duration = len(audio) / 16000
            if duration < 0.3:
                continue
            
            # Transcribe
            try:
                result = self._transcriber.transcribe(audio)
                
                if result.text.strip():
                    text = result.text.strip()
                    
                    # Split text into lines, keep only last max_lines
                    lines = self._split_into_lines(text, max_chars_per_line=45)
                    display_lines = lines[-self.max_lines:]  # Only show last 5 lines
                    display_text = "\n".join(display_lines)
                    
                    # Translate if enabled
                    translated_display = None
                    if self._translator:
                        try:
                            translated = self._translator.translate(text)
                            if translated:
                                # Split translation into lines too, keep only last max_lines
                                trans_lines = self._split_into_lines(translated, max_chars_per_line=45)
                                trans_display_lines = trans_lines[-self.max_lines:]
                                translated_display = "\n".join(trans_display_lines)
                                debug(f"Pipeline: Translated: {text[:30]}... -> {translated[:30]}...")
                        except Exception as e:
                            warning(f"Pipeline: Translation error: {e}")
                    
                    event = SubtitleEvent(
                        text=display_text,
                        language=result.language,
                        confidence=result.confidence,
                        timestamp=time.time(),
                        translated_text=translated_display,
                        target_language=self.target_language if translated_display else None,
                    )
                    self.on_subtitle(event)
            except Exception as e:
                error(f"Pipeline: Transcription error: {e}")
    
    def start(self) -> None:
        """Start the real-time pipeline."""
        if self._running:
            return
        
        # Pre-load models BEFORE starting audio capture to avoid queue buildup
        info("Pipeline: Pre-loading models...")
        
        # Load Whisper model (this triggers lazy loading)
        self._transcriber._ensure_model_loaded()
        
        # Pre-load translation model if enabled
        if self._translator:
            try:
                # Warm up translator with a test translation
                self._translator.translate("test")
                info("Pipeline: Translation model ready")
            except Exception as e:
                warning(f"Pipeline: Translation warmup failed: {e}")
        
        info("Pipeline: All models loaded, starting audio capture...")
        
        self._running = True
        
        # Start transcription thread
        self._transcription_thread = threading.Thread(
            target=self._transcription_loop,
            daemon=True,
        )
        self._transcription_thread.start()
        
        # Start audio capture AFTER models are loaded
        self._audio_capture.start(callback=self._on_audio)
        
        info("Pipeline: Started")
    
    def stop(self) -> None:
        """Stop the pipeline and release resources."""
        self._running = False
        
        self._audio_capture.stop()
        self._buffer.reset()
        
        if self._transcription_thread:
            self._transcription_thread.join(timeout=2.0)
        
        # Clear queue
        while not self._transcription_queue.empty():
            try:
                self._transcription_queue.get_nowait()
            except queue.Empty:
                break
        
        # Release Whisper model to free CUDA memory
        if hasattr(self, '_transcriber') and self._transcriber:
            if hasattr(self._transcriber, '_model') and self._transcriber._model is not None:
                del self._transcriber._model
                self._transcriber._model = None
                info("Pipeline: Released Whisper model")
        
        # Release translator model
        if hasattr(self, '_translator') and self._translator:
            if hasattr(self._translator, 'model'):
                del self._translator.model
            if hasattr(self._translator, 'tokenizer'):
                del self._translator.tokenizer
            self._translator = None
            info("Pipeline: Released translator model")
        
        # Clear CUDA cache
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                info("Pipeline: Cleared CUDA cache")
        except ImportError:
            pass
        except Exception as e:
            warning(f"Pipeline: Failed to clear CUDA cache: {e}")
        
        # Clear display history
        self._lines = []
        self._translation_lines = []
        
        info("Pipeline: Stopped")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


# CLI interface
def run_cli(
    model: str = "base",
    language: Optional[str] = None,
    use_vad: bool = True,
) -> None:
    """Run the pipeline in CLI mode."""
    
    print("=" * 60)
    print("ARIA - Pipeline Mode")
    print("=" * 60)
    print(f"Model: {model}")
    print(f"Language: {language or 'auto-detect'}")
    print(f"VAD: {'enabled' if use_vad else 'disabled'}")
    print("=" * 60)
    print("\nListening for audio... Press Ctrl+C to stop.\n")
    
    def on_subtitle(event: SubtitleEvent):
        # Format output
        print(f"[{event.language}] {event.text}")
    
    pipeline = RealtimePipeline(
        model=model,
        language=language,
        on_subtitle=on_subtitle,
        use_vad=use_vad,
    )
    
    try:
        pipeline.start()
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    run_cli()
