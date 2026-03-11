# Bot Usage Guide

Once the bot is running and invited to your server, you can use the following Slash Commands.

## Basic Commands
- `/play [search or url]`: Joins your voice channel and plays a song from YouTube, Spotify, SoundCloud, etc.
- `/pause`: Pauses the current track.
- `/resume`: Resumes a paused track.
- `/skip`: Skips the current song and plays the next one in the queue.
- `/stop`: Stops playback, clears the queue, and disconnects the bot.
- `/queue`: Displays the next 10 songs currently in the queue.

## Looping Features
The bot supports advanced looping modes via the `/loop` command:
- **/loop Off**: Disables looping (default).
- **/loop Track**: Repeats the currently playing song indefinitely.
- **/loop Queue**: When a song finishes, it is added back to the end of the queue, creating a continuous loop of your playlist.

## Troubleshooting
- **No Audio?** Ensure `ffmpeg` is installed and accessible in your system's PATH.
- **Commands not appearing?** It may take a few minutes for Discord to globalize Slash Commands, or you may need to restart your Discord client.
- **Bot won't join?** Ensure the bot has `Connect` and `Speak` permissions for your voice channel.
