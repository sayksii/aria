"""ARIA - Main entry point."""

Run with: python -m realtime_subtitles.main
"""

import sys
import time
import argparse
from typing import Optional

from .pipeline import RealtimePipeline, SubtitleEvent


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ARIA - Universal system audio transcription"
    )
    parser.add_argument(
        "-m", "--model",
        choices=[
            "tiny", "base", "small", "medium", "large-v3",
            "large-v3-turbo",  # 2024 turbo model
            "distil-large-v3", "distil-medium.en", "distil-small.en",
        ],
        default="base",
        help="Whisper model size (default: base). Use 'large-v3-turbo' for best speed/accuracy."
    )
    parser.add_argument(
        "-l", "--language",
        default=None,
        help="Language code (e.g., en, zh, ja). Leave empty for auto-detect."
    )
    parser.add_argument(
        "--vad/--no-vad",
        dest="use_vad",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Enable/disable Voice Activity Detection (default: enabled)"
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=1.0,
        help="Minimum speech duration before transcribing (seconds, default: 1.0)"
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=10.0,
        help="Maximum speech duration before forcing transcription (seconds, default: 10.0)"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print("=" * 60)
    print("ARIA - AI Realtime Intelligent Audio")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Language: {args.language or 'auto-detect'}")
    print(f"VAD: {'enabled' if args.use_vad else 'disabled'}")
    print(f"Duration: {args.min_duration}s - {args.max_duration}s")
    print("=" * 60)
    print("\nListening for audio... Press Ctrl+C to stop.\n")
    
    # Subtitle callback with RTF display
    def on_subtitle(event: SubtitleEvent):
        print(f"[{event.language}] {event.text}")
    
    # Create and run pipeline
    pipeline = RealtimePipeline(
        model=args.model,
        language=args.language,
        on_subtitle=on_subtitle,
        use_vad=args.use_vad,
        min_segment_duration=args.min_duration,
        max_segment_duration=args.max_duration,
    )
    
    try:
        pipeline.start()
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()

