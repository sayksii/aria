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

## 📦 Download

### Choose Your Version

| Version | Size | Description | Download |
|---------|------|-------------|----------|
| **Lite** | ~6 GB | No models included. Download models in-app. | [Google Drive](https://drive.google.com/file/d/1hCrXqGmDe46bnF5dfyAIxSzVf6P8rTj5/view?usp=sharing) |
| **Full** | ~12 GB | All models pre-installed. Ready to use. | [Google Drive](https://drive.google.com/) |

### Included Models (Full Version)

| Model | Type | Size | Languages |
|-------|------|------|-----------|
| Whisper Large-v3 | Precise | 3 GB | All |
| Sherpa-ONNX Bilingual | Realtime | 500 MB | Chinese, English |
| Vosk Japanese | Realtime | 1 GB | Japanese |
| NLLB Translation | Translation | 1.2 GB | Many |

## 🚀 Quick Start

1. Download and extract the ZIP file
2. Double-click **`ARIA.vbs`** (silent) or **`ARIA.bat`** (with console)
3. If using Lite version, click **Manage Models** to download required models
4. Select recognition mode and language
5. Click **Start Subtitles**

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

## 📁 Package Structure

```
ARIA/
├── python/          # Embedded Python (no installation needed)
├── src/             # Source code
├── models/          # AI models (Lite: empty, Full: pre-installed)
├── ARIA.bat         # Launcher with console window
└── ARIA.vbs         # Silent launcher (recommended)
```

## 🛠️ For Developers

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

## 📝 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper)
- [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)
- [Vosk](https://alphacephei.com/vosk/)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)

## 📧 Contact

- GitHub: [@sayksii](https://github.com/sayksii)
- Email: mark42967151@gmail.com
