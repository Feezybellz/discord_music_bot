# Setup & Installation Guide

This guide will help you set up the Python Discord Music Bot and configure the environment variables correctly.

## 1. Prerequisites
- **Python 3.10+**: Ensure Python is installed on your system.
- **FFmpeg**: This is **REQUIRED** for audio processing.
- **Libsodium & Opus**: Required for Discord voice encryption and encoding.

### System-Level Dependencies (Linux/Ubuntu)
Run the following commands to ensure all necessary libraries are installed:
```bash
sudo apt update
sudo apt install ffmpeg libffi-dev libsodium-dev libopus0
```

### Checking for FFmpeg
Before proceeding, verify FFmpeg is installed:
```bash
ffmpeg -version
```

## 2. Discord Bot Setup (Crucial Steps)
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a **New Application**.
3. Navigate to the **Bot** tab on the left:
   - Click **Reset Token** to get your **Bot Token**.
   - Scroll down to **Privileged Gateway Intents** and **ENABLE ALL THREE**:
     - `Presence Intent`
     - `Server Members Intent`
     - `Message Content Intent`
4. Navigate to **OAuth2 -> URL Generator**:
   - **Step 1: Scopes** - You **MUST** check both of these:
     - `bot`
     - `applications.commands`
   - **Step 2: Bot Permissions** - Once you check `bot`, a new section will appear below. **SCROLL DOWN** and check:
     - `Administrator` (Recommended for full access)
     - OR specifically: `Connect`, `Speak`, `View Channels`, `Send Messages`, `Embed Links`.
5. **Copy the generated URL** at the bottom, paste it into your browser, and invite the bot to your server.

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
   pip install davey
   ```

## 4. Environment Configuration
1. Open the `.env` file in the root directory.
2. Replace the placeholders with your actual settings:
   ```env
   DISCORD_TOKEN=your_token_here_abc123
   DEBUG_MODE=true
   ```

## 5. Running the Bot
```bash
python3 main.py
```

### Note on Command Prefix
The bot uses modern **Slash Commands**. After starting the bot, it may take a few minutes for Discord to register the new commands. Look for the `/musicbot` command group in your server.
