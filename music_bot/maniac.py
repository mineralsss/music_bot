import discord
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
from youtubesearchpython import VideosSearch  # Add this import

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.guilds = True
    
    # Enhanced client configuration for better stability
    client = discord.Client(
        intents=intents,
        heartbeat_timeout=60.0,  # Increase heartbeat timeout
        max_messages=1000,       # Limit message cache
        chunk_guilds_at_startup=False  # Reduce startup load
    )

    # Enhanced voice connection with better error handling
    async def connect_to_voice_with_retry(channel, max_retries=3):
        """Connect to voice channel with retry logic for 4006 errors"""
        for attempt in range(max_retries):
            try:
                print(f"Voice connection attempt {attempt + 1}/{max_retries} for {channel.guild.id}")
                
                # If there's an existing connection, clean it up first
                if channel.guild.id in voice_clients:
                    try:
                        old_client = voice_clients[channel.guild.id]
                        if old_client.is_connected():
                            await old_client.disconnect(force=True)
                        del voice_clients[channel.guild.id]
                        await asyncio.sleep(2)  # Wait for cleanup
                    except Exception as e:
                        print(f"Error cleaning up old connection: {e}")
                
                # Attempt new connection with enhanced parameters
                voice_client = await channel.connect(
                    timeout=30.0,
                    reconnect=True,
                    self_deaf=True,
                    self_mute=False
                )
                
                # Wait a bit for the connection to stabilize
                await asyncio.sleep(3)
                
                # Verify connection is stable
                if voice_client.is_connected():
                    voice_clients[channel.guild.id] = voice_client
                    print(f"Successfully connected to voice for guild {channel.guild.id}")
                    return voice_client
                else:
                    print(f"Connection not stable for guild {channel.guild.id}")
                    continue
                    
            except discord.errors.ConnectionClosed as e:
                if e.code == 4006:
                    print(f"Voice session error (4006) on attempt {attempt + 1}, retrying...")
                    await asyncio.sleep(5)  # Longer wait for session errors
                    continue
                else:
                    print(f"Connection closed with code {e.code}: {e}")
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(2)
            except asyncio.TimeoutError:
                print(f"Voice connection timeout on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(3)
            except Exception as e:
                print(f"Voice connection error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2)
        
        raise Exception("Failed to connect to voice after all retries")

    queues = {}  # Dictionary to store queues for each guild
    voice_clients = {}
    processing_queue = {}  # Track songs being processed
    yt_dl_options = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {
                "skip": ["dash", "hls"],
                "player_client": ["android", "web"],
                "player_skip": ["configs", "webpage"]
            }
        }
    }
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.5"'}

    # Function to extract YouTube URL with fallback methods
    async def extract_youtube_url(url):
        """Extract YouTube URL with multiple fallback methods for SABR issue"""
        loop = asyncio.get_event_loop()
        
        # Method 1: Try with android client (most reliable for auth issues)
        try:
            ytdl_android = yt_dlp.YoutubeDL({
                **yt_dl_options,
                "extractor_args": {"youtube": {"player_client": ["android"]}}
            })
            data = await loop.run_in_executor(None, lambda: ytdl_android.extract_info(url, download=False))
            if data and 'url' in data:
                return data
        except Exception as e:
            print(f"Android client failed: {e}")
        
        # Method 2: Try with tv_embedded client
        try:
            ytdl_tv = yt_dlp.YoutubeDL({
                **yt_dl_options,
                "extractor_args": {"youtube": {"player_client": ["tv_embedded"]}}
            })
            data = await loop.run_in_executor(None, lambda: ytdl_tv.extract_info(url, download=False))
            if data and 'url' in data:
                return data
        except Exception as e:
            print(f"TV embedded client failed: {e}")
        
        # Method 3: Try with web_music client (good for music)
        try:
            ytdl_music = yt_dlp.YoutubeDL({
                **yt_dl_options,
                "extractor_args": {"youtube": {"player_client": ["web_music"]}}
            })
            data = await loop.run_in_executor(None, lambda: ytdl_music.extract_info(url, download=False))
            if data and 'url' in data:
                return data
        except Exception as e:
            print(f"Web music client failed: {e}")
        
        # Method 4: Try with ios client
        try:
            ytdl_ios = yt_dlp.YoutubeDL({
                **yt_dl_options,
                "extractor_args": {"youtube": {"player_client": ["ios"]}}
            })
            data = await loop.run_in_executor(None, lambda: ytdl_ios.extract_info(url, download=False))
            if data and 'url' in data:
                return data
        except Exception as e:
            print(f"iOS client failed: {e}")
        
        # Method 5: Try default method as last resort
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            if data and 'url' in data:
                return data
        except Exception as e:
            print(f"Default client failed: {e}")
        
        return None

    # Function to check and repair voice connection
    async def ensure_voice_connection(guild_id, channel=None):
        """Ensure voice connection is healthy, reconnect if needed"""
        if guild_id not in voice_clients:
            return False
        
        voice_client = voice_clients[guild_id]
        
        # Check if connection is healthy
        try:
            if not voice_client.is_connected():
                print(f"Voice client not connected for guild {guild_id}, attempting reconnect...")
                if channel:
                    new_client = await connect_to_voice_with_retry(channel)
                    voice_clients[guild_id] = new_client
                    return True
                else:
                    # No channel provided, can't reconnect
                    del voice_clients[guild_id]
                    return False
        except Exception as e:
            print(f"Error checking voice connection for guild {guild_id}: {e}")
            # Clean up broken connection
            try:
                del voice_clients[guild_id]
            except:
                pass
            return False
        
        return True

    # Function to add song to queue or play immediately
    async def add_song_to_queue_or_play(guild_id, song_info, channel):
        """Add song to queue if playing, or play immediately if not"""
        try:
            # Don't check connection here - assume it's already handled by caller
            # Check if something is currently playing
            is_currently_playing = voice_clients[guild_id].is_playing()
            
            if is_currently_playing:
                # Add to queue since something is already playing
                if guild_id not in queues:
                    queues[guild_id] = []
                queues[guild_id].append(song_info)
                queue_position = len(queues[guild_id])
                await channel.send(f"🎵 Added to queue (#{queue_position}): **{song_info['title']}**")
            else:
                # Nothing is playing, start playing immediately
                try:
                    source = discord.FFmpegPCMAudio(song_info['url'], **ffmpeg_options)
                    volume_controlled = discord.PCMVolumeTransformer(source, volume=0.5)
                    voice_clients[guild_id].play(
                        volume_controlled,
                        after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), client.loop)
                    )
                    await channel.send(f"🎶 Now playing: **{song_info['title']}**")
                except Exception as e:
                    print(f"Error starting playback: {e}")
                    await channel.send("❌ Error starting playback. The audio format may not be supported.")
        except Exception as e:
            print(f"Error in add_song_to_queue_or_play: {e}")
            await channel.send("❌ An error occurred while adding the song.")

    # Background function to process songs
    async def process_song_in_background(guild_id, query, channel, is_url=False):
        """Process song extraction in background to avoid blocking main thread"""
        try:
            if is_url:
                # Direct URL extraction
                data = await extract_youtube_url(query)
                if not data:
                    await channel.send("❌ Failed to extract video. This could be due to:\n• Age-restricted content\n• Private/deleted video\n• Geographic restrictions\n• YouTube's anti-bot measures\n\nTry a different video or search by name instead.")
                    return None
                song_info = {
                    'url': data['url'],
                    'title': data.get('title', 'Unknown title')
                }
            else:
                # Search then extract
                song_info = await search_youtube(query)
                if not song_info:
                    await channel.send("❌ No results found. Try a different search term.")
                    return None
                    
                # Extract actual streaming URL
                data = await extract_youtube_url(song_info['url'])
                if not data:
                    await channel.send("❌ Found the video but couldn't extract audio. Try a different search term.")
                    return None
                song_info['url'] = data['url']
            
            return song_info
        except Exception as e:
            print(f"Error processing song: {e}")
            await channel.send("❌ An error occurred while processing the song.")
            return None

    # Function to search YouTube for non-URL queries
    async def search_youtube(query):
        try:
            loop = asyncio.get_event_loop()
            # Run YouTube search in executor to avoid blocking
            def _search():
                videos_search = VideosSearch(query, limit=1)
                return videos_search.result()
            
            results = await loop.run_in_executor(None, _search)
            
            if results and 'result' in results and results['result']:
                video = results['result'][0]
                return {
                    'url': video['link'],
                    'title': video['title']
                }
            return None
        except Exception as e:
            print(f"YouTube search error: {e}")
            return None

    # Play next song in queue function
    async def play_next(guild_id):
        if guild_id in queues and queues[guild_id]:
            # Get the next song from queue
            next_song = queues[guild_id].pop(0)
            
            # Check voice connection health
            if not await ensure_voice_connection(guild_id):
                print(f"Voice connection lost for guild {guild_id}, cannot play next song")
                return None
            
            try:
                # Create FFmpeg player
                source = discord.FFmpegPCMAudio(next_song['url'], **ffmpeg_options)
                
                # Wrap it with a volume controller
                volume_controlled = discord.PCMVolumeTransformer(source)
                
                # Play with the volume-controlled source
                voice_clients[guild_id].play(
                    volume_controlled, 
                    after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), client.loop) if not e else print(f"Player error: {e}")
                )
                
                # Find a text channel to announce the next song
                for channel in voice_clients[guild_id].guild.text_channels:
                    try:
                        await channel.send(f"🎶 Now playing: **{next_song['title']}**")
                        break
                    except:
                        continue
            except Exception as e:
                print(f"Error playing next song: {e}")
                # Try to play the next song if this one failed
                await asyncio.sleep(1)
                await play_next(guild_id)
            
            return next_song
        return None

    # Function to fade out current song
    async def fade_out_and_skip(guild_id):
        if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
            return
            
        voice_client = voice_clients[guild_id]
        if not voice_client.is_playing():
            return
        
        try:
            # Access the volume control directly
            if hasattr(voice_client.source, 'volume'):
                # More gradual fade with smaller steps
                volumes = [0.4, 0.3, 0.2, 0.15, 0.1, 0.05]
                
                for volume in volumes:
                    if not voice_client.is_playing() or not voice_client.is_connected():
                        break
                    
                    # Direct volume control without recreating the player
                    voice_client.source.volume = volume
                    
                    # Wait between volume changes
                    await asyncio.sleep(0.2)
            
            # Final stop after fade is complete
            if voice_client.is_connected():
                voice_client.stop()
            
            # Play next song
            await asyncio.sleep(0.5)
            await play_next(guild_id)
            
        except Exception as e:
            print(f"Error during fade: {e}")
            try:
                if voice_client.is_connected():
                    voice_client.stop()
                await play_next(guild_id)
            except Exception as e2:
                print(f"Error in fade fallback: {e2}")

    @client.event
    async def on_ready():
        print(f'{client.user} is now connected and ready!')
        print(f'Bot is in {len(client.guilds)} guilds')
        
        # Start periodic voice connection health check
        client.loop.create_task(voice_health_monitor())

    async def voice_health_monitor():
        """Monitor voice connections and attempt to fix issues"""
        while not client.is_closed():
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                for guild_id in list(voice_clients.keys()):
                    voice_client = voice_clients[guild_id]
                    
                    # Check if voice client is still connected
                    if not voice_client.is_connected():
                        print(f"Detected disconnected voice client for guild {guild_id}")
                        # Clean up disconnected client
                        try:
                            del voice_clients[guild_id]
                            if guild_id in queues:
                                queues[guild_id].clear()
                        except:
                            pass
                    
            except Exception as e:
                print(f"Error in voice health monitor: {e}")
                await asyncio.sleep(60)  # Wait longer if there's an error

    @client.event
    async def on_disconnect():
        print('Bot disconnected from Discord')

    @client.event
    async def on_resumed():
        print('Bot session resumed')

    @client.event
    async def on_error(event, *args, **kwargs):
        print(f'An error occurred in event {event}: {args}')

    @client.event
    async def on_voice_state_update(member, before, after):
        # Clean up if bot is disconnected from voice
        if member == client.user and before.channel is not None and after.channel is None:
            # Bot was disconnected from voice channel
            print(f"Bot was disconnected from voice channel in guild {before.channel.guild.id}")
            for guild_id in list(voice_clients.keys()):
                if voice_clients[guild_id].guild == before.channel.guild:
                    # Clean up queue and voice client
                    if guild_id in queues:
                        queues[guild_id].clear()
                        print(f"Cleared queue for guild {guild_id}")
                    try:
                        if voice_clients[guild_id].is_connected():
                            await voice_clients[guild_id].disconnect()
                    except Exception as e:
                        print(f"Error disconnecting voice client: {e}")
                    del voice_clients[guild_id]
                    print(f"Cleaned up voice client for guild {guild_id}")
                    break
        
        # Check if bot is alone in voice channel and disconnect after delay
        elif member != client.user and before.channel is not None:
            # Someone left a channel, check if bot is alone
            for guild_id, voice_client in voice_clients.items():
                if (voice_client.channel == before.channel and 
                    len([m for m in voice_client.channel.members if not m.bot]) == 0):
                    # Bot is alone, disconnect after 5 minutes
                    print(f"Bot is alone in voice channel for guild {guild_id}, starting disconnect timer")
                    
                    async def delayed_disconnect():
                        await asyncio.sleep(300)  # 5 minutes
                        if (guild_id in voice_clients and 
                            voice_clients[guild_id].is_connected() and
                            len([m for m in voice_clients[guild_id].channel.members if not m.bot]) == 0):
                            print(f"Disconnecting bot from empty voice channel in guild {guild_id}")
                            try:
                                await voice_clients[guild_id].disconnect()
                                if guild_id in queues:
                                    queues[guild_id].clear()
                                del voice_clients[guild_id]
                            except Exception as e:
                                print(f"Error during auto-disconnect: {e}")
                    
                    asyncio.create_task(delayed_disconnect())
                    break

    @client.event
    async def on_message(message):
        if message.content.startswith("?play"):
            try:
                # Check if user is in a voice channel
                if not message.author.voice or not message.author.voice.channel:
                    await message.channel.send("You need to be in a voice channel to play music.")
                    return
                
                # Check current voice connection status
                needs_connection = True
                if message.guild.id in voice_clients:
                    try:
                        # Check if voice client exists and is connected
                        if voice_clients[message.guild.id].is_connected():
                            # Check if we're in the same channel as the user
                            if voice_clients[message.guild.id].channel == message.author.voice.channel:
                                needs_connection = False
                                print(f"Already connected to correct channel for guild {message.guild.id}")
                            else:
                                # We're in a different channel, need to move
                                print(f"Moving to user's channel for guild {message.guild.id}")
                                await voice_clients[message.guild.id].move_to(message.author.voice.channel)
                                needs_connection = False
                        else:
                            # Voice client exists but not connected, clean it up
                            print(f"Voice client exists but not connected for guild {message.guild.id}, cleaning up")
                            try:
                                await voice_clients[message.guild.id].disconnect()
                            except:
                                pass
                            del voice_clients[message.guild.id]
                    except Exception as ex:
                        # Voice client is corrupted, clean it up
                        print(f"Voice client corrupted for guild {message.guild.id}: {ex}")
                        try:
                            del voice_clients[message.guild.id]
                        except:
                            pass
                
                # Connect to voice only if needed
                if needs_connection:
                    print(f"Attempting voice connection for guild {message.guild.id}")
                    try:
                        voice_client = await connect_to_voice_with_retry(message.author.voice.channel)
                        voice_clients[message.guild.id] = voice_client
                    except Exception as e:
                        print(f"Failed to connect to voice: {e}")
                        await message.channel.send("❌ Failed to connect to voice channel. This could be due to:\n• Network connectivity issues\n• Discord voice server problems\n• Permission issues\n\nPlease try again in a few moments.")
                        return
                else:
                    print(f"Voice connection not needed for guild {message.guild.id}")
            except Exception as e:
                print(f"Voice connection error: {e}")
                await message.channel.send("❌ Failed to connect to voice channel. Please make sure you're in a voice channel and try again.")
                return

            try:
                # Extract the query (everything after ?play)
                query = message.content[6:].strip()
                if not query:
                    await message.channel.send("Please provide a song name or URL.")
                    return
                
                # Initialize queue for this guild if it doesn't exist
                if message.guild.id not in queues:
                    queues[message.guild.id] = []

                # Initialize processing queue if it doesn't exist
                if message.guild.id not in processing_queue:
                    processing_queue[message.guild.id] = []

                # Show immediate feedback that we're processing
                is_url = query.startswith("http")
                if is_url:
                    processing_msg = await message.channel.send("⏳ Processing URL...")
                else:
                    processing_msg = await message.channel.send(f"⏳ Searching and processing: `{query}`...")
                
                # Create background task for song processing
                async def process_and_add():
                    try:
                        song_info = await process_song_in_background(
                            message.guild.id, query, message.channel, is_url
                        )
                        
                        if song_info:
                            # Delete the processing message
                            try:
                                await processing_msg.delete()
                            except:
                                pass
                            
                            # Double-check voice connection before adding song
                            if message.guild.id in voice_clients and voice_clients[message.guild.id].is_connected():
                                await add_song_to_queue_or_play(message.guild.id, song_info, message.channel)
                            else:
                                print(f"Voice connection lost during processing for guild {message.guild.id}")
                                await message.channel.send("❌ Voice connection was lost while processing. Please try the command again.")
                        else:
                            # Delete the processing message if song failed
                            try:
                                await processing_msg.delete()
                            except:
                                pass
                    except Exception as e:
                        print(f"Error in background processing: {e}")
                        try:
                            await processing_msg.delete()
                        except:
                            pass
                        await message.channel.send("❌ An error occurred while processing your request.")
                
                # Start the background task
                asyncio.create_task(process_and_add())
                
            except Exception as e:
                print(f"Error in play command: {e}")
                await message.channel.send("❌ An error occurred while processing your request.")

        elif message.content.startswith("?pause"):
            try:
                if message.guild.id in voice_clients and voice_clients[message.guild.id].is_connected():
                    voice_clients[message.guild.id].pause()
                    await message.channel.send("Paused playback")
                else:
                    await message.channel.send("Not connected to voice channel")
            except Exception as e:
                print(f"Pause error: {e}")
                await message.channel.send("Nothing is playing")

        elif message.content.startswith("?resume"):
            try:
                if message.guild.id in voice_clients and voice_clients[message.guild.id].is_connected():
                    voice_clients[message.guild.id].resume()
                    await message.channel.send("Resumed playback")
                else:
                    await message.channel.send("Not connected to voice channel")
            except Exception as e:
                print(f"Resume error: {e}")
                await message.channel.send("Nothing is paused")

        elif message.content.startswith("?stop"):
            try:
                if message.guild.id in queues:
                    queues[message.guild.id] = []  # Clear the queue
                if message.guild.id in voice_clients:
                    voice_clients[message.guild.id].stop()
                    await voice_clients[message.guild.id].disconnect()
                    del voice_clients[message.guild.id]
                await message.channel.send("Stopped playback and cleared queue")
            except Exception as e:
                print(f"Stop error: {e}")
                await message.channel.send("Error stopping playback")
        
        # Fix the skip command
        elif message.content.startswith("?skip"):
            try:
                # Check if voice client exists and is connected
                if message.guild.id not in voice_clients or not voice_clients[message.guild.id].is_connected():
                    await message.channel.send("Not connected to voice channel")
                    return
                    
                # Instead of stopping immediately, fade out then skip
                if voice_clients[message.guild.id].is_playing():
                    await message.channel.send("Fading out and skipping to next song...")
                    await fade_out_and_skip(message.guild.id)  # No player parameter needed
                else:
                    await message.channel.send("Nothing is playing")
            except Exception as e:
                print(f"Skip error: {e}")
                await message.channel.send("Error skipping: Nothing is playing or no songs in queue")
        
        elif message.content.startswith("?queue"):
            try:
                if message.guild.id in queues and queues[message.guild.id]:
                    queue_list = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(queues[message.guild.id])])
                    await message.channel.send(f"**Current Queue:**\n{queue_list}")
                else:
                    await message.channel.send("The queue is empty")
            except Exception as e:
                print(e)

    # Run the bot with reconnection handling
    async def run_bot_with_retry():
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                await client.start(TOKEN)
            except discord.ConnectionClosed as e:
                retry_count += 1
                print(f'Connection closed (attempt {retry_count}/{max_retries}): {e}')
                if e.code == 4006:
                    print('Invalid session error - waiting before retry...')
                    await asyncio.sleep(5)  # Wait 5 seconds before retry
                elif e.code == 4004:
                    print('Authentication failed - check your token')
                    break
                elif retry_count >= max_retries:
                    print('Max retries reached. Bot shutting down.')
                    break
                else:
                    await asyncio.sleep(2)  # Short wait for other errors
            except discord.LoginFailure:
                print('Invalid token provided')
                break
            except Exception as e:
                retry_count += 1
                print(f'Unexpected error (attempt {retry_count}/{max_retries}): {e}')
                if retry_count >= max_retries:
                    break
                await asyncio.sleep(3)
        
        print('Bot stopped running.')

    # Run the async bot function
    try:
        asyncio.run(run_bot_with_retry())
    except KeyboardInterrupt:
        print('Bot stopped by user')
    except Exception as e:
        print(f'Fatal error: {e}')