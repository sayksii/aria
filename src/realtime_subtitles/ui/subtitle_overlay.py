"""
Floating Subtitle Overlay Window.

A transparent, always-on-top, click-through window that displays subtitles
at the bottom of the screen.
"""

import customtkinter as ctk
import tkinter as tk
from typing import Optional
import ctypes
import sys
from realtime_subtitles.settings_manager import get_settings_manager

# Enable DPI awareness on Windows for proper 4K/HiDPI support
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class SubtitleOverlay(ctk.CTkToplevel):
    """
    Transparent floating subtitle overlay.
    
    Features:
    - Transparent background
    - Always on top
    - Click-through (mouse events pass through)
    - Positioned at bottom of screen
    """
    
    def __init__(self, parent: Optional[ctk.CTk] = None):
        """Initialize the overlay window."""
        super().__init__(parent)
        
        # Window setup
        self.title("Subtitles")
        self.overrideredirect(True)  # Remove window decorations
        self.attributes("-topmost", True)  # Always on top
        
        # Window dimensions
        self._window_width = 1200
        self._window_height = 80
        
        # Initial geometry (will be repositioned after UI is ready)
        self.geometry(f"{self._window_width}x{self._window_height}")
        
        # Semi-transparent dark background
        self.configure(fg_color="#1a1a1a")
        self.attributes("-alpha", 0.9)
        
        # Drag state
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Resize state
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_w = 0
        self._resize_start_h = 0
        
        # Create subtitle label
        self._create_ui()
        
        # Bind drag events
        self._setup_drag()
        self._setup_resize()
        
        # Current subtitle text
        self._current_text = ""
        self._language = ""
        
        # Position after window is ready
        self.after(100, self._position_window)
    
    def _position_window(self) -> None:
        """Position the window at the saved position or default middle-lower screen."""
        self.update_idletasks()
        
        # Get actual screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Dynamic window width (40% of screen width for better fit)
        self._window_width = int(screen_width * 0.4)
        
        # Try to load saved position
        settings = get_settings_manager()
        saved_x = settings.get("overlay_x", None)
        saved_y = settings.get("overlay_y", None)
        
        if saved_x is not None and saved_y is not None:
            # Use saved position
            x = saved_x
            y = saved_y
        else:
            # Default: center horizontally, position at 65% height (middle-lower)
            x = (screen_width - self._window_width) // 2
            y = int(screen_height * 0.65)
        
        self.geometry(f"{self._window_width}x{self._window_height}+{x}+{y}")
    
    def _setup_drag(self) -> None:
        """Setup drag-to-move functionality."""
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_drag_end)
        self.container.bind("<ButtonPress-1>", self._on_drag_start)
        self.container.bind("<B1-Motion>", self._on_drag_motion)
        self.container.bind("<ButtonRelease-1>", self._on_drag_end)
        self.subtitle_label.bind("<ButtonPress-1>", self._on_drag_start)
        self.subtitle_label.bind("<B1-Motion>", self._on_drag_motion)
        self.subtitle_label.bind("<ButtonRelease-1>", self._on_drag_end)
        self.lang_label.bind("<ButtonPress-1>", self._on_drag_start)
        self.lang_label.bind("<B1-Motion>", self._on_drag_motion)
        self.lang_label.bind("<ButtonRelease-1>", self._on_drag_end)
    
    def _on_drag_start(self, event) -> None:
        """Record starting position for drag."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def _on_drag_motion(self, event) -> None:
        """Move window during drag."""
        x = self.winfo_x() + (event.x - self._drag_start_x)
        y = self.winfo_y() + (event.y - self._drag_start_y)
        self.geometry(f"+{x}+{y}")
    
    def _on_drag_end(self, event) -> None:
        """Save position when drag ends."""
        x = self.winfo_x()
        y = self.winfo_y()
        self._save_position(x, y)
    
    def _save_position(self, x: int, y: int) -> None:
        """Save overlay position to settings."""
        settings = get_settings_manager()
        settings.set("overlay_x", x)
        settings.set("overlay_y", y)
        settings.save()
        
    def _setup_resize(self) -> None:
        """Setup resize grip."""
        self.resize_grip = ctk.CTkLabel(
            self,
            text="◢",
            font=ctk.CTkFont(size=12),
            text_color="#666666",
            width=15,
            height=15,
            cursor="size_nw_se"
        )
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)
        
        self.resize_grip.bind("<ButtonPress-1>", self._on_resize_start)
        self.resize_grip.bind("<B1-Motion>", self._on_resize_motion)
        
    def _on_resize_start(self, event) -> None:
        """Record starting size for resize."""
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.winfo_width()
        self._resize_start_h = self.winfo_height()

    def _on_resize_motion(self, event) -> None:
        """Resize window."""
        delta_x = event.x_root - self._resize_start_x
        delta_y = event.y_root - self._resize_start_y
        
        new_w = max(200, self._resize_start_w + delta_x)
        new_h = max(50, self._resize_start_h + delta_y)
        
        self.geometry(f"{new_w}x{new_h}")
        self._window_width = new_w
        self._window_height = new_h
    
    def _create_ui(self) -> None:
        """Create the subtitle display."""
        # Main container with rounded corners effect
        self.container = ctk.CTkFrame(
            self,
            fg_color="#2a2a2a",
            corner_radius=12,
        )
        self.container.pack(fill="both", expand=True, padx=5, pady=4)
        
        # Language indicator (small, top left) - hidden by default
        self.lang_label = ctk.CTkLabel(
            self.container,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#888888",
            height=0,
        )
        # Don't pack lang_label if empty, only show when has content
        
        # Original text - use Textbox for proper multiline and wrapping
        self.subtitle_textbox = ctk.CTkTextbox(
            self.container,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white",
            fg_color="transparent",
            bg_color="transparent",
            wrap="word",  # Wrap at word boundaries
            height=50,
            activate_scrollbars=False,
            border_width=0,
        )
        self.subtitle_textbox.pack(expand=True, fill="both", padx=10, pady=(10, 2))
        self.subtitle_textbox.configure(state="disabled")  # Read-only
        # Center text horizontally
        self.subtitle_textbox.tag_config("center", justify="center")
        
        # Translation text - separate box with different color
        self.translation_textbox = ctk.CTkTextbox(
            self.container,
            font=ctk.CTkFont(size=20),
            text_color="#90EE90",  # Light green for translation
            fg_color="transparent",
            bg_color="transparent",
            wrap="word",
            height=40,
            activate_scrollbars=False,
            border_width=0,
        )
        self.translation_textbox.pack(expand=True, fill="both", padx=10, pady=(0, 5))
        self.translation_textbox.configure(state="disabled")
        self.translation_textbox.pack_forget()  # Hidden by default
        # Center text horizontally
        self.translation_textbox.tag_config("center", justify="center")
        
        # Keep reference for compatibility
        self.subtitle_label = self.subtitle_textbox
    
    def update_subtitle(
        self,
        text: str,
        language: str = "",
        translated_text: str = None,
    ) -> None:
        """
        Update the displayed subtitle.
        
        Args:
            text: Subtitle text to display (original)
            language: Language code (for display)
            translated_text: Translated text (optional - shown in separate box)
        """
        self._current_text = text
        self._language = language
        
        # Update original text
        self.subtitle_textbox.configure(state="normal")
        self.subtitle_textbox.delete("1.0", "end")
        self.subtitle_textbox.insert("1.0", text, "center")
        self.subtitle_textbox.configure(state="disabled")
        
        # Update translation (only preserve if same text, otherwise clear)
        if translated_text:
            self._last_translation = translated_text
            self._last_translation_text = text
        elif hasattr(self, '_last_translation_text') and self._last_translation_text != text:
            # Text changed but no new translation - clear old translation
            self._last_translation = None
        
        # Only show translation if we have actual content
        display_translation = translated_text.strip() if translated_text else None
        
        # Update translation textbox
        if display_translation:
            self.translation_textbox.pack(expand=True, fill="both", padx=15, pady=(0, 10))
            self.translation_textbox.configure(state="normal")
            self.translation_textbox.delete("1.0", "end")
            self.translation_textbox.insert("1.0", display_translation, "center")
            self.translation_textbox.configure(state="disabled")
        else:
            # Hide translation box if no translation
            try:
                self.translation_textbox.pack_forget()
            except Exception:
                pass
        
        if language:
            self.lang_label.configure(text=f"[{language.upper()}]")
            self.lang_label.pack(anchor="w", padx=5, pady=0)
        else:
            self.lang_label.pack_forget()
        
        # Show window if hidden
        if not self.winfo_viewable():
            self.deiconify()
    
    def clear(self) -> None:
        """Clear the subtitle display."""
        self.subtitle_textbox.configure(state="normal")
        self.subtitle_textbox.delete("1.0", "end")
        self.subtitle_textbox.configure(state="disabled")
        self.lang_label.configure(text="")
        self._current_text = ""
        self._language = ""
    
    def show(self) -> None:
        """Show the overlay."""
        self.deiconify()
        self.attributes("-topmost", True)
    
    def hide(self) -> None:
        """Hide the overlay."""
        try:
            if self.winfo_exists():
                self.withdraw()
        except Exception:
            pass
    
    def set_multiline_mode(self, enabled: bool) -> None:
        """
        Enable or disable multiline mode for streaming subtitles.
        
        Args:
            enabled: True to enable multiline (taller overlay, auto-wrap)
        """
        try:
            if enabled:
                # Taller overlay for multiline streaming + translation
                self._window_height = 180
                self.subtitle_textbox.configure(
                    font=ctk.CTkFont(size=22, weight="bold"),
                    height=60,
                )
                self.translation_textbox.configure(height=60)
            else:
                # Normal single-line overlay + translation
                self._window_height = 130
                self.subtitle_textbox.configure(
                    font=ctk.CTkFont(size=24, weight="bold"),
                    height=40,
                )
                self.translation_textbox.configure(height=40)
        except Exception:
            pass  # Widget may be destroyed
        
        # Update geometry
        self._position_window()
    
    def set_translation_mode(self, enabled: bool) -> None:
        """
        Configure this overlay for translation display.
        
        Args:
            enabled: True to set translation mode (green text, positioned higher)
        """
        if enabled:
            # Green text for translation
            self.subtitle_textbox.configure(text_color="#90EE90")
            
            # Position higher on screen (above the original text overlay)
            self._is_translation_mode = True
            
            # Adjust position to be higher
            self._reposition_for_translation()
    
    def _reposition_for_translation(self) -> None:
        """Reposition overlay for translation (higher on screen)."""
        self.update_idletasks()
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        self._window_width = int(screen_width * 0.4)
        x = (screen_width - self._window_width) // 2 - screen_width // 4
        x = max(50, x)
        
        # Position higher than original (above original subtitle)
        y = int(screen_height * 0.70)  # Higher position
        
        self.geometry(f"{self._window_width}x{self._window_height}+{x}+{y}")


# Quick test
if __name__ == "__main__":
    import time
    
    root = ctk.CTk()
    root.withdraw()  # Hide main window
    
    overlay = SubtitleOverlay(root)
    
    # Test subtitles
    test_texts = [
        ("Hello, this is a test subtitle.", "en"),
        ("這是一個測試字幕。", "zh"),
        ("これはテスト字幕です。", "ja"),
        ("Real-time AI Subtitles - 全域即時 AI 字幕掛件", ""),
    ]
    
    def cycle_subtitles(index=0):
        if index < len(test_texts):
            text, lang = test_texts[index]
            overlay.update_subtitle(text, lang)
            root.after(2000, lambda: cycle_subtitles(index + 1))
        else:
            root.after(2000, root.destroy)
    
    root.after(1000, cycle_subtitles)
    root.mainloop()
