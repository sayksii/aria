"""Main Settings Window for ARIA."""

A modern, beautiful settings interface using CustomTkinter.
"""

import customtkinter as ctk
from typing import Callable, Optional
import threading

from ..settings_manager import get_settings_manager
from .model_manager_window import show_model_manager
from ..i18n import t, get_current_language, set_language, LANGUAGES


# Configure CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SettingsWindow(ctk.CTk):
    """
    Main settings window with model selection, language, VAD options, etc.
    """
    
    
    # Internal model IDs (without display names - use _get_models() for display)
    MODEL_IDS = ["large-v3", "large-v3-turbo", "medium"]
    
    # Internal language codes (use _get_languages() for display)
    LANGUAGE_CODES = [None, "zh", "en", "ja", "ko", "yue", "es", "fr", "de"]
    
    @staticmethod
    def _get_models():
        """Get models list with translated display names."""
        return [
            (t("model_large_v3"), "large-v3"),
            (t("model_large_v3_turbo"), "large-v3-turbo"),
            (t("model_medium"), "medium"),
        ]
    
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
        ]
    
    # Keep MODELS and LANGUAGES as property for backward compatibility
    @property
    def MODELS(self):
        return self._get_models()
    
    @property
    def LANGUAGES(self):
        return self._get_languages()
    
    def __init__(self, on_start: Callable[[dict], None]):
        """
        Initialize the settings window.
        
        Args:
            on_start: Callback when user clicks Start. Called with settings dict.
        """
        super().__init__()
        
        self.on_start = on_start
        self._is_running = False
        self._settings_mgr = get_settings_manager()
        
        # Window setup
        self.title("ARIA")
        self.geometry("800x630")  # Wider layout for English text
        self.resizable(False, False)
        
        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 800) // 2
        y = (self.winfo_screenheight() - 630) // 2
        self.geometry(f"+{x}+{y}")
        
        # Build UI
        self._create_ui()
        
        # Load saved settings
        self._load_saved_settings()
    
    def _create_ui(self) -> None:
        """Create all UI components with horizontal layout."""
        # Main container with padding
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header row with title and language selector
        header_frame = ctk.CTkFrame(container, fg_color="transparent", height=60)
        header_frame.pack(fill="x", pady=(0, 10))
        header_frame.pack_propagate(False)  # Fixed height
        
        # Title centered absolutely
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        title_label = ctk.CTkLabel(
            title_frame,
            text=t("window_title"),
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title_label.pack()
        
        subtitle_label = ctk.CTkLabel(
            title_frame,
            text=t("subtitle"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        subtitle_label.pack()
        
        # Language selector on the right (absolute position)
        lang_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        lang_frame.place(relx=1.0, rely=0.5, anchor="e", x=-10)
        
        lang_options = [LANGUAGES[code][0] for code in LANGUAGES]
        current_lang = get_current_language()
        current_lang_name = LANGUAGES.get(current_lang, LANGUAGES["zh_TW"])[0]
        
        self.lang_selector = ctk.CTkOptionMenu(
            lang_frame,
            values=lang_options,
            width=100,
            height=28,
            font=ctk.CTkFont(size=11),
            command=self._on_language_change,
        )
        self.lang_selector.set(current_lang_name)
        self.lang_selector.pack()
        
        # ===== Two-column layout using grid =====
        columns_frame = ctk.CTkFrame(container, fg_color="transparent")
        columns_frame.pack(fill="both", expand=True)
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.columnconfigure(1, weight=1)
        columns_frame.rowconfigure(0, weight=1)
        
        # Left column - Recognition + Model
        left_col = ctk.CTkFrame(columns_frame, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="new", padx=(0, 8))
        
        # Right column - Translation + VAD
        right_col = ctk.CTkFrame(columns_frame, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="new", padx=(8, 0))
        
        # ========== LEFT COLUMN ==========
        # === Recognition Settings Frame ===
        recog_frame = ctk.CTkFrame(left_col, height=200)
        recog_frame.pack(fill="x", pady=(0, 15))
        recog_frame.pack_propagate(False)  # Keep fixed height
        
        recog_title = ctk.CTkLabel(
            recog_frame,
            text=t("recognition_settings"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        recog_title.pack(fill="x", padx=18, pady=(15, 12))
        
        # Preset mode selection (centered) - FIRST: select mode
        mode_row = ctk.CTkFrame(recog_frame, fg_color="transparent")
        mode_row.pack(fill="x", padx=15, pady=(0, 5))
        
        self.mode_var = ctk.StringVar(value=t("mode_precise"))
        self.mode_selector = ctk.CTkSegmentedButton(
            mode_row,
            values=[t("mode_precise"), t("mode_realtime")],
            variable=self.mode_var,
            command=self._on_mode_change,
        )
        self.mode_selector.pack(expand=True)  # Center the button
        
        # Mode description (dynamic, shows based on selected mode)
        self.mode_desc = ctk.CTkLabel(
            recog_frame,
            text=t("mode_precise_desc"),  # Default for precise mode
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        )
        self.mode_desc.pack(pady=(0, 15))
        
        # === Model Settings Frame (in left column) ===
        model_frame = ctk.CTkFrame(left_col, height=200)
        model_frame.pack(fill="x", pady=(0, 15))
        model_frame.pack_propagate(False)  # Keep fixed height
        
        model_title = ctk.CTkLabel(
            model_frame,
            text=t("model_settings"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        model_title.pack(fill="x", padx=18, pady=(15, 12))
        
        # Model dropdown
        model_row = ctk.CTkFrame(model_frame, fg_color="transparent")
        model_row.pack(fill="x", padx=18, pady=(0, 10))
        
        ctk.CTkLabel(model_row, text=t("model") + ":", width=50, anchor="w").pack(side="left")
        self.model_var = ctk.StringVar(value="Large-v3 ⭐ (最準)")
        self.model_dropdown = ctk.CTkComboBox(
            model_row,
            values=[m[0] for m in self.MODELS],
            variable=self.model_var,
            width=200,
            state="readonly",
        )
        self.model_dropdown.pack(side="left", padx=(5, 0))
        
        # Language dropdown
        lang_row = ctk.CTkFrame(model_frame, fg_color="transparent")
        lang_row.pack(fill="x", padx=18, pady=(0, 15))
        
        ctk.CTkLabel(lang_row, text=t("lang") + ":", width=50, anchor="w").pack(side="left")
        self.lang_var = ctk.StringVar(value="自動偵測")
        self.lang_dropdown = ctk.CTkComboBox(
            lang_row,
            values=[l[0] for l in self.LANGUAGES],
            variable=self.lang_var,
            width=200,
            state="readonly",
        )
        self.lang_dropdown.pack(side="left", padx=(5, 0))
        # Use trace for reliable change detection (CTkComboBox command may not fire in streaming mode)
        self.lang_var.trace_add("write", self._on_lang_var_change)
        
        # Manage models button
        manage_models_row = ctk.CTkFrame(model_frame, fg_color="transparent")
        manage_models_row.pack(fill="x", padx=18, pady=(0, 15))
        
        self.manage_models_btn = ctk.CTkButton(
            manage_models_row,
            text=t("manage_models"),
            width=140,
            height=28,
            command=self._on_manage_models,
        )
        self.manage_models_btn.pack(side="left")
        
        # ========== RIGHT COLUMN ==========
        # === Translation Settings Frame ===
        trans_frame = ctk.CTkFrame(right_col, height=200)
        trans_frame.pack(fill="x", pady=(0, 15))
        trans_frame.pack_propagate(False)  # Keep fixed height
        
        trans_title = ctk.CTkLabel(
            trans_frame,
            text=t("translation_settings"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        trans_title.pack(fill="x", padx=18, pady=(15, 12))
        
        # Translation switch
        trans_row = ctk.CTkFrame(trans_frame, fg_color="transparent")
        trans_row.pack(fill="x", padx=18, pady=(0, 10))
        
        ctk.CTkLabel(trans_row, text=t("translation") + ":", width=60, anchor="w").pack(side="left")
        self.trans_var = ctk.BooleanVar(value=False)
        self.trans_switch = ctk.CTkSwitch(
            trans_row,
            text="",
            variable=self.trans_var,
            onvalue=True,
            offvalue=False,
            command=self._on_translation_change,
        )
        self.trans_switch.pack(side="left", padx=(5, 5))
        self.trans_label = ctk.CTkLabel(trans_row, text="OFF", text_color="gray")
        self.trans_label.pack(side="left")
        
        # Translation engine selection
        engine_row = ctk.CTkFrame(trans_frame, fg_color="transparent")
        engine_row.pack(fill="x", padx=18, pady=(0, 10))
        
        ctk.CTkLabel(engine_row, text=t("engine") + ":", width=60, anchor="w").pack(side="left")
        self.trans_engine_var = ctk.StringVar(value=t("engine_google"))
        self.trans_engine_dropdown = ctk.CTkComboBox(
            engine_row,
            values=[t("engine_google"), t("engine_nllb")],
            variable=self.trans_engine_var,
            width=180,
            state="readonly",
        )
        self.trans_engine_dropdown.pack(side="left", padx=(5, 0))
        
        # Target language dropdown
        target_row = ctk.CTkFrame(trans_frame, fg_color="transparent")
        target_row.pack(fill="x", padx=18, pady=(0, 15))
        
        ctk.CTkLabel(target_row, text=t("target_lang") + ":", width=60, anchor="w").pack(side="left")
        self.target_lang_var = ctk.StringVar(value=t("target_zh_TW"))
        self.target_lang_dropdown = ctk.CTkComboBox(
            target_row,
            values=[t("target_zh_TW"), t("target_zh_CN"), t("target_en"), t("target_ja"), t("target_ko"), t("target_es"), t("target_fr"), t("target_de")],
            variable=self.target_lang_var,
            width=180,
            state="readonly",
        )
        self.target_lang_dropdown.pack(side="left", padx=(5, 0))
        
        # === VAD Settings Frame (in right column) ===
        vad_frame = ctk.CTkFrame(right_col, height=140)
        vad_frame.pack(fill="x", pady=(0, 15))
        vad_frame.pack_propagate(False)  # Keep fixed height
        
        vad_title = ctk.CTkLabel(
            vad_frame,
            text=t("vad_settings"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        vad_title.pack(fill="x", padx=18, pady=(15, 12))
        
        # VAD container (can be hidden in streaming mode)
        self.vad_container = ctk.CTkFrame(vad_frame, fg_color="transparent")
        self.vad_container.pack(fill="x")
        
        # VAD switch
        vad_row = ctk.CTkFrame(self.vad_container, fg_color="transparent")
        vad_row.pack(fill="x", padx=15, pady=(0, 5))
        
        ctk.CTkLabel(vad_row, text=t("vad_label") + ":", width=120, anchor="w").pack(side="left")
        self.vad_var = ctk.BooleanVar(value=True)
        self.vad_switch = ctk.CTkSwitch(
            vad_row,
            text="",
            variable=self.vad_var,
            onvalue=True,
            offvalue=False,
        )
        self.vad_switch.pack(side="left", padx=(10, 0))
        self.vad_label = ctk.CTkLabel(vad_row, text="ON", text_color="#3B8ED0")
        self.vad_label.pack(side="left", padx=(10, 0))
        self.vad_var.trace_add("write", self._update_vad_label)
        
        # VAD description (can be updated based on mode)
        self.vad_desc = ctk.CTkLabel(
            self.vad_container,
            text=t("vad_desc_precise"),
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        )
        self.vad_desc.pack(padx=15, anchor="w", pady=(0, 10))
        
        # Custom settings container (hidden by default)
        self.custom_settings_frame = ctk.CTkFrame(vad_frame, fg_color="transparent")
        # Don't pack yet - will be shown when custom mode is selected
        
        # VAD sensitivity slider (silence duration to end speech)
        vad_sens_row = ctk.CTkFrame(self.custom_settings_frame, fg_color="transparent")
        vad_sens_row.pack(fill="x", padx=15, pady=(0, 10))
        
        ctk.CTkLabel(vad_sens_row, text=t("silence_threshold") + ":", width=120, anchor="w").pack(side="left")
        self.vad_silence_var = ctk.DoubleVar(value=500)  # Default for realtime mode
        self.vad_sens_slider = ctk.CTkSlider(
            vad_sens_row,
            from_=100,
            to=800,
            number_of_steps=14,
            variable=self.vad_silence_var,
            width=200,
        )
        self.vad_sens_slider.pack(side="left", padx=(10, 10))
        self.vad_sens_label = ctk.CTkLabel(vad_sens_row, text="500ms", width=50)
        self.vad_sens_label.pack(side="left")
        self.vad_silence_var.trace_add("write", self._update_vad_sens_label)
        
        # Min duration slider
        min_row = ctk.CTkFrame(self.custom_settings_frame, fg_color="transparent")
        min_row.pack(fill="x", padx=15, pady=(0, 10))
        
        ctk.CTkLabel(min_row, text=t("min_duration") + ":", width=120, anchor="w").pack(side="left")
        self.min_duration_var = ctk.DoubleVar(value=2.0)  # Default for realtime mode
        self.min_slider = ctk.CTkSlider(
            min_row,
            from_=0.5,
            to=5.0,
            number_of_steps=18,
            variable=self.min_duration_var,
            width=200,
        )
        self.min_slider.pack(side="left", padx=(10, 10))
        self.min_label = ctk.CTkLabel(min_row, text="2.0s", width=40)
        self.min_label.pack(side="left")
        self.min_duration_var.trace_add("write", self._update_min_label)
        
        # Max duration - fixed value (not exposed in UI)
        self.max_duration_var = ctk.DoubleVar(value=10.0)
        
        # === Start Button ===
        self.start_button = ctk.CTkButton(
            container,
            text=t("start_button"),
            font=ctk.CTkFont(size=18, weight="bold"),
            height=50,
            width=200,
            command=self._on_start_click,
        )
        self.start_button.pack(pady=(25, 20))
        
        # === Status ===
        self.status_label = ctk.CTkLabel(
            container,
            text=t("status_ready"),
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.status_label.pack(pady=(0, 10))
        
        # === Footer ===
        footer = ctk.CTkLabel(
            container,
            text="v0.1.0 | " + t("footer"),
            font=ctk.CTkFont(size=11),
            text_color="#666666",
        )
        footer.pack(side="bottom")
    
    def _on_mode_change(self, mode: str) -> None:
        """Handle preset mode change."""
        if mode == t("mode_precise"):
            # Precise mode: 150ms silence, 5s interval (uses Whisper)
            self.vad_silence_var.set(100)
            self.min_duration_var.set(100)
            self.custom_settings_frame.pack_forget()
            self.mode_desc.configure(text=t("mode_precise_desc"))
            # Enable VAD settings
            self.vad_switch.configure(state="normal")
            self.vad_var.set(True)
            self._update_vad_label()
            self.vad_desc.configure(text=t("vad_desc_precise"), text_color="#888888")
            # Restore Whisper models
            self.model_dropdown.configure(values=[m[0] for m in self.MODELS])
            self.model_var.set("Large-v3 ⭐ (最準)")
            # Restore full language options
            self.lang_dropdown.configure(values=[l[0] for l in self.LANGUAGES])
        else:  # Realtime (streaming with Sherpa/Vosk)
            # Realtime mode: streaming transcription
            self.custom_settings_frame.pack_forget()
            self.mode_desc.configure(text=t("mode_realtime_desc"))
            # Disable VAD settings (streaming engines have built-in endpoint detection)
            self.vad_switch.configure(state="disabled")
            self.vad_var.set(False)
            self._update_vad_label()
            self.vad_desc.configure(text=t("vad_desc_realtime"), text_color="#666666")
            # Show auto-engine message (engine is selected by language automatically)
            self.model_dropdown.configure(values=["Sherpa-ONNX"])
            self.model_var.set("Sherpa-ONNX")
            # Limit to languages with streaming models
            streaming_languages = [t("lang_chinese"), t("lang_english"), t("lang_japanese")]
            self.lang_dropdown.configure(values=streaming_languages)
            # If current selection is not valid, default to Chinese
            if self.lang_var.get() not in streaming_languages:
                self.lang_var.set(t("lang_chinese"))
            # Update model display based on language
            self._update_streaming_model_display()
            self._update_streaming_model_display()
    
    def _on_lang_var_change(self, *args) -> None:
        """Handle language variable change via trace."""
        if self.mode_var.get() == t("mode_realtime"):
            self._update_streaming_model_display()
    
    def _on_language_change(self, language: str) -> None:
        """Handle language change - update model display in streaming mode (legacy)."""
        if self.mode_var.get() == t("mode_realtime"):
            self._update_streaming_model_display()
    
    def _update_streaming_model_display(self) -> None:
        """Update model dropdown to show current streaming engine based on language."""
        lang_code = self._get_language_value()  # Get internal language code
        if lang_code == "ja":
            engine = "Vosk"
        else:  # Chinese or English - use Sherpa
            engine = "Sherpa-ONNX"
        
        self.model_dropdown.configure(values=[engine])
        self.model_var.set(engine)
    
    def _on_translation_change(self) -> None:
        """Handle translation switch change."""
        if self.trans_var.get():
            self.trans_label.configure(text="ON", text_color="#3B8ED0")
        else:
            self.trans_label.configure(text="OFF", text_color="gray")
    
    def _on_manage_models(self) -> None:
        """Open the model manager window."""
        show_model_manager(self)
    
    def _update_vad_label(self, *args) -> None:
        """Update VAD label when switch changes."""
        if self.vad_var.get():
            self.vad_label.configure(text="ON", text_color="#3B8ED0")
        else:
            self.vad_label.configure(text="OFF", text_color="gray")
    
    def _update_vad_sens_label(self, *args) -> None:
        """Update VAD sensitivity label."""
        self.vad_sens_label.configure(text=f"{int(self.vad_silence_var.get())}ms")
    
    def _update_min_label(self, *args) -> None:
        """Update min duration label."""
        self.min_label.configure(text=f"{self.min_duration_var.get():.1f}s")
    
    def _on_language_change(self, lang_display: str) -> None:
        """Handle UI language change."""
        from tkinter import messagebox
        
        # Find language code from display name
        lang_code = None
        for code, (name, _) in LANGUAGES.items():
            if name == lang_display:
                lang_code = code
                break
        
        if lang_code and lang_code != get_current_language():
            set_language(lang_code)
            # Restart the application
            import sys
            import subprocess
            # Start a new instance of the app
            subprocess.Popen([sys.executable, "-m", "realtime_subtitles.ui.app"])
            # Exit current instance
            sys.exit(0)
    
    def _get_model_value(self) -> str:
        """Get the actual model value from display name."""
        display = self.model_var.get()
        for name, value in self.MODELS:
            if name == display:
                return value
        return "base"
    
    def _get_language_value(self) -> Optional[str]:
        """Get the actual language value from display name."""
        display = self.lang_var.get()
        # First try the static LANGUAGES list
        for name, value in self.LANGUAGES:
            if name == display:
                return value
        
        # Fallback: check translated language names for streaming mode
        if display == t("lang_chinese"):
            return "zh"
        elif display == t("lang_english"):
            return "en"
        elif display == t("lang_japanese"):
            return "ja"
        elif display == t("auto_detect"):
            return None
        
        return None
    
    def _get_target_language_code(self) -> str:
        """Get the target language code from display name (NLLB format)."""
        display = self.target_lang_var.get()
        
        # Map from translation key to NLLB code
        key_to_code = {
            "target_zh_TW": "zho_Hant",
            "target_zh_CN": "zho_Hans",
            "target_en": "eng_Latn",
            "target_ja": "jpn_Jpan",
            "target_ko": "kor_Hang",
            "target_es": "spa_Latn",
            "target_fr": "fra_Latn",
            "target_de": "deu_Latn",
        }
        
        # Find the code by matching display text with translations
        for key, code in key_to_code.items():
            if display == t(key):
                return code
        
        # Fallback: check old Chinese values
        old_map = {
            "繁體中文": "zho_Hant", "繁体中文": "zho_Hant",
            "簡體中文": "zho_Hans", "简体中文": "zho_Hans",
            "英文": "eng_Latn", "English": "eng_Latn",
            "日文": "jpn_Jpan", "Japanese": "jpn_Jpan", "日本語": "jpn_Jpan",
        }
        return old_map.get(display, "zho_Hant")
    
    def _on_start_click(self) -> None:
        """Handle start/stop button click."""
        if self._is_running:
            # Already running - trigger stop via callback
            self.on_start(None)  # None signals stop
            return
        
        self._is_running = True
        self.start_button.configure(state="disabled", text=t("loading"))
        self.status_label.configure(text=t("status_loading_model"), text_color="#3B8ED0")
        
        # Convert mode display text to internal value
        mode_display = self.mode_var.get()
        if mode_display == t("mode_precise"):
            mode_internal = "precise"
        else:
            mode_internal = "realtime"
        
        # Gather settings
        settings = {
            "mode": mode_internal,  # Language-independent: "precise" or "realtime"
            "model": self._get_model_value(),
            "language": self._get_language_value(),
            "use_vad": self.vad_var.get(),
            "vad_silence_ms": int(self.vad_silence_var.get()),
            "min_duration": self.min_duration_var.get(),
            "max_duration": self.max_duration_var.get(),
            # Translation settings
            "enable_translation": self.trans_var.get(),
            "translation_engine": "google" if self.trans_engine_var.get() == t("engine_google") else "nllb",
            "target_language": self._get_target_language_code(),
        }
        
        # Save settings for next time
        self._settings_mgr.update({
            "mode": self.mode_var.get(),
            "model": self.model_var.get(),
            "language": self.lang_var.get(),
            "vad_enabled": self.vad_var.get(),
            "vad_silence_ms": int(self.vad_silence_var.get()),
            "min_duration": self.min_duration_var.get(),
            "enable_translation": self.trans_var.get(),
            "translation_engine": self.trans_engine_var.get(),
            "target_language": self.target_lang_var.get(),
        })
        self._settings_mgr.save()
        
        # Call callback (will hide window and start overlay)
        self.after(100, lambda: self.on_start(settings))
    
    def show_running(self) -> None:
        """Update UI to show running state."""
        self.start_button.configure(text=t("stop_button"), state="normal")
        self.status_label.configure(text=t("status_running"), text_color="#00AA00")
        self._is_running = True
    
    def show_stopped(self) -> None:
        """Update UI to show stopped state."""
        self.start_button.configure(text=t("start_button"), state="normal")
        self.status_label.configure(text=t("status_ready"), text_color="gray")
        self._is_running = False
    
    def _load_saved_settings(self) -> None:
        """Load saved settings from previous session."""
        # Mode - handle both internal values and legacy Chinese values
        saved_mode = self._settings_mgr.get("mode", "precise")
        if saved_mode in ["precise", "精準"]:
            display_mode = t("mode_precise")
        elif saved_mode in ["realtime", "實時"]:
            display_mode = t("mode_realtime")
        else:
            display_mode = t("mode_precise")  # Default
        
        self.mode_var.set(display_mode)
        self._on_mode_change(display_mode)
        
        # Model (only for precise mode)
        if saved_mode in ["precise", "精準"]:
            saved_model = self._settings_mgr.get("model", "")
            # Find the internal model ID from saved display name (may be in any language)
            model_id = None
            # Check if it's already an internal ID
            if saved_model in self.MODEL_IDS:
                model_id = saved_model
            else:
                # Try to find by partial match (the model name without language-specific suffix)
                for mid in self.MODEL_IDS:
                    if mid in saved_model.lower().replace("-", "").replace("_", ""):
                        model_id = mid
                        break
                # Fallback: check by position in old saved values
                if not model_id and "large-v3" in saved_model.lower() and "turbo" in saved_model.lower():
                    model_id = "large-v3-turbo"
                elif not model_id and "large" in saved_model.lower():
                    model_id = "large-v3"
                elif not model_id and "medium" in saved_model.lower():
                    model_id = "medium"
                else:
                    model_id = "large-v3"  # Default
            
            # Get the translated display name for this model ID
            for display_name, mid in self.MODELS:
                if mid == model_id:
                    self.model_var.set(display_name)
                    break
        
        # Language - convert saved language value to current translation
        saved_lang = self._settings_mgr.get("language", "")
        lang_code = None
        # Try to find the language code from saved display name
        for display_name, code in self.LANGUAGES:
            if saved_lang == display_name:
                lang_code = code
                break
        # Also check known old values
        lang_mapping = {
            "自動偵測": None, "自动检测": None, "Auto Detect": None,
            "中文 (繁/簡)": "zh", "中文 (繁/简)": "zh", "Chinese (Trad/Simp)": "zh",
            "英文": "en", "English": "en",
            "日文": "ja", "Japanese": "ja",
        }
        if lang_code is None:
            lang_code = lang_mapping.get(saved_lang, None)
        
        # Set the translated display name
        for display_name, code in self.LANGUAGES:
            if code == lang_code:
                self.lang_var.set(display_name)
                break
        
        # VAD settings
        self.vad_var.set(self._settings_mgr.get("vad_enabled", True))
        self.vad_silence_var.set(self._settings_mgr.get("vad_silence_ms", 150))
        self.min_duration_var.set(self._settings_mgr.get("min_duration", 5.0))
        
        # Translation settings
        trans_enabled = self._settings_mgr.get("enable_translation", False)
        self.trans_var.set(trans_enabled)
        self._on_translation_change()  # Update label
        
        # Translation engine - convert to current translation
        saved_engine = self._settings_mgr.get("translation_engine", "google")
        if saved_engine in ["google", "Google 雲端", "Google 云端", "Google Cloud"]:
            self.trans_engine_var.set(t("engine_google"))
        elif saved_engine in ["nllb", "NLLB 本地", "NLLB Local"]:
            self.trans_engine_var.set(t("engine_nllb"))
        else:
            self.trans_engine_var.set(t("engine_google"))  # Default
        
        # Target language - convert saved value to current translation
        saved_target = self._settings_mgr.get("target_language", "zho_Hant")
        # Map from any known value to translation key
        target_key_map = {
            # NLLB codes
            "zho_Hant": "target_zh_TW", "zho_Hans": "target_zh_CN",
            "eng_Latn": "target_en", "jpn_Jpan": "target_ja",
            "kor_Hang": "target_ko", "spa_Latn": "target_es",
            "fra_Latn": "target_fr", "deu_Latn": "target_de",
            # Old Chinese display names
            "繁體中文": "target_zh_TW", "繁体中文": "target_zh_TW",
            "簡體中文": "target_zh_CN", "简体中文": "target_zh_CN",
            "英文": "target_en", "English": "target_en",
            "日文": "target_ja", "Japanese": "target_ja",
            "韓文": "target_ko", "Korean": "target_ko",
            "西班牙文": "target_es", "Spanish": "target_es",
            "法文": "target_fr", "French": "target_fr",
            "德文": "target_de", "German": "target_de",
        }
        target_key = target_key_map.get(saved_target, "target_zh_TW")
        self.target_lang_var.set(t(target_key))


# Quick test
if __name__ == "__main__":
    def on_start(settings):
        print(f"Starting with settings: {settings}")
    
    app = SettingsWindow(on_start=on_start)
    app.mainloop()
