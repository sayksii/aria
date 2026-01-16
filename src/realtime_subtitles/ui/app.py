"""
Main Application using PyQt6 - Coordinates settings window, overlay, and pipeline.
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
import threading
import sys
import os
from typing import Optional, Union

from .settings_window import SettingsWindow
from .subtitle_overlay import SubtitleOverlay
from .system_tray import SystemTray
from ..pipeline import RealtimePipeline, SubtitleEvent
from ..vosk_pipeline import VoskStreamingPipeline
from ..model_manager import ModelManager, ModelType, ModelStatus
from ..i18n import t
from PyQt6.QtWidgets import QMessageBox


class PipelineSignals(QObject):
    """Signals for thread-safe communication from pipeline to UI."""
    subtitle = pyqtSignal(object)  # SubtitleEvent
    started = pyqtSignal()
    error = pyqtSignal(str)


class App:
    """Main application coordinator.
    
    Manages the settings window, subtitle overlay, system tray, and transcription pipeline.
    """
    
    def __init__(self):
        """Initialize the application."""
        self._settings_window: Optional[SettingsWindow] = None
        self._overlay: Optional[SubtitleOverlay] = None
        self._translation_overlay: Optional[SubtitleOverlay] = None
        self._pipeline: Optional[Union[RealtimePipeline, VoskStreamingPipeline]] = None
        self._tray: Optional[SystemTray] = None
        self._is_running = False
        self._last_settings: Optional[dict] = None
        self._is_streaming_mode = False
        self._enable_translation = False
        
        # For precise mode multi-line display
        self._subtitle_lines: list = []
        self._translation_lines: list = []
        self._max_lines = 3
        
        # Pipeline signals for thread-safe updates
        self._signals = PipelineSignals()
        self._signals.subtitle.connect(self._on_subtitle)
        self._signals.started.connect(self._on_pipeline_started)
        self._signals.error.connect(self._on_error)
    
    def run(self) -> None:
        """Run the application."""
        # Create QApplication
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("ARIA")
        self._app.setFont(QFont("Segoe UI", 9))
        
        # Create settings window
        self._settings_window = SettingsWindow(on_start=self._on_start, on_quit=self._cleanup_and_quit)
        self._settings_window.show()
        
        # Handle window close
        self._settings_window.closeEvent = self._on_window_close
        
        # Create and start system tray
        self._tray = SystemTray(
            on_show=self._on_tray_show,
            on_toggle=self._on_tray_toggle,
            on_quit=self._on_tray_quit
        )
        self._tray.start()
        
        # Start the Qt event loop
        sys.exit(self._app.exec())
    
    def _on_window_close(self, event) -> None:
        """Handle window close - minimize to tray."""
        event.ignore()
        self._settings_window.hide()
        
        if self._tray:
            self._tray.show_notification(
                t("tray_minimized_title"),
                t("tray_minimized_msg")
            )
    
    def _on_tray_show(self) -> None:
        """Handle tray 'show' click."""
        self._settings_window.show()
        self._settings_window.activateWindow()
    
    def _on_tray_toggle(self) -> None:
        """Handle tray 'toggle' click."""
        if self._is_running:
            self._stop()
        else:
            if self._last_settings:
                self._on_start(self._last_settings)
    
    def _on_tray_quit(self) -> None:
        """Handle tray 'quit' click."""
        self._cleanup_and_quit()
    
    def _cleanup_and_quit(self) -> None:
        """Clean up and quit the application."""
        self._stop()
        if self._tray:
            self._tray.stop()
        self._app.quit()
    
    def _on_start(self, settings: dict) -> None:
        """Handle start/stop button click."""
        if settings is None:
            self._stop()
            return
        
        if self._is_running:
            self._stop()
            return
        
        # Save settings for tray toggle
        self._last_settings = settings
        
        # Check mode
        mode = settings.get("mode", "precise")
        self._is_streaming_mode = (mode == "realtime")
        self._enable_translation = settings.get("enable_translation", False)
        
        # Check if all required models are available
        if not self._check_all_required_models(settings):
            return
        
        # Create overlay
        if self._overlay is None:
            self._overlay = SubtitleOverlay(on_close=self._stop)
        
        # Create translation overlay if enabled
        if self._enable_translation and self._translation_overlay is None:
            self._translation_overlay = SubtitleOverlay(
                position_key="translation_overlay",
                on_close=self._stop
            )
            self._translation_overlay.set_translation_mode(True)
        elif not self._enable_translation and self._translation_overlay is not None:
            self._translation_overlay.close()
            self._translation_overlay = None
        
        # Set overlay mode
        if self._is_streaming_mode:
            self._overlay.set_multiline_mode(True)
            if self._translation_overlay:
                self._translation_overlay.set_multiline_mode(True)
        
        # Create pipeline
        def create_pipeline():
            try:
                if self._is_streaming_mode:
                    # Use streaming pipeline
                    lang = settings.get("language") or "zh"  # Default to zh if None
                    self._pipeline = VoskStreamingPipeline(
                        language=lang,
                        on_subtitle=lambda e: self._signals.subtitle.emit(e),
                        enable_translation=self._enable_translation,
                        translation_engine=settings.get("translation_engine", "google"),
                        target_language=settings.get("target_language", "zho_Hant"),
                    )
                else:
                    # Use precise mode (Whisper)
                    self._pipeline = RealtimePipeline(
                        model=settings.get("model", "large-v3"),
                        language=settings.get("language"),
                        use_vad=settings.get("use_vad", True),
                        vad_silence_ms=settings.get("vad_silence_ms", 100),
                        enable_translation=self._enable_translation,
                        translation_engine=settings.get("translation_engine", "google"),
                        target_language=settings.get("target_language", "zho_Hant"),
                        on_subtitle=lambda e: self._signals.subtitle.emit(e),
                    )
                
                self._pipeline.start()
                self._signals.started.emit()
                
            except Exception as e:
                self._signals.error.emit(str(e))
        
        # Start pipeline in background thread
        threading.Thread(target=create_pipeline, daemon=True).start()
        
        # Show loading state
        self._settings_window.status_label.setText(t("status_loading_model"))
        self._settings_window.status_label.setStyleSheet("color: #888888;")
    
    def _on_pipeline_started(self) -> None:
        """Called when pipeline has started."""
        self._is_running = True
        self._settings_window.show_running()
        
        # Show overlay
        self._overlay.show()
        self._overlay.update_subtitle(t("overlay_waiting"), "")
        
        if self._translation_overlay:
            self._translation_overlay.show()
            self._translation_overlay.update_subtitle(t("overlay_translation_waiting"), "")
        
        # Update tray
        if self._tray:
            self._tray.update_status(True)
    
    def _on_subtitle(self, event: SubtitleEvent) -> None:
        """Handle subtitle events from pipeline."""
        if not self._is_running:
            return
        text = event.text
        language = event.language
        translated = event.translated_text
        
        # For precise mode, maintain history of lines
        if not self._is_streaming_mode and text:
            self._subtitle_lines.append(text)
            if len(self._subtitle_lines) > self._max_lines:
                self._subtitle_lines = self._subtitle_lines[-self._max_lines:]
            display_text = "\n".join(self._subtitle_lines)
        else:
            display_text = text
        
        # Update overlay
        if self._overlay:
            self._overlay.update_subtitle(display_text, language)
        
        # Update translation overlay
        if self._translation_overlay and translated:
            if not self._is_streaming_mode:
                self._translation_lines.append(translated)
                if len(self._translation_lines) > self._max_lines:
                    self._translation_lines = self._translation_lines[-self._max_lines:]
                display_translated = "\n".join(self._translation_lines)
            else:
                display_translated = translated
            
            self._translation_overlay.update_subtitle(display_translated, "")
    
    def _on_error(self, error: str) -> None:
        """Handle pipeline error."""
        self._is_running = False
        self._settings_window.show_stopped()
        self._settings_window.status_label.setText(f"Error: {error}")
        self._settings_window.status_label.setStyleSheet("color: red;")
        
        if self._tray:
            self._tray.update_status(False)
    
    def _stop(self) -> None:
        """Stop the pipeline and overlay."""
        self._is_running = False

        if self._pipeline:
            self._pipeline.stop()
            self._pipeline = None
        
        if self._overlay:
            self._overlay.hide()
        
        if self._translation_overlay:
            self._translation_overlay.hide()
        
        self._subtitle_lines = []
        self._translation_lines = []
        
        self._settings_window.show_stopped()
        
        if self._tray:
            self._tray.update_status(False)
    
    def _check_all_required_models(self, settings: dict) -> bool:
        """Check if all required models are available and prompt to download if not."""
        missing_models = []
        manager = ModelManager()
        mode = settings.get("mode", "precise")
        
        # Check Whisper model (only for precise mode)
        if mode == "precise":
            model_id = settings.get("model", "large-v3")
            for m in manager.get_all_models():
                if m.model_type == ModelType.WHISPER and model_id in m.id:
                    status = manager.get_status(m)
                    if status != ModelStatus.DOWNLOADED:
                        missing_models.append(m)
                    break
        else:
            # Check realtime model (Sherpa for zh/en, Vosk for ja)
            lang = settings.get("language") or "zh"
            required_type = ModelType.VOSK if lang == "ja" else ModelType.SHERPA
            for m in manager.get_all_models():
                if m.model_type == required_type:
                    status = manager.get_status(m)
                    if status != ModelStatus.DOWNLOADED:
                        missing_models.append(m)
                    break
        
        # Check NLLB model (if translation enabled with NLLB engine)
        if settings.get("enable_translation", False) and settings.get("translation_engine", "google") == "nllb":
            for m in manager.get_all_models():
                if m.model_type == ModelType.NLLB:
                    status = manager.get_status(m)
                    if status != ModelStatus.DOWNLOADED:
                        missing_models.append(m)
                    break
        
        if not missing_models:
            return True
        
        # Build model names list (translate names)
        model_names = "\n".join([t(m.name) for m in missing_models])
        
        # Show download dialog
        from .model_manager_window import show_download_dialog
        
        result = QMessageBox.question(
            self._settings_window,
            t("model_not_downloaded_title"),
            t("model_not_downloaded_msg").format(models=model_names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            show_download_dialog(
                self._settings_window,
                missing_models,
                on_complete=lambda: self._on_start(settings)
            )
        
        return False


def run_app():
    """Entry point for the GUI application."""
    # Set environment
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    # Run app
    app = App()
    app.run()


if __name__ == "__main__":
    run_app()
