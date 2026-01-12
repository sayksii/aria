"""
Model Manager - Handles model downloading and status checking.
"""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Dict, List
import threading


class ModelType(Enum):
    """Types of models supported."""
    WHISPER = "whisper"
    SHERPA = "sherpa"
    VOSK = "vosk"
    NLLB = "nllb"


class ModelStatus(Enum):
    """Download status of a model."""
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    ERROR = "error"


@dataclass
class ModelInfo:
    """Information about a model."""
    id: str
    name: str
    model_type: ModelType
    size_mb: int
    description: str
    # Download source
    hf_repo: Optional[str] = None  # Hugging Face repo ID
    download_url: Optional[str] = None  # Direct download URL
    # Local paths
    local_folder: Optional[str] = None  # Folder name in models directory
    
    def get_size_display(self) -> str:
        """Get human-readable size string."""
        if self.size_mb >= 1024:
            return f"{self.size_mb / 1024:.1f}GB"
        return f"{self.size_mb}MB"


# Registry of all supported models
SUPPORTED_MODELS: List[ModelInfo] = [
    # Whisper models (via faster-whisper / CTranslate2)
    ModelInfo(
        id="whisper-large-v3",
        name="Whisper Large-v3",
        model_type=ModelType.WHISPER,
        size_mb=3000,
        description="最高準確度，適合精準模式",
        hf_repo="Systran/faster-whisper-large-v3",
        local_folder="faster-whisper-large-v3",
    ),
    ModelInfo(
        id="whisper-large-v3-turbo",
        name="Whisper Large-v3 Turbo",
        model_type=ModelType.WHISPER,
        size_mb=1500,
        description="快速且準確",
        hf_repo="deepdml/faster-whisper-large-v3-turbo-ct2",
        local_folder="faster-whisper-large-v3-turbo-ct2",
    ),
    ModelInfo(
        id="whisper-medium",
        name="Whisper Medium",
        model_type=ModelType.WHISPER,
        size_mb=1500,
        description="中等大小，平衡效能與準確度",
        hf_repo="Systran/faster-whisper-medium",
        local_folder="faster-whisper-medium",
    ),
    # Sherpa-ONNX models
    ModelInfo(
        id="sherpa-onnx-streaming-paraformer-zh",
        name="Sherpa 中/英文",
        model_type=ModelType.SHERPA,
        size_mb=500,
        description="實時中英文辨識",
        download_url="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2",
        local_folder="sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20",
    ),
    # Vosk models
    ModelInfo(
        id="vosk-model-ja",
        name="Vosk 日文",
        model_type=ModelType.VOSK,
        size_mb=1000,
        description="實時日文辨識",
        download_url="https://alphacephei.com/vosk/models/vosk-model-ja-0.22.zip",
        local_folder="vosk-model-ja-0.22",
    ),
    # NLLB translation model
    ModelInfo(
        id="nllb-200-distilled-600M",
        name="NLLB 翻譯模型",
        model_type=ModelType.NLLB,
        size_mb=600,
        description="離線多語言翻譯 (600M 版本)",
        hf_repo="JustFrederik/nllb-200-distilled-600M-ct2-int8",
        local_folder="nllb-200-distilled-600M-ct2-int8",
    ),
]


class ModelManager:
    """Manages model downloading and status."""
    
    def __init__(self, models_dir: Optional[Path] = None):
        """
        Initialize the model manager.
        
        Args:
            models_dir: Directory to store models. If None, uses default cache locations.
        """
        self.models_dir = models_dir or self._get_default_models_dir()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Download state
        self._download_progress: Dict[str, float] = {}
        self._download_threads: Dict[str, threading.Thread] = {}
        self._download_callbacks: Dict[str, Callable[[str, float, str], None]] = {}
    
    @staticmethod
    def _get_default_models_dir() -> Path:
        """Get the default models directory (project directory)."""
        # Use project directory for portability
        # Find the project root by looking for src directory
        current = Path(__file__).resolve()
        # Go up from model_manager/manager.py -> model_manager -> realtime_subtitles -> src -> project_root
        project_root = current.parent.parent.parent.parent
        return project_root / "models"
    
    def get_model_path(self, model: ModelInfo) -> Path:
        """Get the local path for a model."""
        if model.local_folder:
            return self.models_dir / model.local_folder
        return self.models_dir / model.id
    
    def get_status(self, model: ModelInfo) -> ModelStatus:
        """Check if a model is downloaded."""
        model_path = self.get_model_path(model)
        
        # Check if downloading
        if model.id in self._download_threads:
            thread = self._download_threads[model.id]
            if thread.is_alive():
                return ModelStatus.DOWNLOADING
        
        # Check if downloaded
        if model_path.exists():
            # For Hugging Face models, check for model files
            if model.hf_repo:
                if any(model_path.glob("*.bin")) or any(model_path.glob("*.safetensors")):
                    return ModelStatus.DOWNLOADED
            # For downloaded archives, check if extracted
            elif model.download_url:
                if model_path.is_dir() and any(model_path.iterdir()):
                    return ModelStatus.DOWNLOADED
        
        return ModelStatus.NOT_DOWNLOADED
    
    def get_progress(self, model: ModelInfo) -> float:
        """Get download progress (0.0 to 1.0)."""
        return self._download_progress.get(model.id, 0.0)
    
    def download(
        self,
        model: ModelInfo,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> None:
        """
        Start downloading a model in background.
        
        Args:
            model: Model to download
            progress_callback: Callback(model_id, progress, status_text)
        """
        if self.get_status(model) == ModelStatus.DOWNLOADING:
            return
        
        if progress_callback:
            self._download_callbacks[model.id] = progress_callback
        
        thread = threading.Thread(
            target=self._download_model,
            args=(model,),
            daemon=True,
        )
        self._download_threads[model.id] = thread
        self._download_progress[model.id] = 0.0
        thread.start()
    
    def _download_model(self, model: ModelInfo) -> None:
        """Download a model (runs in background thread)."""
        try:
            callback = self._download_callbacks.get(model.id)
            
            if model.hf_repo:
                self._download_from_huggingface(model, callback)
            elif model.download_url:
                self._download_from_url(model, callback)
            
            self._download_progress[model.id] = 1.0
            if callback:
                callback(model.id, 1.0, "完成")
        except Exception as e:
            print(f"[ModelManager] Download error: {e}")
            if callback:
                callback(model.id, -1, f"錯誤: {e}")
        finally:
            if model.id in self._download_threads:
                del self._download_threads[model.id]
    
    def _download_from_huggingface(
        self,
        model: ModelInfo,
        callback: Optional[Callable[[str, float, str], None]],
    ) -> None:
        """Download model from Hugging Face Hub."""
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            raise RuntimeError("請安裝 huggingface_hub: pip install huggingface_hub")
        
        model_path = self.get_model_path(model)
        
        if callback:
            callback(model.id, 0.1, f"正在下載 {model.name}...")
        
        # Disable tqdm progress bars to avoid threading issues
        import os
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        
        snapshot_download(
            repo_id=model.hf_repo,
            local_dir=str(model_path),
            local_dir_use_symlinks=False,
            cache_dir=str(model_path),
        )
        
        if callback:
            callback(model.id, 0.9, "驗證中...")
    
    def _download_from_url(
        self,
        model: ModelInfo,
        callback: Optional[Callable[[str, float, str], None]],
    ) -> None:
        """Download model from direct URL."""
        import urllib.request
        import tempfile
        import zipfile
        import tarfile
        
        model_path = self.get_model_path(model)
        url = model.download_url
        
        if callback:
            callback(model.id, 0.05, f"正在下載 {model.name}...")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=self._get_archive_suffix(url)) as tmp:
            tmp_path = tmp.name
            
            def report_progress(block_num, block_size, total_size):
                if total_size > 0:
                    progress = min(0.8, block_num * block_size / total_size * 0.8)
                    self._download_progress[model.id] = progress
                    if callback:
                        downloaded_mb = block_num * block_size / 1024 / 1024
                        total_mb = total_size / 1024 / 1024
                        callback(model.id, progress, f"下載中... {downloaded_mb:.0f}/{total_mb:.0f}MB")
            
            urllib.request.urlretrieve(url, tmp_path, report_progress)
        
        if callback:
            callback(model.id, 0.85, "解壓縮中...")
        
        model_path.mkdir(parents=True, exist_ok=True)
        
        if url.endswith(".zip"):
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                zf.extractall(model_path.parent)
        elif url.endswith(".tar.bz2") or url.endswith(".tar.gz"):
            with tarfile.open(tmp_path, 'r:*') as tf:
                tf.extractall(model_path.parent)
        
        os.unlink(tmp_path)
    
    @staticmethod
    def _get_archive_suffix(url: str) -> str:
        """Get archive suffix from URL."""
        if ".tar.bz2" in url:
            return ".tar.bz2"
        elif ".tar.gz" in url:
            return ".tar.gz"
        elif ".zip" in url:
            return ".zip"
        return ""
    
    def delete(self, model: ModelInfo) -> bool:
        """Delete a downloaded model."""
        import shutil
        
        model_path = self.get_model_path(model)
        if model_path.exists():
            try:
                shutil.rmtree(model_path)
                return True
            except Exception as e:
                print(f"[ModelManager] Delete error: {e}")
        return False
    
    def get_all_models(self) -> List[ModelInfo]:
        """Get list of all supported models."""
        return SUPPORTED_MODELS.copy()
    
    def get_models_by_type(self, model_type: ModelType) -> List[ModelInfo]:
        """Get models of a specific type."""
        return [m for m in SUPPORTED_MODELS if m.model_type == model_type]
