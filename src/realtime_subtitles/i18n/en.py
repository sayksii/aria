# English

TRANSLATIONS = {
    # Window title
    "window_title": "ARIA",
    "subtitle": "Real-time Speech-to-Text Tool",
    
    # Language selector
    "language": "Language",
    "lang_zh_TW": "繁體中文",
    "lang_zh_CN": "简体中文",
    "lang_en": "English",
    
    # Recognition settings
    "recognition_settings": "Recognition",
    "mode_precise": "Precise",
    "mode_realtime": "Realtime",
    "mode_precise_desc": "Wait for complete sentences, suitable for speeches and videos",
    "mode_realtime_desc": "Word-by-word display, Sherpa (CN/EN) / Vosk (JP)",
    
    # Translation settings
    "translation_settings": "Translation",
    "translation": "Translate",
    "engine": "Engine",
    "target_lang": "Target",
    "engine_google": "Google Cloud",
    "engine_nllb": "NLLB Local",
    
    # Model settings
    "model_settings": "Model Settings",
    "model": "Model",
    "lang": "Language",
    "manage_models": "📦 Manage Models",
    
    # VAD settings
    "vad_settings": "Voice Detection",
    "vad_label": "VAD (Voice Activity Detection)",
    "vad_on": "ON",
    "vad_off": "OFF",
    "vad_desc_precise": "Auto sentence splitting, enable when audio is clear",
    "vad_desc_realtime": "Realtime mode uses built-in endpoint detection",
    "silence_threshold": "Silence Threshold",
    "min_duration": "Min Duration",
    
    # Start button
    "start_button": "🚀 Start Subtitles",
    "stop_button": "⏹ Stop Subtitles",
    "loading": "🔄 Loading...",
    
    # Status
    "status_ready": "Ready",
    "status_running": "Recognizing...",
    "status_loading_model": "Loading model (may take a while first time)...",
    
    # Footer
    "footer": "Supports any system audio",
    
    # Model manager
    "model_manager_title": "Model Manager",
    "model_path": "Location",
    "open_folder": "📂 Open",
    "recognition_models": "🎙️ Speech Recognition Models",
    "realtime_models": "⚡ Realtime Recognition Models",
    "translation_models": "🌐 Translation Models",
    "download": "Download",
    "delete": "Delete",
    "downloading": "Downloading...",
    "retry": "Retry",
    "complete": "Complete",
    
    # Download dialog
    "download_title": "Download Model",
    "downloading_models": "📥 Downloading models...",
    "download_in_progress": "Download in Progress",
    "download_cancel_confirm": "Cancelling will delete the partial download and close ARIA.\n\nAre you sure you want to cancel?",
    
    # Model not downloaded dialog
    "model_not_downloaded_title": "Model Not Downloaded",
    "model_not_downloaded_msg": "The following models are not downloaded:\n\n{models}\n\nDownload now?",
    
    # Overlay
    "overlay_waiting": "Subtitles started, waiting for audio...",
    "overlay_translation_waiting": "Waiting for translation...",
    
    # Languages
    "auto_detect": "Auto Detect",
    "lang_chinese": "Chinese (Trad/Simp)",
    "lang_english": "English",
    "lang_japanese": "Japanese",
    "lang_korean": "Korean",
    "lang_cantonese": "Cantonese",
    "lang_spanish": "Spanish",
    "lang_french": "French",
    "lang_german": "German",
    
    # Target languages
    "target_zh_TW": "Traditional Chinese",
    "target_zh_CN": "Simplified Chinese",
    "target_en": "English",
    "target_ja": "Japanese",
    "target_ko": "Korean",
    "target_es": "Spanish",
    "target_fr": "French",
    "target_de": "German",
    
    # Translation engines
    "engine_google_free": "Google",
    "engine_baidu": "Baidu Translate",
    "engine_youdao": "Youdao (CN↔EN only)",
    "engine_bing": "Bing",
    "engine_alibaba": "Alibaba Translate",
    "translation_disclaimer": "",
    
    # Misc
    "yes": "Yes",
    "no": "No",
    "restart_required": "Language change will take effect after restart",
    "already_running": "ARIA is already running.",
    "reset_settings": "Reset Settings",
    "quit_app": "Quit",
    "reset_settings_confirm": "This will reset all settings including overlay positions.\nARIA will restart. Continue?",
    "reset_settings_desc": "Fix can't see overlay or restore defaults",
    
    # Tray notifications
    "tray_minimized_title": "Minimized to system tray",
    "tray_minimized_msg": "Right-click the tray icon to control subtitles or quit",
    
    # Model names (for dropdown)
    "model_large_v3": "Large-v3 ⭐ (Best)",
    "model_large_v3_turbo": "Large-v3-turbo (Fast & Accurate)",
    "model_medium": "Medium (Balanced)",
    
    # Model manager - model names
    "model_name_whisper_large_v3": "Whisper Large-v3",
    "model_name_whisper_large_v3_turbo": "Whisper Large-v3 Turbo",
    "model_name_whisper_medium": "Whisper Medium",
    "model_name_sherpa_zh_en": "Sherpa Chinese/English",
    "model_name_vosk_ja": "Vosk Japanese",
    "model_name_nllb": "NLLB Translation",
    
    # Model manager - descriptions
    "model_desc_whisper_large_v3": "Highest accuracy, recommended for precise mode",
    "model_desc_whisper_large_v3_turbo": "Fast and accurate",
    "model_desc_whisper_medium": "Medium size, balanced performance and accuracy",
    "model_desc_sherpa_zh_en": "Real-time Chinese/English recognition",
    "model_desc_vosk_ja": "Real-time Japanese recognition",
    "model_desc_nllb": "Offline multilingual translation (600M)",
    
    # Download status messages
    "download_status_downloading": "Downloading {name}...",
    "download_status_verifying": "Verifying...",
    "download_status_extracting": "Extracting...",
    "download_status_complete": "Complete",
    "download_status_error": "Error: {error}",
    "download_status_progress": "Downloading... {downloaded}/{total}MB",
    "download_status_install_hf": "Please install huggingface_hub: pip install huggingface_hub",
    "cancel_download": "Cancel Download",
    "download_waiting": "Waiting to download...",
    "download_progress_note": "Progress may be inaccurate and can jump based on network",
}
