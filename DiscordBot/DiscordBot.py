import asyncio
from itertools import starmap
import discord
import youtube_dl
from urllib.parse import urlparse
from discord.ext import commands
from asyncio import run
# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url_title(cls, querry, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        if not(urlparse(querry)):
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{querry}", download=not stream))
        else:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(querry, download=not stream))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls (discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.musicQueu = []

    @commands.command()
    async def play(self, ctx, *, querry):
        """Streams from a url (same as yt, but doesn't predownload)"""
        if ctx.voice_client.is_playing():
            self.musicQueu.append(querry)
            await ctx.send('Adicionado na fila: {}'.format(querry))
        elif not (ctx.voice_client.is_playing()):
            async with ctx.typing():
                player = await YTDLSource.from_url_title(querry, loop=self.bot.loop, stream=True)
                ctx.voice_client.play(player, after= lambda e: print('Player error: %s' % e) if e else asyncio.run_coroutine_threadsafe(self.proximo(ctx=ctx), loop=self.bot.loop))
            await ctx.send('Now playing: {}'.format(player.title))

    @commands.command()
    async def proximo(self, ctx):
        if self.musicQueu:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
                await self.play(ctx = ctx, querry = self.musicQueu.pop(0))
            else:    
                await self.play(ctx = ctx, querry = self.musicQueu.pop(0))
        elif not self.musicQueu and not ctx.voice_client.is_playing():
            await ctx.send('Sem musicas na fila!')
            ctx.voice_client.stop()

    @commands.command()
    async def fila(self, ctx):
        if self.musicQueu:
           await ctx.send('\n'.join(starmap('{}: {}'.format, enumerate(self.musicQueu)))) 
        else:
            await ctx.send('Fila vazia!')   
        
    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")
        ctx.voice_client.source.volume = volume / 100
        await ctx.send("Changed volume to {}%".format(volume))

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")


bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"),
                   description='Relatively simple music bot example')

@bot.event
async def on_ready():
    print('Logged in as {0} ({0.id})'.format(bot.user))
    print('------')

bot.add_cog(Music(bot))
bot.run('TOKEN')

