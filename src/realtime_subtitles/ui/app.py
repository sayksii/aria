"""
Main Application - Coordinates settings window, overlay, and pipeline.
"""

import customtkinter as ctk
import threading
import sys
from typing import Optional, Union

from .settings_window import SettingsWindow
from .subtitle_overlay import SubtitleOverlay
from .system_tray import SystemTray
from .model_manager_window import show_model_manager, show_download_dialog
from ..pipeline import RealtimePipeline, SubtitleEvent
from ..vosk_pipeline import VoskStreamingPipeline
from ..model_manager import ModelManager, ModelType, ModelStatus
from ..i18n import t
from tkinter import messagebox


class App:
    """
    Main application coordinator.
    
    Manages the settings window, subtitle overlay, system tray, and transcription pipeline.
    """
    
    def __init__(self):
        """Initialize the application."""
        self._pipeline: Optional[Union[RealtimePipeline, VoskStreamingPipeline]] = None
        self._overlay: Optional[SubtitleOverlay] = None
        self._translation_overlay: Optional[SubtitleOverlay] = None  # Separate translation overlay
        self._settings_window: Optional[SettingsWindow] = None
        self._tray: Optional[SystemTray] = None
        self._is_running = False
        self._last_settings: Optional[dict] = None
        self._is_streaming_mode = False
        self._enable_translation = False
    
    def run(self) -> None:
        """Run the application."""
        # Create settings window
        self._settings_window = SettingsWindow(on_start=self._on_start)
        
        # Create and start system tray
        self._tray = SystemTray(
            on_show=self._on_tray_show,
            on_toggle=self._on_tray_toggle,
            on_quit=self._on_tray_quit,
        )
        self._tray.start()
        
        # Handle window close - minimize to tray instead of quit
        self._settings_window.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Run main loop
        self._settings_window.mainloop()
        
        # Cleanup
        if self._tray:
            self._tray.stop()
    
    def _on_window_close(self) -> None:
        """Handle window close - always minimize to tray."""
        # Hide window and show in tray
        self._settings_window.withdraw()  # Hide completely instead of iconify
        
        # Show notification
        if self._tray:
            self._tray.show_notification(
                t("tray_minimized_title"),
                t("tray_minimized_msg")
            )
    
    def _on_tray_show(self) -> None:
        """Handle tray 'show' click."""
        self._settings_window.after(0, self._settings_window.deiconify)
        self._settings_window.after(0, self._settings_window.lift)
    
    def _on_tray_toggle(self) -> None:
        """Handle tray 'toggle' click."""
        def toggle():
            if self._is_running:
                self._stop()
            elif self._last_settings:
                self._on_start(self._last_settings)
            else:
                # No saved settings - show settings window
                self._settings_window.deiconify()
                self._settings_window.lift()
        
        self._settings_window.after(0, toggle)
    
    def _on_tray_quit(self) -> None:
        """Handle tray 'quit' click."""
        self._settings_window.after(0, self._cleanup_and_quit)
    
    def _cleanup_and_quit(self) -> None:
        """Clean up and quit the application."""
        self._stop()
        if self._tray:
            self._tray.stop()
        self._settings_window.destroy()
    
    def _on_start(self, settings: dict) -> None:
        """
        Handle start/stop button click.
        
        Args:
            settings: Dictionary with model, language, use_vad, mode, etc.
                     None signals stop request.
        """
        # None means stop request
        if settings is None:
            self._stop()
            return
        
        if self._is_running:
            self._stop()
            return
        
        # Save settings for tray toggle
        self._last_settings = settings
        
        # Check if streaming mode
        mode = settings.get("mode", "precise")
        self._is_streaming_mode = (mode == "realtime")
        self._enable_translation = settings.get("enable_translation", False)
        
        # Check if required model is available
        if not self._check_model_available(settings):
            self._settings_window.show_stopped()  # Reset button state
            return  # User declined download or model not available
        
        # Create overlay (with multiline support for streaming mode)
        if self._overlay is None:
            self._overlay = SubtitleOverlay(self._settings_window)
        
        # Create separate translation overlay if enabled
        if self._enable_translation and self._translation_overlay is None:
            self._translation_overlay = SubtitleOverlay(self._settings_window)
            self._translation_overlay.set_translation_mode(True)  # Green text, positioned above
        elif not self._enable_translation and self._translation_overlay is not None:
            # Translation disabled - destroy existing overlay
            try:
                self._translation_overlay.destroy()
            except Exception:
                pass
            self._translation_overlay = None
        
        # Set overlay height based on mode
        if self._is_streaming_mode:
            self._overlay.set_multiline_mode(True)
            if self._translation_overlay:
                self._translation_overlay.set_multiline_mode(True)
        else:
            self._overlay.set_multiline_mode(False)
            if self._translation_overlay:
                self._translation_overlay.set_multiline_mode(False)
        
        # Create appropriate pipeline
        if self._is_streaming_mode:
            # Map Whisper language codes to Vosk language codes
            lang = settings.get("language", "zh")
            vosk_lang_map = {
                "zh": "zh",      # Chinese
                "ja": "ja",      # Japanese  
                "en": "en",      # English
            }
            vosk_lang = vosk_lang_map.get(lang, "zh")  # Default to Chinese
            
            # Use Vosk/Sherpa for true streaming (no repetition)
            self._pipeline = VoskStreamingPipeline(
                language=vosk_lang,
                on_subtitle=self._on_subtitle,
                max_lines=5,
                enable_translation=settings.get("enable_translation", False),
                translation_engine=settings.get("translation_engine", "google"),
                target_language=settings.get("target_language", "zh"),
            )
        else:
            self._pipeline = RealtimePipeline(
                model=settings["model"],
                language=settings["language"],
                on_subtitle=self._on_subtitle,
                use_vad=settings["use_vad"],
                vad_silence_ms=settings.get("vad_silence_ms", 300),
                min_segment_duration=settings["min_duration"],
                max_segment_duration=settings["max_duration"],
                enable_translation=settings.get("enable_translation", False),
                translation_engine=settings.get("translation_engine", "google"),
                target_language=settings.get("target_language", "zh"),
            )
        
        # Start pipeline in background
        def start_pipeline():
            try:
                self._pipeline.start()
                self._is_running = True
                
                # Update UI in main thread
                self._settings_window.after(0, self._on_pipeline_started)
            except Exception as e:
                print(f"[App] Pipeline error: {e}")
                self._settings_window.after(0, lambda: self._on_error(str(e)))
        
        threading.Thread(target=start_pipeline, daemon=True).start()
    
    def _on_pipeline_started(self) -> None:
        """Called when pipeline has started."""
        self._settings_window.show_running()
        self._overlay.show()
        self._overlay.update_subtitle(t("overlay_waiting"), "")
        
        # Show translation overlay if enabled
        if self._translation_overlay:
            self._translation_overlay.show()
            self._translation_overlay.update_subtitle(t("overlay_translation_waiting"), "")
        
        # Update tray status
        if self._tray:
            self._tray.update_status(True)
        
        # Minimize settings window
        self._settings_window.iconify()
    
    def _on_subtitle(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle events from pipeline.
        
        Args:
            event: SubtitleEvent with text, language, translated_text, etc.
        """
        # Capture values to avoid lambda closure issues
        text = event.text
        language = event.language
        translated = event.translated_text
        
        # Update original overlay in main thread
        if self._overlay:
            self._settings_window.after(
                0,
                lambda t=text, l=language: self._overlay.update_subtitle(t, l)
            )
        
        # Update translation overlay if enabled and has translation
        if self._translation_overlay and translated:
            self._settings_window.after(
                0,
                lambda tr=translated: self._translation_overlay.update_subtitle(tr, "")
            )
    
    def _on_error(self, error: str) -> None:
        """Handle pipeline error."""
        self._settings_window.show_stopped()
        self._settings_window.status_label.configure(
            text=f"Error: {error}",
            text_color="red"
        )
        self._is_running = False
        
        # Update tray status
        if self._tray:
            self._tray.update_status(False)
    
    def _stop(self) -> None:
        """Stop the pipeline and overlay."""
        if self._pipeline:
            self._pipeline.stop()
            self._pipeline = None
        
        # Hide or destroy overlays
        if self._overlay:
            try:
                self._overlay.hide()
            except Exception:
                try:
                    self._overlay.destroy()
                except Exception:
                    pass
                self._overlay = None
        
        if self._translation_overlay:
            try:
                self._translation_overlay.hide()
            except Exception:
                try:
                    self._translation_overlay.destroy()
                except Exception:
                    pass
                self._translation_overlay = None
        
        self._settings_window.show_stopped()
        self._settings_window.deiconify()
        self._is_running = False
        
        # Update tray status
        if self._tray:
            self._tray.update_status(False)
    
    def _check_model_available(self, settings: dict) -> bool:
        """
        Check if required model is available locally.
        
        Returns:
            True if model is available,
            False if model is not available.
        """
        mode = settings.get("mode", "precise")
        model_name = settings.get("model", "large-v3")
        language = settings.get("language")
        enable_translation = settings.get("enable_translation", False)
        translation_engine = settings.get("translation_engine", "google")
        
        manager = ModelManager()
        missing_models = []
        
        if mode == "precise":
            # Whisper models
            model_id_map = {
                "large-v3": "whisper-large-v3",
                "large-v3-turbo": "whisper-large-v3-turbo",
                "medium": "whisper-medium",
            }
            model_id = model_id_map.get(model_name)
            if model_id:
                for m in manager.get_all_models():
                    if m.id == model_id:
                        if manager.get_status(m) != ModelStatus.DOWNLOADED:
                            missing_models.append(m)
                        break
        else:
            # Streaming mode - check Sherpa or Vosk based on language
            if language == "ja":
                model_id = "vosk-model-ja"
            else:
                model_id = "sherpa-onnx-streaming-paraformer-zh"
            
            for m in manager.get_all_models():
                if m.id == model_id:
                    if manager.get_status(m) != ModelStatus.DOWNLOADED:
                        missing_models.append(m)
                    break
        
        # Check NLLB translation model if translation is enabled
        if enable_translation and translation_engine == "nllb":
            for m in manager.get_all_models():
                if m.id == "nllb-200-distilled-600M":
                    if manager.get_status(m) != ModelStatus.DOWNLOADED:
                        missing_models.append(m)
                    break
        
        if not missing_models:
            return True  # All models are available
        
        # Build message for missing models (translate model names)
        model_list = "\n".join([f"  • {t(m.name)} ({m.get_size_display()})" for m in missing_models])
        result = messagebox.askyesno(
            t("model_not_downloaded_title"),
            t("model_not_downloaded_msg").format(models=model_list),
        )
        
        if result:
            # User chose to download - show download dialog
            show_download_dialog(self._settings_window, missing_models)
        
        return False  # Don't start subtitles yet


def run_app() -> None:
    """Entry point for the GUI application."""
    import os
    import tempfile
    from pathlib import Path
    
    # Single instance check using lock file
    lock_file_path = Path(tempfile.gettempdir()) / "aria_subtitles.lock"
    
    try:
        # Try to create/open the lock file exclusively
        if sys.platform == 'win32':
            import msvcrt
            lock_file = open(lock_file_path, 'w')
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except (IOError, OSError):
                # Another instance is running
                from tkinter import messagebox
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                messagebox.showwarning(
                    "ARIA",
                    t("already_running")
                )
                root.destroy()
                sys.exit(0)
        else:
            import fcntl
            lock_file = open(lock_file_path, 'w')
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                print("ARIA is already running.")
                sys.exit(0)
        
        # Write PID to lock file
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        
        # Run the app
        app = App()
        app.run()
        
    finally:
        # Clean up lock file on exit
        try:
            if 'lock_file' in locals():
                lock_file.close()
            if lock_file_path.exists():
                lock_file_path.unlink()
        except:
            pass


if __name__ == "__main__":
    run_app()

