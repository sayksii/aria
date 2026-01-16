"""
Model Manager Window using PyQt6.
"""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QFrame, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont
from typing import Optional, Dict, Callable
import threading
import os
import subprocess

from ..model_manager import ModelManager, ModelInfo, ModelType, ModelStatus
from ..i18n import t


class ModelRow(QFrame):
    """A single row displaying a model's status and actions."""
    
    progress_updated = pyqtSignal(float, str)
    
    def __init__(
        self,
        model: ModelInfo,
        manager: ModelManager,
        on_status_change: Optional[Callable] = None,
    ):
        super().__init__()
        
        self.model = model
        self.manager = manager
        self.on_status_change = on_status_change
        
        self.setObjectName("model_row")
        self.setStyleSheet("""
            #model_row {
                background-color: #333333;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        self._create_ui()
        self._update_status()
        
        # Connect signal
        self.progress_updated.connect(self._update_progress_ui)
    
    def _create_ui(self):
        """Create the row UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)
        
        # Top row: name and size
        top_row = QHBoxLayout()
        
        # Model name with emoji if recommended
        name = t(self.model.name) if self.model.name.startswith("model_name_") else self.model.name
        if "large-v3" in self.model.id and "turbo" not in self.model.id:
            name = "⭐ " + name  # Recommended
        
        self.name_label = QLabel(name)
        self.name_label.setFont(QFont("", 12, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: white;")
        top_row.addWidget(self.name_label)
        
        top_row.addStretch()
        
        # Size
        size_label = QLabel(f"({self.model.get_size_display()})")
        size_label.setStyleSheet("color: #888888;")
        top_row.addWidget(size_label)
        
        layout.addLayout(top_row)
        
        # Description
        desc = t(self.model.description) if self.model.description.startswith("model_desc_") else self.model.description
        if desc:
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #444444;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3B8ED0;
                border-radius: 4px;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Status text
        self.status_text = QLabel("")
        self.status_text.setStyleSheet("color: #888888; font-size: 11px;")
        self.status_text.hide()
        layout.addWidget(self.status_text)

        # Progress disclaimer
        self.progress_note = QLabel(t("download_progress_note"))
        self.progress_note.setStyleSheet("color: #666666; font-size: 10px;")
        self.progress_note.hide()
        layout.addWidget(self.progress_note)
        
        # Action button
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        self.action_button = QPushButton(t("download"))
        self.action_button.setMaximumWidth(120)
        self.action_button.clicked.connect(self._on_action)
        button_row.addWidget(self.action_button)
        
        layout.addLayout(button_row)
    
    def _update_status(self):
        """Update UI based on model status."""
        status = self.manager.get_status(self.model)
        
        if status == ModelStatus.DOWNLOADED:
            self.action_button.setText(t("downloaded"))
            self.action_button.setEnabled(False)
            self.action_button.setStyleSheet("""
                QPushButton {
                    background-color: #2a5a2a;
                    color: #90EE90;
                    border-radius: 6px;
                }
            """)
            self.progress_bar.hide()
            self.status_text.hide()
            self.progress_note.hide()
        elif status == ModelStatus.DOWNLOADING:
            self.action_button.setText(t("downloading"))
            self.action_button.setEnabled(False)
            self.progress_bar.show()
            self.status_text.show()
            self.progress_note.show()
        else:
            self.action_button.setText(t("download"))
            self.action_button.setEnabled(True)
            self.action_button.setStyleSheet("")
            self.progress_bar.hide()
            self.status_text.hide()
            self.progress_note.hide()
    
    def _on_action(self):
        """Handle action button click."""
        status = self.manager.get_status(self.model)
        if status == ModelStatus.NOT_DOWNLOADED:
            self._start_download()
    
    def _start_download(self):
        """Start downloading the model."""
        self.action_button.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_text.show()
        self.progress_note.show()
        
        def progress_callback(model_id: str, progress: float, status_text: str):
            self.progress_updated.emit(progress, status_text)
        
        # Start download in background
        self.manager.download(self.model, progress_callback)
    
    def _update_progress_ui(self, progress: float, status_text: str):
        """Update progress display (called from signal)."""
        self.progress_bar.setValue(int(progress * 100))
        self.status_text.setText(status_text)
        self.progress_note.show()
        
        if progress >= 1.0:
            self._update_status()
            if self.on_status_change:
                self.on_status_change()


class ModelManagerWindow(QDialog):
    """Window for managing model downloads."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle(t("model_manager_title"))
        self.setFixedSize(650, 550)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background-color: #3B8ED0;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4AA3E0;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        
        self.manager = ModelManager()
        self.model_rows: Dict[str, ModelRow] = {}
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the window UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("📦 " + t("model_manager_title"))
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Scroll area for models
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 5px;
                min-height: 20px;
            }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)
        
        # Whisper models section
        self._create_model_section(scroll_layout, t("whisper_models"), [ModelType.WHISPER])
        
        # Translation models section
        self._create_model_section(scroll_layout, t("translation_models"), [ModelType.NLLB])
        
        # Streaming models section
        self._create_model_section(scroll_layout, t("streaming_models"), [ModelType.SHERPA, ModelType.VOSK])
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Footer buttons
        footer = QHBoxLayout()
        
        open_folder_btn = QPushButton("📁 " + t("open_models_folder"))
        open_folder_btn.clicked.connect(self._open_models_folder)
        footer.addWidget(open_folder_btn)
        
        footer.addStretch()
        
        close_btn = QPushButton(t("close"))
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)
        
        layout.addLayout(footer)
    
    def _create_model_section(self, parent_layout, title: str, model_types):
        """Create a section for a group of models."""
        # Section title
        section_title = QLabel(title)
        section_title.setFont(QFont("", 13, QFont.Weight.Bold))
        section_title.setStyleSheet("color: #888888; margin-top: 10px;")
        parent_layout.addWidget(section_title)
        
        # Model rows
        for model in self.manager.get_all_models():
            if model.model_type in model_types:
                row = ModelRow(model, self.manager, self._on_status_change)
                self.model_rows[model.id] = row
                parent_layout.addWidget(row)
    
    def _on_status_change(self):
        """Called when any model's status changes."""
        pass
    
    def _open_models_folder(self):
        """Open the models folder in file explorer."""
        models_dir = self.manager.models_dir
        if not models_dir.exists():
            models_dir.mkdir(parents=True, exist_ok=True)
        
        # Open in file explorer
        if os.name == 'nt':
            os.startfile(str(models_dir))
        else:
            subprocess.run(['xdg-open', str(models_dir)])


class ModelDownloadDialog(QDialog):
    """Dialog for downloading missing models."""
    
    progress_updated = pyqtSignal(str, float, str)
    
    def __init__(self, parent, models_to_download: list, on_complete: Optional[Callable] = None):
        super().__init__(parent)
        
        self.models_to_download = models_to_download
        self.on_complete = on_complete
        self.manager = ModelManager()
        self._completed_count = 0
        self._destroyed = False
        
        self.setWindowTitle(t("download_title"))
        # Dynamic height: base 200 + 140 per model
        height = 200 + (len(models_to_download) * 140)
        self.setFixedSize(500, min(height, 600))
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                color: white;
            }
        """)
        
        self._create_ui()
        self._start_downloads()
        
        # Connect signal
        self.progress_updated.connect(self._update_progress)
    
    def _create_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("📥 " + t("downloading_models"))
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Model progress sections
        self.progress_widgets = {}
        
        for model in self.models_to_download:
            frame = QFrame()
            frame.setMinimumHeight(110)
            frame.setStyleSheet("""
                QFrame {
                    background-color: #2a2a2a;
                    border-radius: 8px;
                }
            """)
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(15, 15, 15, 15)
            frame_layout.setSpacing(8)
            
            name = t(model.name) if model.name.startswith("model_name_") else model.name
            name_label = QLabel(f"{name} ({model.get_size_display()})")
            name_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
            name_label.setMinimumHeight(22)
            frame_layout.addWidget(name_label)
            
            progress_bar = QProgressBar()
            progress_bar.setMaximum(100)
            progress_bar.setMinimumHeight(20)
            progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #444444;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background-color: #3B8ED0;
                    border-radius: 4px;
                }
            """)
            frame_layout.addWidget(progress_bar)
            
            status_label = QLabel(t("download_waiting"))
            status_label.setStyleSheet("color: #888888; font-size: 11px;")
            status_label.setMinimumHeight(18)
            frame_layout.addWidget(status_label)

            progress_note = QLabel(t("download_progress_note"))
            progress_note.setStyleSheet("color: #666666; font-size: 10px;")
            progress_note.setMinimumHeight(16)
            frame_layout.addWidget(progress_note)
            
            layout.addWidget(frame)
            
            self.progress_widgets[model.id] = {
                "progress_bar": progress_bar,
                "status_label": status_label,
            }
        
        layout.addStretch()
        
        # Cancel button (enabled during download)
        self.cancel_button = QPushButton(t("cancel_download"))
        self.cancel_button.setEnabled(True)
        self.cancel_button.clicked.connect(self._on_close)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        layout.addWidget(self.cancel_button)
    
    def _start_downloads(self):
        """Start downloading all models."""
        for model in self.models_to_download:
            def make_callback(m):
                return lambda mid, prog, status: self.progress_updated.emit(m.id, prog, status)
            
            self.manager.download(model, make_callback(model))
    
    def _update_progress(self, model_id: str, progress: float, status_text: str):
        """Update progress for a model."""
        if self._destroyed or model_id not in self.progress_widgets:
            return
        
        widgets = self.progress_widgets[model_id]
        widgets["progress_bar"].setValue(int(progress * 100))
        widgets["status_label"].setText(status_text)
        
        if progress >= 1.0:
            self._completed_count += 1
            self._check_all_complete()
    
    def _check_all_complete(self):
        """Check if all downloads are complete."""
        if self._completed_count >= len(self.models_to_download):
            self.cancel_button.setText(t("close"))
            self.cancel_button.setStyleSheet("""
                QPushButton {
                    background-color: #3B8ED0;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px;
                }
                QPushButton:hover {
                    background-color: #4B9EE0;
                }
            """)
    
    def _on_close(self):
        """Handle dialog close."""
        # Check if any download is still in progress
        if self._completed_count < len(self.models_to_download):
            result = QMessageBox.question(
                self,
                t("download_in_progress"),
                t("download_cancel_confirm"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return
            
            # User confirmed cancel - delete partial downloaded models and force quit
            import shutil
            
            for model in self.models_to_download:
                model_path = self.manager.get_model_path(model)
                if model_path and model_path.exists():
                    try:
                        if model_path.is_dir():
                            shutil.rmtree(model_path)
                        else:
                            os.remove(model_path)
                    except Exception:
                        pass
                
                # Also try to clear HuggingFace cache
                if model.hf_repo:
                    try:
                        hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
                        repo_name = model.hf_repo.replace("/", "--")
                        for entry in os.listdir(hf_cache):
                            if repo_name in entry:
                                cache_path = os.path.join(hf_cache, entry)
                                if os.path.isdir(cache_path):
                                    shutil.rmtree(cache_path)
                    except Exception:
                        pass
            
            # Force exit
            os._exit(0)

        self._destroyed = True
        self.accept()
    
    def closeEvent(self, event):
        """Handle window close."""
        if self._destroyed:
            event.accept()
            return

        event.ignore()
        self._on_close()


def show_model_manager(parent=None):
    """Show the model manager window."""
    dialog = ModelManagerWindow(parent)
    dialog.exec()


def show_download_dialog(parent, models_to_download: list, on_complete=None):
    """Show the download dialog for specific models."""
    dialog = ModelDownloadDialog(parent, models_to_download, on_complete)
    dialog.exec()
