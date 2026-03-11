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

## 2. YouTube Authentication (Fixing "Sign in" Errors)

YouTube is extremely aggressive against bots. To bypass this, you **MUST** use a PO Token.

### Generating a PO Token

1. Install the generator globally (requires Node.js):
   ```bash
   npm install -g youtube-po-token-generator
   ```
2. Run the generator:
   ```bash
   youtube-po-token-generator
   ```
3. Copy the `visitorData` and `poToken` values.
4. Add them to your `.env` file (see Section 5).

## 3. Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a **New Application**.
3. In the **Bot** tab:
   - Reset Token to get your **Bot Token**.
   - Enable **ALL THREE** Privileged Gateway Intents (Presence, Server Members, Message Content).
4. In **OAuth2 -> URL Generator**:
   - Check `bot` and `applications.commands`.
   - **Step 2: Bot Permissions** - Once you check `bot`, a new section will appear below. **SCROLL DOWN** and check:
     - `Administrator` (Recommended for the easiest setup)
     - **OR** manually select these essential permissions:
       - `View Channels` (General)
       - `Send Messages` (Text)
       - `Embed Links` (Text)
       - `Connect` (Voice)
       - `Speak` (Voice)
       - `Use Slash Commands` (Text)
5. Invite the bot using the generated link.

## 4. Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install davey
```

## 5. Environment Configuration

Create a `.env` file in the root folder:

```env
DISCORD_TOKEN=your_bot_token
DEBUG_MODE=true
PO_TOKEN=paste_your_poToken_here
VISITOR_DATA=paste_your_visitorData_here
PROXY_URL=http://user:pass@host:port (Optional: For bypassing IP blocks)
COOKIE_PATH=/path/to/your/cookie.txt (Optional: Defaults to cookie.txt in bot folder)
```

get proxy from

https://dashboard.webshare.io/

## 6. Commands Reference

- `/musicbot play [url]`: Stop everything and play this song **now**.
- `/musicbot queue add [url]`: Add a song/playlist to the end of the queue.
- `/musicbot queue list`: View the current queue.
- `/musicbot stop`: Stop music and disconnect.
- `/musicbot status`: Check bot permissions.
- `/musicbot check`: Verify if the bot can see your cookies and PO token.
