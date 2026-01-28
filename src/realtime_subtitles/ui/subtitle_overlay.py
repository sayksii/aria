"""
Floating Subtitle Overlay Window using PyQt6.

A transparent, always-on-top, draggable window that displays subtitles.
"""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QApplication, QSizeGrip, QFrame, QTextEdit
)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QScreen
from typing import Optional, Callable
import sys

from realtime_subtitles.settings_manager import get_settings_manager


class SubtitleOverlay(QWidget):
    """
    Transparent floating subtitle overlay using PyQt6.
    
    Features:
    - Transparent background
    - Always on top
    - Draggable
    - Positioned at bottom of screen
    """
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position_key: str = "overlay",
        on_close: Optional[Callable] = None,
    ):
        """Initialize the overlay window.
        
        Args:
            parent: Parent widget (optional)
            position_key: Key prefix for saving position
            on_close: Callback when window is closed
        """
        super().__init__(parent)
        
        self._position_key = position_key
        self._on_close_callback = on_close
        
        # Drag state
        self._drag_position: Optional[QPoint] = None
        
        # Window dimensions
        self._window_width = 1200
        self._window_height = 120
        
        # Setup window
        self._setup_window()
        self._create_ui()
        
        # Position window after a short delay
        QTimer.singleShot(100, self._position_window)
    
    def _setup_window(self) -> None:
        """Configure window flags and appearance."""
        # Frameless, always on top, tool window (no taskbar)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # Enable transparency
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set window title (for taskbar if shown)
        self.setWindowTitle("Subtitles")
        
        # Initial size
        self.resize(self._window_width, self._window_height)
    
    def _create_ui(self) -> None:
        """Create the UI elements."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        
        # Container frame with dark background
        self.container = QFrame()
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            #container {
                background-color: rgba(42, 42, 42, 230);
                border-radius: 12px;
            }
        """)
        layout.addWidget(self.container)
        
        # Container layout
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(8, 6, 8, 6)
        container_layout.setSpacing(5)
        
        # Subtitle label (main text) - using QTextEdit for auto-scroll
        self.subtitle_label = QTextEdit()
        self.subtitle_label.setReadOnly(True)
        self.subtitle_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.subtitle_label.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.subtitle_label.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.subtitle_label.setFrameStyle(QFrame.Shape.NoFrame)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.document().setDocumentMargin(20)  # Add left/right padding
        self.subtitle_label.setStyleSheet("""
            QTextEdit {
                color: white;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        container_layout.addWidget(self.subtitle_label)
        
        # Translation label - using QTextEdit for auto-scroll
        self.translation_label = QTextEdit()
        self.translation_label.setReadOnly(True)
        self.translation_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.translation_label.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.translation_label.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.translation_label.setFrameStyle(QFrame.Shape.NoFrame)
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.translation_label.document().setDocumentMargin(20)  # Add left/right padding
        self.translation_label.setStyleSheet("""
            QTextEdit {
                color: #90EE90;
                font-size: 20px;
                background: transparent;
                border: none;
            }
        """)
        self.translation_label.hide()  # Hidden by default
        container_layout.addWidget(self.translation_label)
        
        # Size grip for resizing (bottom right corner)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent;")
    
    def _position_window(self) -> None:
        """Position the window at saved position or default."""
        # Get screen dimensions
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # Dynamic width based on resolution
        if screen_width >= 3840:
            width_ratio = 0.40  # 4K
        elif screen_width >= 2560:
            width_ratio = 0.55  # 1440p
        else:
            width_ratio = 0.70  # 1080p
        
        self._window_width = int(screen_width * width_ratio)
        
        # Try to load saved position
        settings = get_settings_manager()
        saved_x = settings.get(f"{self._position_key}_x", None)
        saved_y = settings.get(f"{self._position_key}_y", None)
        
        if saved_x is not None and saved_y is not None:
            x, y = saved_x, saved_y
        else:
            # Default: center horizontally, 65% from top
            x = (screen_width - self._window_width) // 2
            y = int(screen_height * 0.65)
        
        self.resize(self._window_width, self._window_height)
        self.move(x, y)
    
    def _save_position(self) -> None:
        """Save current position to settings."""
        settings = get_settings_manager()
        settings.set(f"{self._position_key}_x", self.x())
        settings.set(f"{self._position_key}_y", self.y())
        settings.save()
    
    # === Drag to move ===
    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if self._drag_position is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release - save position."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = None
            self._save_position()
            event.accept()
    
    # === Window close ===
    def closeEvent(self, event):
        """Handle window close."""
        if self._on_close_callback:
            self._on_close_callback()
        event.accept()
    
    # === Public API ===
    def update_subtitle(
        self,
        text: str,
        language: str = "",
        translated_text: str = None,
        committed_translation: str = None,
        draft_translation: str = None,
    ) -> None:
        """Update the displayed subtitle.
        
        Args:
            text: Subtitle text to display
            language: Language code (unused currently)
            translated_text: Translated text (optional)
            committed_translation: Stable translation text (white)
            draft_translation: Unstable/draft translation text (green)
        """
        self.subtitle_label.setPlainText(text)
        # Auto-scroll to bottom to show latest content
        self.subtitle_label.verticalScrollBar().setValue(
            self.subtitle_label.verticalScrollBar().maximum()
        )
        
        # Handle translation with dual-color support (committed=white, draft=green)
        if committed_translation is not None or draft_translation is not None:
            committed = committed_translation or ""
            draft = draft_translation or ""
            
            # Build HTML with dual colors
            html_parts = []
            if committed:
                # White text for committed (stable)
                escaped_committed = committed.replace('\n', '<br>')
                html_parts.append(f'<span style="color: white;">{escaped_committed}</span>')
            if draft:
                # Green text for draft (in progress)
                escaped_draft = draft.replace('\n', '<br>')
                html_parts.append(f'<span style="color: #90EE90;">{escaped_draft}</span>')
            
            if html_parts:
                html_content = '<br>'.join(html_parts)
                self.translation_label.setHtml(html_content)
                self.translation_label.verticalScrollBar().setValue(
                    self.translation_label.verticalScrollBar().maximum()
                )
                self.translation_label.show()
            else:
                self.translation_label.hide()
        elif translated_text and translated_text.strip():
            # Simple mode: just show translated text in default color
            self.translation_label.setPlainText(translated_text)
            self.translation_label.verticalScrollBar().setValue(
                self.translation_label.verticalScrollBar().maximum()
            )
            self.translation_label.show()
        else:
            self.translation_label.hide()
        
        # Show if hidden
        if not self.isVisible():
            self.show()
    
    def clear(self) -> None:
        """Clear the subtitle display."""
        self.subtitle_label.setPlainText("")
        self.translation_label.setPlainText("")
        self.translation_label.hide()
    
    def set_multiline_mode(self, enabled: bool) -> None:
        """Enable multiline mode (taller overlay)."""
        if enabled:
            self._window_height = 180
            self.subtitle_label.setStyleSheet("""
                QTextEdit {
                    color: white;
                    font-size: 22px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }
            """)
        else:
            self._window_height = 120
            self.subtitle_label.setStyleSheet("""
                QTextEdit {
                    color: white;
                    font-size: 24px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }
            """)
        self.resize(self._window_width, self._window_height)
    
    def set_translation_mode(self, enabled: bool) -> None:
        """Configure as translation overlay (green text)."""
        if enabled:
            self.subtitle_label.setStyleSheet("""
                QTextEdit {
                    color: #90EE90;
                    font-size: 24px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }
            """)


# Test
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    overlay = SubtitleOverlay()
    overlay.show()
    overlay.update_subtitle("Hello, this is a test subtitle!", "en")
    
    # Test multiline
    def test_multiline():
        overlay.update_subtitle(
            "This is a very long subtitle that should wrap to multiple lines. "
            "Let's see how PyQt6 handles word wrapping compared to Tkinter.",
            "en",
            "這是一個很長的翻譯文字，應該要自動換行顯示。"
        )
    
    QTimer.singleShot(2000, test_multiline)
    
    sys.exit(app.exec())
