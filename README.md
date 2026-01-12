# ARIA

<p align="center">
  <strong>AI Realtime Intelligent Audio</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
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

## 📦 Installation

### Prerequisites
- Python 3.10 or higher
- Windows 10/11

### Install from source

```bash
# Clone the repository
git clone https://github.com/sayksii/aria.git
cd aria

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install the package
pip install -e .
```

## 🚀 Usage

### Launch the GUI

```bash
python -m realtime_subtitles.ui.app
```

Or after installation:
```bash
aria
```

### Quick Start

1. Launch ARIA
2. Select recognition mode (Precise or Realtime)
3. Choose the language you want to recognize
4. Click **Start Subtitles**
5. Drag the subtitle overlay to your preferred position

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

## 🏗️ Project Structure

```
aria/
├── src/realtime_subtitles/
│   ├── audio/          # Audio capture (WASAPI loopback)
│   ├── recognition/    # Speech recognition engines
│   ├── translation/    # Translation engines
│   ├── i18n/           # Internationalization
│   └── ui/             # GUI components
├── models/             # Downloaded AI models (gitignored)
└── pyproject.toml
```

## 🔧 Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint code
ruff check src/
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) - Fast Whisper inference
- [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx) - Streaming speech recognition
- [Vosk](https://alphacephei.com/vosk/) - Offline speech recognition
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI framework

## 📧 Contact

- GitHub: [@sayksii](https://github.com/sayksii)
- Email: mark42967151@gmail.com
