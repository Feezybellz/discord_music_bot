# Setup & Installation Guide

This guide will help you set up the Python Discord Music Bot and configure the environment variables correctly.

## 1. Prerequisites
- **Python 3.10+**: Ensure Python is installed on your system.
- **FFmpeg**: This is **REQUIRED** for audio processing.

### Checking for FFmpeg
Before installing, check if you already have it:
```bash
ffmpeg -version
```
If you see an error like "command not found", follow the installation steps below:

### Installing FFmpeg
- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt update && sudo apt install ffmpeg
  ```
- **macOS (Homebrew):**
  ```bash
  brew install ffmpeg
  ```
- **Windows:**
  1. Download the "essentials" build from [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/).
  2. Extract the ZIP file.
  3. Move the folder to `C:\ffmpeg`.
  4. Add `C:\ffmpeg\bin` to your **System Environment Variables (PATH)**.
  5. Restart your terminal.

## 2. Discord Bot Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a **New Application**.
3. Navigate to the **Bot** tab:
   - Click **Reset Token** to get your **Bot Token**.
   - **Important:** Scroll down to **Privileged Gateway Intents** and enable:
     - `Presence Intent`
     - `Server Members Intent`
     - `Message Content Intent`
4. Navigate to **OAuth2 -> URL Generator**:
   - Select `bot` and `applications.commands` scopes.
   - Select `Administrator` or specific voice/message permissions.
   - Use the generated URL to invite the bot to your server.

## 3. Installation
1. **Clone or navigate to the project directory:**
   ```bash
   cd music_bot
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 4. Environment Configuration
1. Open the `.env` file in the root directory.
2. Replace the placeholder with your actual Discord Token:
   ```env
   DISCORD_TOKEN=your_token_here_abc123
   ```

## 5. Running the Bot
```bash
python3 main.py
```
