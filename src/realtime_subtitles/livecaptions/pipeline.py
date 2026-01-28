"""
LiveCaptions Pipeline
Integrates LiveCaptions monitoring, text processing, and translation
"""

import threading
import time
from typing import Optional, Callable

from .monitor import LiveCaptionsMonitor, CaptionEvent
from .controller import LiveCaptionsController
from .manager import TranslationStateManager
from ..pipeline import SubtitleEvent
from ..logger import info, debug, warning, error

# Translation support (optional)
try:
    from ..translation.translator import create_translator, CTRANSLATE2_AVAILABLE, GOOGLETRANS_AVAILABLE
    TRANSLATION_AVAILABLE = CTRANSLATE2_AVAILABLE or GOOGLETRANS_AVAILABLE
except ImportError:
    TRANSLATION_AVAILABLE = False
    create_translator = None


class LiveCaptionsPipeline:
    """
    Complete LiveCaptions pipeline
    
    Flow:
    1. Launch Windows LiveCaptions
    2. Monitor caption text
    3. Text deduplication and segmentation
    4. Translation (optional)
    5. Send to subtitle window
    
    Example:
        >>> def on_subtitle(event):
        ...     print(f"[{event.language}] {event.text}")
        ...     if event.translated_text:
        ...         print(f"[Translation] {event.translated_text}")
        >>> 
        >>> pipeline = LiveCaptionsPipeline(
        ...     on_subtitle=on_subtitle,
        ...     enable_translation=True,
        ...     target_language="zho_Hant"
        ... )
        >>> pipeline.start()
    """
    
    def __init__(
        self,
        on_subtitle: Optional[Callable[[SubtitleEvent], None]] = None,
        # Translation settings
        enable_translation: bool = False,
        translation_engine: str = "google",
        target_language: str = "zho_Hant",
        # LiveCaptions settings
        auto_hide_window: bool = True,
        poll_interval: float = 0.1,
    ):
        """
        Initialize the pipeline
        
        Args:
            on_subtitle: Subtitle callback function
            enable_translation: Whether to enable translation
            translation_engine: Translation engine ("google", "nllb")
            target_language: Target language code
            auto_hide_window: Whether to auto-hide LiveCaptions window
            poll_interval: Monitoring poll interval in seconds
        """
        self.on_subtitle = on_subtitle or self._default_callback
        self.enable_translation = enable_translation
        self.auto_hide_window = auto_hide_window
        
        # Check system support
        if not LiveCaptionsController.is_livecaptions_available():
            raise RuntimeError(
                "LiveCaptions is not available on this system. "
                "Windows 11 22H2 or later is required."
            )
        
        # Create monitor
        self._monitor = LiveCaptionsMonitor(
            on_caption=self._on_caption,
            poll_interval=poll_interval
        )
        
        # Translator
        self._translator = None
        if enable_translation and TRANSLATION_AVAILABLE:
            try:
                self._translator = create_translator(
                    engine=translation_engine,
                    target_language=target_language,
                )
                info(f"LiveCaptionsPipeline: Translator initialized ({translation_engine})")
            except Exception as e:
                warning(f"LiveCaptionsPipeline: Translation init failed: {e}")
        
        # State
        self._running = False
        self._last_sent_text = ""
        
        # Translation state manager for incremental translation
        self._translation_manager = None
        if self._translator:
            self._translation_manager = TranslationStateManager(
                translator=self._translator.translate
            )
            info("LiveCaptionsPipeline: TranslationStateManager initialized")
        
        trans_status = "enabled" if self._translator else "disabled"
        info(f"LiveCaptionsPipeline: Initialized, translation={trans_status}")
    
    def _on_caption(self, caption: CaptionEvent):
        """Process caption events"""
        try:
            # Filter out initial placeholder text from LiveCaptions
            initial_texts = [
                "即時輔助字幕",
                "实时辅助字幕", 
                "Ready for live subtitles",
                "Live captions",
                "準備好即時輔助字幕",
                "准备好实时辅助字幕"
            ]
            
            if any(initial_text in caption.text for initial_text in initial_texts):
                debug(f"LiveCaptionsPipeline: Skipping initial placeholder text: {caption.text}")
                return
            
            # Deduplication: avoid sending duplicate content
            if caption.text == self._last_sent_text:
                debug("LiveCaptionsPipeline: Duplicate text, skipping")
                return
            
            # Use translation manager for incremental translation
            committed_translation = None
            draft_translation = None
            translated_text = None
            
            if self._translation_manager:
                try:
                    state = self._translation_manager.process_text(caption.text)
                    committed_translation = state.committed_text
                    draft_translation = state.draft_text
                except Exception as e:
                    warning(f"LiveCaptionsPipeline: Translation manager failed: {e}")
            elif self._translator:
                # Fallback: direct translation without state management
                try:
                    translated_text = self._translator.translate(caption.text)
                except Exception as e:
                    warning(f"LiveCaptionsPipeline: Translation failed: {e}")
            
            # Create subtitle event with dual-buffer translation fields
            event = SubtitleEvent(
                text=caption.text,
                language="auto",  # LiveCaptions auto-detects language
                confidence=1.0,
                timestamp=caption.timestamp,
                is_partial=not caption.is_final,
                translated_text=translated_text,
                target_language=self._translator.target_language if self._translator else None,
                committed_translation=committed_translation,
                draft_translation=draft_translation
            )
            
            # Send
            self.on_subtitle(event)
            self._last_sent_text = caption.text
            
        except Exception as e:
            error(f"LiveCaptionsPipeline: Error processing caption: {e}")
    
    def start(self):
        """Start the pipeline"""
        if self._running:
            warning("LiveCaptionsPipeline: Already running")
            return
        
        # Check if already running
        if not LiveCaptionsController.is_livecaptions_running():
            # Launch LiveCaptions
            info("LiveCaptionsPipeline: Launching LiveCaptions...")
            if not LiveCaptionsController.launch_livecaptions():
                raise RuntimeError("Failed to launch LiveCaptions")
            
            # Wait for window to appear
            time.sleep(2)
        else:
            info("LiveCaptionsPipeline: LiveCaptions already running")
        
        # Start monitor
        self._monitor.start()
        self._running = True
        
        # Hide window AFTER monitor has found the element
        # Wait a bit for monitor to initialize
        time.sleep(1)
        
        if self.auto_hide_window:
            info("LiveCaptionsPipeline: Minimizing LiveCaptions window...")
            # Instead of moving off-screen, just minimize it
            # This keeps UI Automation working while hiding from user
            if LiveCaptionsController.minimize_livecaptions_window():
                info("LiveCaptionsPipeline: Window minimized successfully")
            else:
                warning("LiveCaptionsPipeline: Failed to minimize window, keeping visible")
        else:
            info("LiveCaptionsPipeline: Keeping LiveCaptions window visible")
        
        info("LiveCaptionsPipeline: Started")
    
    def stop(self):
        """Stop the pipeline"""
        if not self._running:
            return
        
        self._monitor.stop()
        self._running = False
        
        info("LiveCaptionsPipeline: Stopped")
    
    def _default_callback(self, event: SubtitleEvent):
        """Default callback"""
        print(f"[{event.language}] {event.text}")
        if event.translated_text:
            print(f"[Translation] {event.translated_text}")


# Simple test
if __name__ == "__main__":
    print("Testing LiveCaptionsPipeline...")
    print("Please make sure you have audio playing")
    print("Press Ctrl+C to stop")
    
    # Test without translation
    pipeline = LiveCaptionsPipeline(
        enable_translation=False,
        auto_hide_window=False  # Don't hide window for observation
    )
    
    try:
        pipeline.start()
        
        # Run for a while
        print("\nListening for captions...")
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        pipeline.stop()
        print("Done!")
