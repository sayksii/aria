# ARIA

<p align="center">
  <strong>AI Realtime Intelligent Audio</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey.svg" alt="Windows">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
</p>

**Universal Real-time AI Subtitles for Windows** - Capture and transcribe any audio playing on your system with AI-powered speech recognition.

## ✨ Features

- 🎯 **Universal Audio Capture** - Works with any application (games, videos, calls, etc.)
- 🚀 **Two Recognition Modes**:
  - **Precise Mode**: Uses Whisper for high-accuracy transcription
  - **Realtime Mode**: Uses Sherpa-ONNX/Vosk for word-by-word streaming
- 🌍 **Multi-language Support**: Chinese, English, Japanese, Korean, and more
- 🔄 **Real-time Translation**: Translate transcriptions with Google Cloud or NLLB (local)
- 🎨 **Customizable Overlay**: Draggable subtitle window with adjustable position
- 🌐 **Multilingual UI**: English, Traditional Chinese, Simplified Chinese

## 📦 Quick Start (Recommended)

### Download Pre-built Release

1. Go to [Releases](https://github.com/sayksii/aria/releases)
2. Download the latest `ARIA-vX.X.X-windows.zip`
3. Extract to any folder
4. Double-click **`ARIA.vbs`** (silent) or **`ARIA.bat`** (with console)

> **Note**: First launch will download AI models (~500MB-1.5GB depending on features used).

### First Time Setup

1. Launch ARIA
2. Click **Manage Models** to download required models
3. Select recognition mode (Precise or Realtime)
4. Choose the language you want to recognize
5. Click **Start Subtitles**

## 🛠️ Development Installation

For developers who want to modify the source code:

```bash
# Clone the repository
git clone https://github.com/sayksii/aria.git
cd aria

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install the package
pip install -e .

# Run
python -m realtime_subtitles.ui.app
```

## ⚙️ Configuration

### Recognition Modes

| Mode | Engine | Best For |
|------|--------|----------|
| **Precise** | Whisper | Speeches, videos, pre-recorded content |
| **Realtime** | Sherpa-ONNX / Vosk | Live conversations, streaming |

### Supported Languages

| Language | Precise Mode | Realtime Mode |
|----------|--------------|---------------|
| Chinese (中文) | ✅ | ✅ (Sherpa-ONNX) |
| English | ✅ | ✅ (Sherpa-ONNX) |
| Japanese (日本語) | ✅ | ✅ (Vosk) |
| Korean (한국어) | ✅ | ❌ |
| + 50 more | ✅ | ❌ |

### Translation

- **Google Cloud**: Fast, accurate, requires internet
- **NLLB Local**: Offline, runs locally using Meta's NLLB model

## 📁 Release Package Structure

```
ARIA/
├── python/          # Embedded Python (no installation needed)
├── src/             # Source code
├── models/          # AI models (downloaded on first use)
├── ARIA.bat         # Launcher with console window
└── ARIA.vbs         # Silent launcher (recommended)
```

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper)
- [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)
- [Vosk](https://alphacephei.com/vosk/)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)

## 📧 Contact

- GitHub: [@sayksii](https://github.com/sayksii)
- Email: mark42967151@gmail.com
