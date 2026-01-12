"""
Model Manager module - Handles model downloading and management.
"""

from .manager import (
    ModelManager,
    ModelInfo,
    ModelType,
    ModelStatus,
    SUPPORTED_MODELS,
)

__all__ = [
    "ModelManager",
    "ModelInfo",
    "ModelType",
    "ModelStatus",
    "SUPPORTED_MODELS",
]
