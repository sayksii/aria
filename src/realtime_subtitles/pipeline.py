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
        vad_silence_ms: int = 300,
        min_segment_duration: float = 1.0,
        max_segment_duration: float = 10.0,
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
                print(f"[Pipeline] Translation init failed: {e}")
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
        self._transcription_queue: queue.Queue = queue.Queue()
        self._transcription_thread: Optional[threading.Thread] = None
        
        trans_status = "enabled" if self._translator else "disabled"
        print(f"[Pipeline] Initialized: model={model}, language={language or 'auto'}, VAD={use_vad}, translation={trans_status}")
    
    def _default_callback(self, event: SubtitleEvent) -> None:
        """Default subtitle callback - prints to console."""
        print(f"\r\033[K[{event.language}] {event.text}")
    
    def _on_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """Callback from AudioCapture - feeds into buffer."""
        self._buffer.add_audio(audio)
    
    def _on_audio_segment(self, audio: np.ndarray) -> None:
        """Callback from Buffer - queues for transcription."""
        self._transcription_queue.put(audio)
    
    def _transcription_loop(self) -> None:
        """Background thread for transcription."""
        while self._running:
            try:
                audio = self._transcription_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Skip if too short
            duration = len(audio) / 16000
            if duration < 0.3:
                continue
            
            # Transcribe
            try:
                result = self._transcriber.transcribe(audio)
                
                if result.text.strip():
                    text = result.text.strip()
                    
                    # Translate if enabled
                    translated = None
                    if self._translator:
                        try:
                            translated = self._translator.translate(text)
                            if translated:
                                print(f"[Pipeline] Translated: {text} -> {translated}")
                        except Exception as e:
                            print(f"[Pipeline] Translation error: {e}")
                    
                    event = SubtitleEvent(
                        text=text,
                        language=result.language,
                        confidence=result.confidence,
                        timestamp=time.time(),
                        translated_text=translated,
                        target_language=self.target_language if translated else None,
                    )
                    self.on_subtitle(event)
            except Exception as e:
                print(f"[Pipeline] Transcription error: {e}")
    
    def start(self) -> None:
        """Start the real-time pipeline."""
        if self._running:
            return
        
        self._running = True
        
        # Start transcription thread
        self._transcription_thread = threading.Thread(
            target=self._transcription_loop,
            daemon=True,
        )
        self._transcription_thread.start()
        
        # Start audio capture
        self._audio_capture.start(callback=self._on_audio)
        
        print("[Pipeline] Started")
    
    def stop(self) -> None:
        """Stop the pipeline."""
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
        
        print("[Pipeline] Stopped")
    
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
