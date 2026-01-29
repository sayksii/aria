"""
Main Settings Window for ARIA using PyQt6.

A modern, beautiful settings interface.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QFrame, QCheckBox, QSlider,
    QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon
from typing import Callable, Optional
import os
import sys

from ..settings_manager import get_settings_manager
from .model_manager_window import show_model_manager
from ..i18n import t, get_current_language, set_language, LANGUAGES


class SettingsWindow(QMainWindow):
    """Main settings window with model selection, language, VAD options, etc."""
    
    # Model options
    MODEL_IDS = ["large-v3", "large-v3-turbo", "medium"]
    LANGUAGE_CODES = [None, "zh", "en", "ja", "ko", "yue", "es", "fr", "de"]
    
    # Signal for thread-safe updates
    status_update = pyqtSignal(str, str)  # text, color
    
    @staticmethod
    def _get_whisper_models():
        """Get Whisper models list with translated display names."""
        return [
            (t("model_large_v3"), "large-v3"),
            (t("model_large_v3_turbo"), "large-v3-turbo"),
            (t("model_medium"), "medium"),
        ]
    
    @staticmethod
    def _get_realtime_languages():
        """Get available languages for realtime mode."""
        return [
            ("中/英文", "zh"),   # Uses Sherpa
            ("日文", "ja"),      # Uses Vosk
        ]
    
    @staticmethod
    def _get_streaming_model_for_language(lang_code: str) -> str:
        """Get the streaming model ID for a language."""
        if lang_code in ["zh", "en"]:
            return "sherpa-zh-en"
        elif lang_code == "ja":
            return "vosk-ja"
        return "sherpa-zh-en"  # Default
    
    @staticmethod
    def _get_languages():
        """Get languages list with translated display names."""
        return [
            (t("auto_detect"), None),
            (t("lang_chinese"), "zh"),
            (t("lang_english"), "en"),
            (t("lang_japanese"), "ja"),
            (t("lang_korean"), "ko"),
            (t("lang_cantonese"), "yue"),
            (t("lang_spanish"), "es"),
            (t("lang_french"), "fr"),
            (t("lang_german"), "de"),
            (t("lang_russian"), "ru"),
        ]
    
    @property
    def WHISPER_MODELS(self):
        return self._get_whisper_models()
    
    @property
    def REALTIME_LANGUAGES(self):
        return self._get_realtime_languages()
    
    @property
    def LANGUAGES(self):
        return self._get_languages()
    
    def __init__(self, on_start: Callable[[dict], None], on_quit: Optional[Callable[[], None]] = None):
        """Initialize the settings window.
        
        Args:
            on_start: Callback when user clicks Start. Called with settings dict.
            on_quit: Callback when user clicks Quit.
        """
        super().__init__()
        
        self.on_start = on_start
        self.on_quit = on_quit
        self._is_running = False
        self._loading = True
        
        # Window setup
        self.setWindowTitle("ARIA")
        self.setFixedSize(820, 620)  # Slightly wider to accommodate better spacing
        self.setStyleSheet(self._get_stylesheet())
        
        # Center on screen
        self._center_on_screen()
        
        # Create UI
        self._create_ui()
        
        # Load saved settings
        self._load_saved_settings()
        self._loading = False
        
        # Connect status signal
        self.status_update.connect(self._update_status_label)
    
    def _center_on_screen(self):
        """Center window on screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)
    
    def _get_stylesheet(self):
        """Return the main stylesheet."""
        return """
            QMainWindow {
                background-color: #1a1a1a;
            }
            QLabel {
                color: white;
            }
            QFrame#card {
                background-color: #2a2a2a;
                border-radius: 12px;
            }
            QFrame#title_label {
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #3B8ED0;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4AA3E0;
            }
            QPushButton:pressed {
                background-color: #2A7DC0;
            }
            QPushButton#secondary {
                background-color: transparent;
                border: 1px solid #555555;
                color: #aaaaaa;
            }
            QPushButton#secondary:hover {
                background-color: #333333;
            }
            QComboBox {
                background-color: #333333;
                color: white;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 180px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #333333;
                color: white;
                selection-background-color: #3B8ED0;
            }
            QCheckBox {
                color: white;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 1px solid #555555;
                background-color: #333333;
            }
            QCheckBox::indicator:hover {
                border-color: #3B8ED0;
                background-color: #444444;
            }
            QCheckBox::indicator:checked {
                background-color: #3B8ED0;
                border-color: #3B8ED0;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #4AA3E0;
                border-color: #4AA3E0;
            }
            QComboBox:hover {
                border-color: #3B8ED0;
            }
        """
    
    def _create_ui(self):
        """Create all UI components."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # === Header ===
        header = self._create_header()
        main_layout.addWidget(header)
        
        # === Two-column layout ===
        columns = QHBoxLayout()
        columns.setSpacing(15)
        
        # Left column
        left_col = QVBoxLayout()
        left_col.setSpacing(15)
        left_col.addWidget(self._create_recognition_card())
        left_col.addWidget(self._create_model_card())
        columns.addLayout(left_col, 1)  # Equal weight
        
        # Right column
        right_col = QVBoxLayout()
        right_col.setSpacing(15)
        right_col.addWidget(self._create_translation_card())
        right_col.addWidget(self._create_vad_card())
        right_col.addWidget(self._create_reset_card())
        columns.addLayout(right_col, 1)  # Equal weight
        
        main_layout.addLayout(columns)
        
        # Push button to bottom
        main_layout.addStretch()
        
        # === Start Button ===
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        self.start_button = QPushButton("🎙 " + t("start"))
        self.start_button.setMinimumHeight(45)
        self.start_button.setMinimumWidth(150)
        self.start_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
            }
        """)
        self.start_button.clicked.connect(self._on_start_click)
        button_row.addWidget(self.start_button)
        
        button_row.addStretch()
        main_layout.addLayout(button_row)
        
        # === Status Label (close to button) ===
        self.status_label = QLabel(t("status_ready"))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; margin-top: 5px;")
        main_layout.addWidget(self.status_label)
        

    
    def _create_header(self):
        """Create header with title and language selector."""
        header = QFrame()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Left spacer (same width as language selector for balance)
        left_spacer = QWidget()
        left_spacer.setFixedWidth(210)
        layout.addWidget(left_spacer)
        
        # Spacer
        layout.addStretch()
        
        # Title (centered)
        title_container = QVBoxLayout()
        
        title = QLabel("ARIA")
        title.setFont(QFont("", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_container.addWidget(title)
        
        subtitle = QLabel(t("subtitle") + " | v2.0.0")
        subtitle.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_container.addWidget(subtitle)
        
        layout.addLayout(title_container)
        
        # Spacer
        layout.addStretch()
        
        # Language selector (right side)
        self.lang_selector = QComboBox()
        lang_options = [LANGUAGES[code][0] for code in LANGUAGES]
        self.lang_selector.addItems(lang_options)
        current_lang = get_current_language()
        current_lang_name = LANGUAGES.get(current_lang, LANGUAGES["zh_TW"])[0]
        self.lang_selector.setCurrentText(current_lang_name)
        self.lang_selector.currentTextChanged.connect(self._on_ui_language_change)
        self.lang_selector.setFixedWidth(120)
        layout.addWidget(self.lang_selector)
        
        return header
    
    def _create_card(self, title: str) -> tuple:
        """Create a card frame with title. Returns (frame, content_layout)."""
        frame = QFrame()
        frame.setObjectName("card")
        frame.setMaximumWidth(400)  # Limit maximum width to prevent imbalance
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(12)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        return frame, layout
    
    def _create_recognition_card(self):
        """Create recognition settings card."""
        card, layout = self._create_card(t("recognition_settings"))
        
        # Mode selector (Precise / Realtime)
        mode_layout = QHBoxLayout()
        mode_layout.addStretch()
        
        self.mode_precise_btn = QPushButton(t("mode_precise"))
        self.mode_precise_btn.setCheckable(True)
        self.mode_precise_btn.setChecked(True)
        self.mode_precise_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555555;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #333333;
                border-color: #3B8ED0;
            }
            QPushButton:checked {
                background-color: #3B8ED0;
                border: none;
                color: white;
            }
            QPushButton:checked:hover {
                background-color: #4AA3E0;
            }
        """)
        self.mode_precise_btn.clicked.connect(lambda: self._on_mode_change("precise"))
        mode_layout.addWidget(self.mode_precise_btn)
        
        self.mode_realtime_btn = QPushButton(t("mode_realtime"))
        self.mode_realtime_btn.setCheckable(True)
        self.mode_realtime_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555555;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #333333;
                border-color: #3B8ED0;
            }
            QPushButton:checked {
                background-color: #3B8ED0;
                border: none;
                color: white;
            }
            QPushButton:checked:hover {
                background-color: #4AA3E0;
            }
        """)
        self.mode_realtime_btn.clicked.connect(lambda: self._on_mode_change("realtime"))
        mode_layout.addWidget(self.mode_realtime_btn)
        
        self.mode_livecaptions_btn = QPushButton(t("mode_livecaptions"))
        self.mode_livecaptions_btn.setCheckable(True)
        self.mode_livecaptions_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555555;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #333333;
                border-color: #3B8ED0;
            }
            QPushButton:checked {
                background-color: #3B8ED0;
                border: none;
                color: white;
            }
            QPushButton:checked:hover {
                background-color: #4AA3E0;
            }
        """)
        self.mode_livecaptions_btn.clicked.connect(lambda: self._on_mode_change("livecaptions"))
        mode_layout.addWidget(self.mode_livecaptions_btn)
        
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Mode description
        self.mode_desc = QLabel(t("mode_precise_desc"))
        self.mode_desc.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self.mode_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mode_desc)
        
        return card
    
    def _create_model_card(self):
        """Create model settings card."""
        card, layout = self._create_card(t("model_settings"))
        
        # Store reference for enabling/disabling
        self.model_card = card
        
        # Model dropdown
        model_row = QHBoxLayout()
        self.model_label = QLabel(t("model") + ":")
        model_row.addWidget(self.model_label)
        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems([m[0] for m in self.WHISPER_MODELS])
        self.model_dropdown.currentTextChanged.connect(self._on_model_change)
        model_row.addWidget(self.model_dropdown)
        model_row.addStretch()
        layout.addLayout(model_row)
        
        # Language dropdown
        lang_row = QHBoxLayout()
        self.lang_label = QLabel(t("lang") + ":")
        lang_row.addWidget(self.lang_label)
        self.lang_dropdown = QComboBox()
        self.lang_dropdown.addItems([l[0] for l in self.LANGUAGES])
        self.lang_dropdown.currentTextChanged.connect(lambda _: self._persist_ui_settings())
        lang_row.addWidget(self.lang_dropdown)
        lang_row.addStretch()
        layout.addLayout(lang_row)
        
        # Manage models button
        self.manage_models_btn = QPushButton("📦 " + t("manage_models"))
        self.manage_models_btn.setObjectName("secondary")
        self.manage_models_btn.setMaximumWidth(160)
        self.manage_models_btn.clicked.connect(self._on_manage_models)
        layout.addWidget(self.manage_models_btn)
        
        return card
    
    def _create_translation_card(self):
        """Create translation settings card."""
        card, layout = self._create_card(t("translation_settings"))
        
        # Translation switch
        trans_row = QHBoxLayout()
        trans_row.addWidget(QLabel(t("translation") + ":"))
        self.trans_checkbox = QCheckBox()
        self.trans_checkbox.stateChanged.connect(self._on_translation_change)
        trans_row.addWidget(self.trans_checkbox)
        self.trans_status = QLabel("OFF")
        self.trans_status.setStyleSheet("color: #888888;")
        trans_row.addWidget(self.trans_status)
        trans_row.addStretch()
        layout.addLayout(trans_row)
        
        # Engine dropdown
        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel(t("engine") + ":"))
        self.trans_engine_dropdown = QComboBox()
        self.trans_engine_dropdown.addItems([
            t("engine_nllb"),
            t("engine_google_free"),
            t("engine_bing"),
            t("engine_youdao"),
        ])
        self.trans_engine_dropdown.currentTextChanged.connect(lambda _: self._persist_ui_settings())
        engine_row.addWidget(self.trans_engine_dropdown)
        engine_row.addStretch()
        layout.addLayout(engine_row)
        
        # Target language dropdown
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel(t("target_lang") + ":"))
        self.target_lang_dropdown = QComboBox()
        self.target_lang_dropdown.addItems([
            t("target_zh_TW"), t("target_zh_CN"), t("target_en"),
            t("target_ja"), t("target_ko"), t("target_es"),
            t("target_fr"), t("target_de")
        ])
        self.target_lang_dropdown.currentTextChanged.connect(lambda _: self._persist_ui_settings())
        target_row.addWidget(self.target_lang_dropdown)
        target_row.addStretch()
        layout.addLayout(target_row)
        
        return card
    
    def _create_vad_card(self):
        """Create VAD settings card."""
        card, layout = self._create_card(t("vad_settings"))
        
        # Store reference for enabling/disabling
        self.vad_card = card
        
        # VAD switch
        vad_row = QHBoxLayout()
        self.vad_label = QLabel(t("vad_label") + ":")
        vad_row.addWidget(self.vad_label)
        self.vad_checkbox = QCheckBox()
        self.vad_checkbox.setChecked(True)
        self.vad_checkbox.stateChanged.connect(self._on_vad_change)
        vad_row.addWidget(self.vad_checkbox)
        self.vad_status = QLabel("ON")
        self.vad_status.setStyleSheet("color: #3B8ED0;")
        vad_row.addWidget(self.vad_status)
        vad_row.addStretch()
        layout.addLayout(vad_row)
        
        # VAD description
        self.vad_desc = QLabel(t("vad_desc_precise"))
        self.vad_desc.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self.vad_desc.setWordWrap(True)
        layout.addWidget(self.vad_desc)
        
        return card
    
    def _create_reset_card(self):
        """Create reset settings card."""
        card = QFrame()
        card.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        
        self.reset_button = QPushButton("🔄 " + t("reset_settings"))
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555555;
                color: #aaaaaa;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #333333;
                border-color: #3B8ED0;
            }
        """)
        self.reset_button.clicked.connect(self._on_reset_settings)
        button_row.addWidget(self.reset_button)
        
        self.quit_button = QPushButton("⏻ " + t("quit_app"))
        self.quit_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555555;
                color: #aaaaaa;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #333333;
                border-color: #E04040;
            }
        """)
        self.quit_button.clicked.connect(self._on_quit_app)
        button_row.addWidget(self.quit_button)
        
        layout.addLayout(button_row)
        
        reset_desc = QLabel(t("reset_settings_desc"))
        reset_desc.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        reset_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(reset_desc)
        
        return card
    
    # === Event Handlers ===
    
    def _on_mode_change(self, mode: str):
        """Handle mode button click."""
        if mode == "precise":
            self.mode_precise_btn.setChecked(True)
            self.mode_realtime_btn.setChecked(False)
            self.mode_livecaptions_btn.setChecked(False)
            self.mode_desc.setText(t("mode_precise_desc"))
            # Swap to Whisper models
            self.model_label.setText(t("model") + ":")  # Restore label to "模型:"
            self.model_label.show()  # Ensure label is visible
            self.model_dropdown.clear()
            self.model_dropdown.addItems([m[0] for m in self.WHISPER_MODELS])
            self.model_dropdown.setEnabled(True)
            self.model_dropdown.show()  # Ensure dropdown is visible
            # Show and restore full language list
            self.lang_label.show()
            self.lang_dropdown.show()
            self.lang_dropdown.clear()
            self.lang_dropdown.addItems([l[0] for l in self.LANGUAGES])
            self.lang_dropdown.setEnabled(True)
            self.manage_models_btn.show()
            self.vad_checkbox.setEnabled(True)
            self.vad_desc.setText(t("vad_desc_precise"))
            # Normal styling for VAD card
            self.vad_label.setStyleSheet("color: white;")
            self.vad_status.setStyleSheet("color: #3B8ED0;")
            self.vad_checkbox.setStyleSheet("")  # Reset to default
            self.vad_card.setStyleSheet("")
            # Normal styling for Model card
            self.model_label.setStyleSheet("color: white;")
            self.lang_label.setStyleSheet("color: white;")
            self.model_card.setEnabled(True)
            self.model_card.setStyleSheet("")
        elif mode == "realtime":
            self.mode_precise_btn.setChecked(False)
            self.mode_realtime_btn.setChecked(True)
            self.mode_livecaptions_btn.setChecked(False)
            self.mode_desc.setText(t("mode_realtime_desc"))
            # Swap to realtime language selection (shows in model dropdown position)
            self.model_label.setText(t("lang") + ":")  # Change label to "语言:"
            self.model_label.show()  # Ensure label is visible
            self.model_dropdown.clear()
            self.model_dropdown.addItems([lang[0] for lang in self.REALTIME_LANGUAGES])
            self.model_dropdown.setEnabled(True)
            self.model_dropdown.show()  # Ensure dropdown is visible
            # Hide language dropdown in realtime mode (selection is in model dropdown)
            self.lang_label.hide()
            self.lang_dropdown.hide()
            self.manage_models_btn.show()
            self.vad_checkbox.setEnabled(False)
            self.vad_desc.setText(t("vad_desc_realtime"))
            # Dimmed styling for VAD card
            self.vad_label.setStyleSheet("color: #555555;")
            self.vad_status.setStyleSheet("color: #555555;")
            self.vad_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    background-color: #444444;
                    border: 1px solid #555555;
                }
            """)
            self.vad_card.setStyleSheet("#card { background-color: rgba(42, 42, 42, 0.5); }")
            # Normal styling for Model card
            self.model_label.setStyleSheet("color: white;")
            self.model_card.setEnabled(True)
            self.model_card.setStyleSheet("")
        else:  # livecaptions mode
            self.mode_precise_btn.setChecked(False)
            self.mode_realtime_btn.setChecked(False)
            self.mode_livecaptions_btn.setChecked(True)
            self.mode_desc.setText(t("mode_livecaptions_desc"))
            # Disable model selection (uses Windows LiveCaptions)
            self.model_label.hide()
            self.model_dropdown.hide()
            self.lang_label.hide()
            self.lang_dropdown.hide()
            self.manage_models_btn.hide()
            self.vad_checkbox.setEnabled(False)
            self.vad_desc.setText(t("vad_desc_realtime"))
            # Dimmed styling for both VAD and Model cards
            self.vad_label.setStyleSheet("color: #555555;")
            self.vad_status.setStyleSheet("color: #555555;")
            self.vad_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    background-color: #444444;
                    border: 1px solid #555555;
                }
            """)
            self.vad_card.setStyleSheet("#card { background-color: rgba(42, 42, 42, 0.5); }")
            self.model_label.setStyleSheet("color: #555555;")
            self.model_card.setEnabled(False)
            self.model_card.setStyleSheet("#card { background-color: rgba(42, 42, 42, 0.5); }")
        self._persist_ui_settings()
    
    def _on_model_change(self, model_text: str):
        """Handle model dropdown change."""
        self._persist_ui_settings()
    
    def _on_translation_change(self, state):
        """Handle translation checkbox change."""
        if state:
            self.trans_status.setText("ON")
            self.trans_status.setStyleSheet("color: #3B8ED0;")
        else:
            self.trans_status.setText("OFF")
            self.trans_status.setStyleSheet("color: #888888;")
        self._persist_ui_settings()
    
    def _on_vad_change(self, state):
        """Handle VAD checkbox change."""
        if state:
            self.vad_status.setText("ON")
            self.vad_status.setStyleSheet("color: #3B8ED0;")
        else:
            self.vad_status.setText("OFF")
            self.vad_status.setStyleSheet("color: #888888;")
        self._persist_ui_settings()
    
    def _on_manage_models(self):
        """Open model manager window."""
        show_model_manager(self)
    
    def _on_reset_settings(self):
        """Reset all settings."""
        result = QMessageBox.question(
            self,
            t("reset_settings"),
            t("reset_settings_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            # Delete settings file
            settings = get_settings_manager()
            settings_path = settings._config_file
            if settings_path.exists():
                settings_path.unlink()
            
            # Restart app
            import subprocess
            subprocess.Popen([sys.executable, "-m", "realtime_subtitles.ui.app"])
            QApplication.quit()

    def _on_quit_app(self):
        """Quit the application."""
        if self.on_quit:
            self.on_quit()
        else:
            QApplication.quit()
    
    def _on_ui_language_change(self, lang_display: str):
        """Handle UI language change."""
        # Find language code from display name
        lang_code = None
        for code, (name, _) in LANGUAGES.items():
            if name == lang_display:
                lang_code = code
                break
        
        if lang_code and lang_code != get_current_language():
            set_language(lang_code)
            QMessageBox.information(
                self,
                t("restart_required"),
                t("restart_required")
            )
    
    def _on_start_click(self):
        """Handle start/stop button click."""
        if self._is_running:
            # Stop
            self.on_start(None)
        else:
            # Start - gather settings
            settings = self._gather_settings()
            self.on_start(settings)

    def _persist_ui_settings(self) -> None:
        """Persist current UI selections without starting."""
        if self._loading:
            return
        self._gather_settings()
    
    def _gather_settings(self) -> dict:
        """Gather current settings into a dictionary."""
        # Determine mode
        if self.mode_precise_btn.isChecked():
            mode = "precise"
        elif self.mode_livecaptions_btn.isChecked():
            mode = "livecaptions"
        else:
            mode = "realtime"
        
        # Get model value
        model_display = self.model_dropdown.currentText()
        
        if mode == "precise":
            # Precise mode: model dropdown shows Whisper models
            model_id = "large-v3"
            for display, mid in self.WHISPER_MODELS:
                if display == model_display:
                    model_id = mid
                    break
            # Get language from lang dropdown
            lang_display = self.lang_dropdown.currentText()
            lang_code = None
            for display, lcode in self.LANGUAGES:
                if display == lang_display:
                    lang_code = lcode
                    break
        elif mode == "livecaptions":
            # LiveCaptions mode: no model/language selection needed
            model_id = None
            lang_code = None
        else:
            # Realtime mode: model dropdown shows languages, model is auto-selected
            lang_code = "zh"  # Default
            for display, lcode in self.REALTIME_LANGUAGES:
                if display == model_display:
                    lang_code = lcode
                    break
            # Get model from language
            model_id = self._get_streaming_model_for_language(lang_code)
        
        # Get target language code
        target_lang = self._get_target_language_code()
        
        # Get translation engine - map display name to engine ID
        engine_display = self.trans_engine_dropdown.currentText()
        engine_map = {
            t("engine_nllb"): "nllb",
            t("engine_google_free"): "google_free",
            t("engine_bing"): "bing",
            t("engine_youdao"): "youdao",
        }
        engine = engine_map.get(engine_display, "nllb")  # Default to NLLB
        
        settings = {
            "mode": mode,
            "model": model_id,
            "language": lang_code,
            "use_vad": self.vad_checkbox.isChecked(),
            "vad_silence_ms": 100 if mode == "precise" else 500,
            "enable_translation": self.trans_checkbox.isChecked(),
            "translation_engine": engine,
            "target_language": target_lang,
        }
        
        # Save settings
        self._save_settings(settings)
        
        return settings
    
    def _get_target_language_code(self) -> str:
        """Get target language code from dropdown."""
        target_display = self.target_lang_dropdown.currentText()
        
        # Map display names to NLLB codes
        target_map = {
            t("target_zh_TW"): "zho_Hant",
            t("target_zh_CN"): "zho_Hans",
            t("target_en"): "eng_Latn",
            t("target_ja"): "jpn_Jpan",
            t("target_ko"): "kor_Hang",
            t("target_es"): "spa_Latn",
            t("target_fr"): "fra_Latn",
            t("target_de"): "deu_Latn",
        }
        
        return target_map.get(target_display, "zho_Hant")
    
    def _save_settings(self, settings: dict):
        """Save settings to file."""
        sm = get_settings_manager()
        for key, value in settings.items():
            sm.set(key, value)
        sm.save()
    
    def _load_saved_settings(self):
        """Load saved settings from previous session."""
        sm = get_settings_manager()
        
        # Mode (handle legacy Chinese values)
        mode = sm.get("mode", "realtime")
        if mode in ["實時", "realtime"]:
            mode = "realtime"
        elif mode in ["精準", "precise"]:
            mode = "precise"
        self._on_mode_change(mode)
        
        if mode == "precise":
            # Load Whisper model
            model_id = sm.get("model", "large-v3")
            for display, mid in self.WHISPER_MODELS:
                if mid == model_id:
                    self.model_dropdown.setCurrentText(display)
                    break
            # Load language
            lang_code = sm.get("language", None)
            for display, lcode in self.LANGUAGES:
                if lcode == lang_code:
                    self.lang_dropdown.setCurrentText(display)
                    break
        else:
            # Realtime mode: load language to model dropdown
            lang_code = sm.get("language", "zh")
            for display, lcode in self.REALTIME_LANGUAGES:
                if lcode == lang_code:
                    self.model_dropdown.setCurrentText(display)
                    break
        
        # Translation
        self.trans_checkbox.setChecked(sm.get("enable_translation", False))
        
        # Translation engine - map engine ID to display name
        engine = sm.get("translation_engine", "nllb")
        engine_reverse_map = {
            "nllb": t("engine_nllb"),
            "google_free": t("engine_google_free"),
            "bing": t("engine_bing"),
            "youdao": t("engine_youdao"),
            # Legacy support
            "google": t("engine_google_free"),
            "baidu": t("engine_bing"),
            "alibaba": t("engine_bing"),
        }
        display_name = engine_reverse_map.get(engine, t("engine_nllb"))
        self.trans_engine_dropdown.setCurrentText(display_name)
        
        # Target language
        target = sm.get("target_language", "zho_Hant")
        target_map = {
            "zho_Hant": t("target_zh_TW"),
            "zho_Hans": t("target_zh_CN"),
            "eng_Latn": t("target_en"),
            "jpn_Jpan": t("target_ja"),
            "kor_Hang": t("target_ko"),
            "spa_Latn": t("target_es"),
            "fra_Latn": t("target_fr"),
            "deu_Latn": t("target_de"),
        }
        if target in target_map:
            self.target_lang_dropdown.setCurrentText(target_map[target])
        
        # VAD
        self.vad_checkbox.setChecked(sm.get("use_vad", True))
    
    # === Public API ===
    
    def show_running(self):
        """Update UI to show running state."""
        self._is_running = True
        self.start_button.setText("⏹ " + t("stop"))
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #E04040;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F05050;
            }
        """)
        self.status_label.setText(t("status_running"))
        self.status_label.setStyleSheet("color: #3B8ED0;")
    
    def show_stopped(self):
        """Update UI to show stopped state."""
        self._is_running = False
        self.start_button.setText("🎙 " + t("start"))
        self.start_button.setStyleSheet("")  # Reset to default
        self.status_label.setText(t("status_ready"))
        self.status_label.setStyleSheet("color: #888888;")
    
    def _update_status_label(self, text: str, color: str):
        """Update status label (thread-safe via signal)."""
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")


# Quick test
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    def on_start(settings):
        print(f"Start clicked: {settings}")
    
    window = SettingsWindow(on_start=on_start)
    window.show()
    
    sys.exit(app.exec())
