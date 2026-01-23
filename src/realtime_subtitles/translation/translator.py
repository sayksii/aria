"""
NLLB-200 Translator for real-time translation.

Uses CTranslate2 for efficient inference with NLLB-200 model.
Supports 200+ languages with high quality translation.
"""

import os
from pathlib import Path
from typing import Optional
import threading

from ..logger import info, debug, warning, error

# CTranslate2 imports with error handling
try:
    import ctranslate2
    from transformers import AutoTokenizer
    from huggingface_hub import snapshot_download
    CTRANSLATE2_AVAILABLE = True
    debug("CTranslate2 and transformers loaded successfully")
except ImportError as e:
    warning(f"Translator import failed: {e}")
    CTRANSLATE2_AVAILABLE = False

# Translators library import (multi-engine web scraper) - delayed to avoid conflicts
TRANSLATORS_AVAILABLE = False
try:
    import importlib.util
    if importlib.util.find_spec("translators") is not None:
        TRANSLATORS_AVAILABLE = True
        debug("translators library available (delayed import)")
except Exception as e:
    warning(f"translators check failed: {e}")


class NLLBTranslator:
    """
    NLLB-200 based translator using CTranslate2.
    
    Features:
    - 200+ language support with high quality
    - GPU acceleration (CUDA)
    - Efficient int8 quantization
    - Automatic model download
    """
    
    # Available models - aligned with ModelManager
    # Uses the same model as ModelManager for consistency
    MODELS = {
        "600m": {
            "repo": "JustFrederik/nllb-200-distilled-600M-ct2-int8",
            "name": "NLLB-200 600M (int8)",
            "local_folder": "nllb-200-distilled-600M-ct2-int8",
        },
    }
    
    # NLLB language codes (BCP-47 style)
    LANGUAGE_CODES = {
        # Display name -> NLLB code
        "繁體中文": "zho_Hant",
        "簡體中文": "zho_Hans", 
        "英文": "eng_Latn",
        "日文": "jpn_Jpan",
        "韓文": "kor_Hang",
        "西班牙文": "spa_Latn",
        "法文": "fra_Latn",
        "德文": "deu_Latn",
        "俄文": "rus_Cyrl",
        "阿拉伯文": "arb_Arab",
        "葡萄牙文": "por_Latn",
        "義大利文": "ita_Latn",
        "越南文": "vie_Latn",
        "泰文": "tha_Thai",
        "印尼文": "ind_Latn",
    }
    
    # Language code to detect source language
    SOURCE_LANG_MAP = {
        "zh": "zho_Hans",  # Chinese -> Simplified Chinese
        "ja": "jpn_Jpan",  # Japanese
        "en": "eng_Latn",  # English
        "ko": "kor_Hang",  # Korean
    }
    
    def __init__(
        self,
        model_size: str = "600m",
        target_language: str = "zho_Hant",
        device: str = "auto",
    ):
        """
        Initialize the NLLB translator.
        
        Args:
            model_size: Model size ("600m", "1.3b", or "3.3b")
            target_language: Target language code (NLLB format, e.g., "zho_Hant")
            device: Device to use ("auto", "cuda", "cpu")
        """
        if not CTRANSLATE2_AVAILABLE:
            raise ImportError(
                "CTranslate2 is required. Run: pip install ctranslate2 transformers huggingface_hub"
            )
        
        if model_size not in self.MODELS:
            raise ValueError(f"Unknown model: {model_size}. Available: {list(self.MODELS.keys())}")
        
        self.model_size = model_size
        self.target_language = target_language
        self._lock = threading.Lock()
        
        # Determine device
        if device == "auto":
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        self._device = device
        
        # Get model path
        model_info = self.MODELS[model_size]
        model_path = self._get_or_download_model(model_info)
        
        # Load model
        info(f"Loading NLLB {model_info['name']} on {device}...")
        
        self._translator = ctranslate2.Translator(
            str(model_path),
            device=device,
            compute_type="auto",
            inter_threads=1,
            intra_threads=4,
        )
        
        # Load tokenizer from original model (use project models dir for cache)
        debug("Loading NLLB tokenizer...")
        tokenizer_cache_dir = self._get_cache_dir() / "nllb-tokenizer"
        self._tokenizer = AutoTokenizer.from_pretrained(
            "facebook/nllb-200-distilled-600M",
            src_lang="jpn_Jpan",  # Default source
            cache_dir=str(tokenizer_cache_dir),
        )
        
        info(f"NLLB initialized: {model_info['name']}, target={target_language}")
    
    def _get_cache_dir(self) -> Path:
        """Get the model cache directory (project models folder)."""
        # Use project's models directory for consistency with ModelManager
        current = Path(__file__).resolve()
        # Go up: translator.py -> translation -> realtime_subtitles -> src -> project_root
        project_root = current.parent.parent.parent.parent
        cache_dir = project_root / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    
    def _get_or_download_model(self, model_info: dict) -> Path:
        """Get model path, checking if already downloaded by ModelManager."""
        cache_dir = self._get_cache_dir()
        
        # Use local_folder name (same as ModelManager) for consistency
        local_folder = model_info.get("local_folder")
        repo_id = model_info["repo"]
        
        if local_folder:
            model_path = cache_dir / local_folder
        else:
            # Fallback to repo name conversion
            model_path = cache_dir / repo_id.replace("/", "_")
        
        if model_path.exists() and (model_path / "model.bin").exists():
            debug(f"Using cached NLLB model: {model_path}")
            return model_path
        
        # Model not found - raise error to let user download via ModelManager
        raise FileNotFoundError(
            f"NLLB model not found at {model_path}. "
            f"Please download the model using the Model Manager first."
        )
    
    def translate(
        self,
        text: str,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ) -> str:
        """
        Translate text.
        
        Args:
            text: Text to translate
            source_language: Source language code (optional, e.g., "ja", "en")
            target_language: Target language code (overrides default, NLLB format)
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""
        
        target = target_language or self.target_language
        
        # Map simple language codes to NLLB format
        if source_language and source_language in self.SOURCE_LANG_MAP:
            src_lang = self.SOURCE_LANG_MAP[source_language]
        else:
            src_lang = "jpn_Jpan"  # Default to Japanese
        
        with self._lock:
            # Set source language for tokenizer (IMPORTANT for NLLB)
            self._tokenizer.src_lang = src_lang
            
            # Tokenize following official CTranslate2 NLLB example
            source = self._tokenizer.convert_ids_to_tokens(
                self._tokenizer.encode(text)
            )
            
            # Translate with target language prefix
            target_prefix = [target]  # Single list, not nested
            results = self._translator.translate_batch(
                [source],
                target_prefix=[target_prefix],
                beam_size=4,  # Higher beam for better quality
                max_decoding_length=256,
            )
            
            # Decode - skip first token (target language token)
            output_tokens = results[0].hypotheses[0][1:]  # Skip lang token
            
            translated = self._tokenizer.decode(
                self._tokenizer.convert_tokens_to_ids(output_tokens),
                skip_special_tokens=True,
            )
        
        return translated.strip()
    
    def set_target_language(self, language: str) -> None:
        """Set the target language (NLLB format)."""
        self.target_language = language
        debug(f"NLLB target language set to: {language}")
    
    @classmethod
    def get_language_code(cls, display_name: str) -> str:
        """Get NLLB language code from display name."""
        return cls.LANGUAGE_CODES.get(display_name, "eng_Latn")


# Keep old class for compatibility but redirect to NLLB
class MADLADTranslator(NLLBTranslator):
    """Alias for backward compatibility."""
    pass


# Google Translate support (using googletrans library)
try:
    from googletrans import Translator as GoogleTranslatorBase
    GOOGLETRANS_AVAILABLE = True
except ImportError:
    GOOGLETRANS_AVAILABLE = False
    GoogleTranslatorBase = None


class GoogleTranslator:
    """
    Google Translate wrapper using googletrans library.
    
    Features:
    - Free (unofficial API)
    - No model download required
    - High quality translation
    - Note: May be unstable due to rate limiting
    """
    
    # Language code mapping (display name -> googletrans code)
    LANGUAGE_CODES = {
        "繁體中文": "zh-tw",
        "簡體中文": "zh-cn",
        "英文": "en",
        "日文": "ja",
        "韓文": "ko",
        "西班牙文": "es",
        "法文": "fr",
        "德文": "de",
    }
    
    # Source language mapping
    SOURCE_LANG_MAP = {
        "zh": "zh-cn",
        "ja": "ja",
        "en": "en",
        "ko": "ko",
    }
    
    def __init__(self, target_language: str = "zh-tw"):
        """
        Initialize Google Translator.
        
        Args:
            target_language: Target language code (e.g., "zh-tw", "en")
        """
        if not GOOGLETRANS_AVAILABLE:
            raise ImportError("googletrans is required. Run: pip install googletrans==4.0.0-rc1")
        
        self._translator = GoogleTranslatorBase()
        self.target_language = target_language
        self._lock = threading.Lock()
        info(f"GoogleTranslator initialized with target={target_language}")
    
    def translate(
        self,
        text: str,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ) -> str:
        """
        Translate text using Google Translate.
        
        Args:
            text: Text to translate
            source_language: Source language code (optional)
            target_language: Target language code (overrides default)
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""
        
        target = target_language or self.target_language
        src = self.SOURCE_LANG_MAP.get(source_language, "auto") if source_language else "auto"
        
        with self._lock:
            try:
                result = self._translator.translate(text, src=src, dest=target)
                return result.text
            except Exception as e:
                warning(f"GoogleTranslator error: {e}")
                return ""
    
    def set_target_language(self, language: str) -> None:
        """Set the target language."""
        self.target_language = language
        debug(f"GoogleTranslator target language set to: {language}")
    
    @classmethod
    def get_language_code(cls, display_name: str) -> str:
        """Get Google Translate language code from display name."""
        return cls.LANGUAGE_CODES.get(display_name, "en")


class TranslatorsLibWrapper:
    """
    Wrapper for translators library (multi-engine web scraper).
    Supports Google, Baidu, Youdao, Bing, Alibaba, and more.
    
    Warning: This uses web scraping and may be unstable or blocked.
    """
    
    # Language code mapping (NLLB format -> translators format)
    # Different engines may use different codes
    LANGUAGE_CODES = {
        # Google and most engines
        "google": {
            "zho_Hant": "zh-TW",
            "zho_Hans": "zh-CN", 
            "eng_Latn": "en",
            "jpn_Jpan": "ja",
            "kor_Hang": "ko",
            "spa_Latn": "es",
            "fra_Latn": "fr",
            "deu_Latn": "de",
            "rus_Cyrl": "ru",
            "arb_Arab": "ar",
            "por_Latn": "pt",
            "ita_Latn": "it",
            "vie_Latn": "vi",
            "tha_Thai": "th",
            "ind_Latn": "id",
        },
        # Bing uses different codes
        "bing": {
            "zho_Hant": "zh-Hant",
            "zho_Hans": "zh-Hans", 
            "eng_Latn": "en",
            "jpn_Jpan": "ja",
            "kor_Hang": "ko",
            "spa_Latn": "es",
            "fra_Latn": "fr",
            "deu_Latn": "de",
            "rus_Cyrl": "ru",
            "arb_Arab": "ar",
            "por_Latn": "pt",
            "ita_Latn": "it",
            "vie_Latn": "vi",
            "tha_Thai": "th",
            "ind_Latn": "id",
        },
        # Youdao only supports Chinese-English translation
        "youdao": {
            "zho_Hant": "zh-CHS",  # Only simplified Chinese supported
            "zho_Hans": "zh-CHS", 
            "eng_Latn": "en",
            "jpn_Jpan": "en",  # Other languages fallback to English
            "kor_Hang": "en",
            "spa_Latn": "en",
            "fra_Latn": "en",
            "deu_Latn": "en",
            "rus_Cyrl": "en",
            "arb_Arab": "en",
            "por_Latn": "en",
            "ita_Latn": "en",
            "vie_Latn": "en",
            "tha_Thai": "en",
            "ind_Latn": "en",
        },
    }
    
    # Supported engines
    ENGINES = {
        "google": "Google (Free)",
        "bing": "Bing",
        "youdao": "有道翻譯 (中英互譯)",
    }
    
    def __init__(
        self,
        engine: str = "google",
        target_language: str = "zho_Hant",
    ):
        """
        Initialize translators library wrapper.
        
        Args:
            engine: Engine name ("google", "baidu", "youdao", "bing", "alibaba")
            target_language: Target language code (NLLB format)
        """
        if not TRANSLATORS_AVAILABLE:
            raise ImportError(
                "translators library is required. Run: pip install translators"
            )
        
        self.engine = engine
        # Get language code based on engine
        lang_map = self.LANGUAGE_CODES.get(engine, self.LANGUAGE_CODES["google"])
        self.target_language = lang_map.get(target_language, "zh-TW")
        self._lock = threading.Lock()
        
        info(f"TranslatorsLib initialized: engine={engine}, target={self.target_language}")
    
    def translate(
        self,
        text: str,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ) -> str:
        """
        Translate text using selected engine.
        
        Args:
            text: Text to translate
            source_language: Source language code (optional, auto-detect)
            target_language: Target language code (overrides default)
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""
        
        target = target_language or self.target_language
        
        # Lazy import translators to avoid conflicts
        import translators as ts
        
        with self._lock:
            try:
                # Map engine name to translators library function
                if self.engine == "google":
                    result = ts.translate_text(text, to_language=target, translator='google')
                elif self.engine == "bing":
                    result = ts.translate_text(text, to_language=target, translator='bing')
                elif self.engine == "youdao":
                    result = ts.translate_text(text, to_language=target, translator='youdao')
                else:
                    warning(f"Unknown engine: {self.engine}, falling back to Google")
                    result = ts.translate_text(text, to_language=target, translator='google')
                
                return result
            except Exception as e:
                warning(f"TranslatorsLib ({self.engine}) error: {e}")
                return ""
    
    def set_target_language(self, language: str) -> None:
        """Set the target language."""
        lang_map = self.LANGUAGE_CODES.get(self.engine, self.LANGUAGE_CODES["google"])
        self.target_language = lang_map.get(language, language)
        debug(f"TranslatorsLib target language set to: {self.target_language}")
    
    @classmethod
    def get_language_code(cls, nllb_code: str, engine: str = "google") -> str:
        """Get translators language code from NLLB code."""
        lang_map = cls.LANGUAGE_CODES.get(engine, cls.LANGUAGE_CODES["google"])
        return lang_map.get(nllb_code, "en")


def create_translator(
    engine: str = "nllb",
    target_language: str = "zho_Hant",
    **kwargs
):
    """
    Factory function to create a translator instance.
    
    Args:
        engine: "nllb" (local) or translators engines ("google_free", "bing", "youdao")
        target_language: Target language code (NLLB format like "zho_Hant")
        **kwargs: Additional arguments for specific translator
    
    Returns:
        Translator instance (NLLBTranslator or TranslatorsLibWrapper)
    """
    
    # Handle translators library engines
    if engine in ["google_free", "bing", "youdao", "google"]:  # "google" for legacy support
        if not TRANSLATORS_AVAILABLE:
            raise ImportError("translators library not available. Install: pip install translators")
        # Map engine names
        engine_map = {
            "google": "google",  # Legacy support
            "google_free": "google",
            "bing": "bing",
            "youdao": "youdao",
        }
        ts_engine = engine_map.get(engine, "google")
        return TranslatorsLibWrapper(engine=ts_engine, target_language=target_language)
    
    # Handle NLLB (local)
    else:  # nllb
        if not CTRANSLATE2_AVAILABLE:
            raise ImportError("CTranslate2 not available. Install: pip install ctranslate2")
        return NLLBTranslator(target_language=target_language, **kwargs)


# Quick test
if __name__ == "__main__":
    print("Testing Translators...")
    
    # Test NLLB
    if CTRANSLATE2_AVAILABLE:
        try:
            translator = NLLBTranslator(model_size="1.3b", target_language="zho_Hant")
            result = translator.translate("Hello, how are you today?", source_language="en")
            print(f"NLLB EN -> ZH: {result}")
        except Exception as e:
            print(f"NLLB Error: {e}")
    
    # Test Google
    if GOOGLETRANS_AVAILABLE:
        try:
            translator = GoogleTranslator(target_language="zh-tw")
            result = translator.translate("Hello, how are you today?", source_language="en")
            print(f"Google EN -> ZH: {result}")
        except Exception as e:
            print(f"Google Error: {e}")
