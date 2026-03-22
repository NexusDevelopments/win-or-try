import os
import random

import discord
from discord.ext import commands

# this gotta be on so prefix cmds can be read
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='-', intents=intents)


def get_bot_token():
    # this checks env vars from railway/local so token gets picked up right
    return os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TOKEN")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready.")


@bot.command(name="roll")
async def roll(ctx: commands.Context):
    die_one = random.randint(1, 6)
    die_two = random.randint(1, 6)

    # if its doubles its Win, if not then Try
    result = "Win" if die_one == die_two else "Try"

    embed = discord.Embed(
        title=f"{result} Dice Roll (6-sided)",
        description=f"🎲 {ctx.author.mention} rolled {die_one} & {die_two}",
        color=discord.Color.yellow(),
    )

    await ctx.send(embed=embed)


def main():
    token = get_bot_token()
    if not token:
        raise RuntimeError("no bot token env var found. set DISCORD_TOKEN (or BOT_TOKEN/TOKEN) in railway vars.")

    bot.run(token)


if __name__ == "__main__":
    main()
