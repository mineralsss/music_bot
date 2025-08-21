# Discord Music Bot

A Discord music bot that can play audio from YouTube with queue management and voice connection handling.

## Features

- 🎵 Play music from YouTube URLs or search terms
- 📋 Queue management with skip, pause, resume commands
- 🔄 Automatic reconnection and error recovery
- 🎛️ Volume control and fade effects
- 🚫 Auto-disconnect when alone in voice channel

## Commands

- `?play <song name or URL>` - Play a song or add to queue
- `?pause` - Pause current playback
- `?resume` - Resume paused playback
- `?skip` - Skip current song with fade effect
- `?stop` - Stop playback and clear queue
- `?queue` - Show current queue

## Setup

1. Clone this repository
2. Install required dependencies:
   ```bash
   pip install discord.py yt-dlp python-dotenv youtubesearchpython
   ```
3. Create a `.env` file with your Discord bot token:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```
4. Run the bot:
   ```bash
   python main.py
   ```

## Requirements

- Python 3.8+
- FFmpeg (for audio processing)
- Discord bot token

## Enhanced Features

- **Robust Voice Connections**: Advanced error handling for Discord WebSocket errors (4006)
- **Multiple YouTube Extractors**: Fallback methods for YouTube audio extraction
- **Health Monitoring**: Automatic voice connection health checks
- **Session Recovery**: Automatic reconnection with exponential backoff

## Error Handling

The bot includes comprehensive error handling for:
- Discord WebSocket connection issues (Error 4006)
- YouTube extraction failures
- Voice connection problems
- Network connectivity issues
