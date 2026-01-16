"""
ARIA - AI Realtime Intelligent Audio

A transparent floating window application that captures system audio
and generates real-time bilingual subtitles using AI.
"""

import os
# Disable tqdm progress bars early to avoid threading issues with HuggingFace downloads
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_TQDM"] = "1"
os.environ["TQDM_DISABLE"] = "1"

__version__ = "0.1.0"
__author__ = "sayksii"
