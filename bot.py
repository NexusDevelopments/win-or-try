import io
import json
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.ext import commands

DATA_FILE = Path(__file__).with_name("ticket_data.json")
EMBED_COLOR = discord.Color.gold()

# this gotta be on so prefix cmds can be read
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='-', intents=intents)
views_registered = False


def get_bot_token():
    # this checks env vars from railway/local so token gets picked up right
    return os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TOKEN")


def load_ticket_data():
    if not DATA_FILE.exists():
        return {"guilds": {}, "tickets": {}}

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"guilds": {}, "tickets": {}}

    if not isinstance(data, dict):
        return {"guilds": {}, "tickets": {}}

    data.setdefault("guilds", {})
    data.setdefault("tickets", {})
    return data


def save_ticket_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_guild_config(guild_id: int):
    data = load_ticket_data()
    guild_key = str(guild_id)
    data["guilds"].setdefault(
        guild_key,
        {
            "panel_channel_id": None,
            "log_channel_id": None,
            "category_id": None,
            "panel_message_id": None,
        },
    )
    save_ticket_data(data)
    return data["guilds"][guild_key]


def update_guild_config(guild_id: int, **updates):
    data = load_ticket_data()
    guild_key = str(guild_id)
    data["guilds"].setdefault(
        guild_key,
        {
            "panel_channel_id": None,
            "log_channel_id": None,
            "category_id": None,
            "panel_message_id": None,
        },
    )
    data["guilds"][guild_key].update(updates)
    save_ticket_data(data)


def find_open_ticket_for_user(guild_id: int, user_id: int):
    data = load_ticket_data()
    for channel_id, ticket in data["tickets"].items():
        if (
            ticket.get("guild_id") == guild_id
            and ticket.get("owner_id") == user_id
            and ticket.get("status") == "open"
        ):
            return int(channel_id)
    return None


def create_ticket_record(channel_id: int, guild_id: int, owner_id: int):
    data = load_ticket_data()
    data["tickets"][str(channel_id)] = {
        "guild_id": guild_id,
        "owner_id": owner_id,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "status": "open",
    }
    save_ticket_data(data)


def close_ticket_record(channel_id: int, closed_by_id: int):
    data = load_ticket_data()
    ticket = data["tickets"].get(str(channel_id))
    if not ticket:
        return None

    ticket["status"] = "closed"
    ticket["closed_at"] = datetime.now(timezone.utc).isoformat()
    ticket["closed_by_id"] = closed_by_id
    save_ticket_data(data)
    return ticket


def get_ticket_record(channel_id: int):
    data = load_ticket_data()
    return data["tickets"].get(str(channel_id))


def slugify_name(value: str):
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:40] or "user"


async def build_transcript(channel: discord.TextChannel):
    lines = []
    async for message in channel.history(limit=None, oldest_first=True):
        stamp = message.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        content = message.content if message.content else "[no text]"
        lines.append(f"[{stamp}] {message.author} ({message.author.id}): {content}")

        if message.attachments:
            for attachment in message.attachments:
                lines.append(f"  attachment: {attachment.url}")

        if message.embeds:
            for embed in message.embeds:
                if embed.title:
                    lines.append(f"  embed title: {embed.title}")
                if embed.description:
                    lines.append(f"  embed text: {embed.description}")

    if not lines:
        lines.append("No messages in this ticket.")

    return "\n".join(lines)


async def send_log_message(guild: discord.Guild, title: str, description: str, transcript_file=None):
    config = get_guild_config(guild.id)
    log_channel = guild.get_channel(config.get("log_channel_id"))
    if not isinstance(log_channel, discord.TextChannel):
        return

    embed = discord.Embed(title=title, description=description, color=EMBED_COLOR)
    if transcript_file:
        await log_channel.send(embed=embed, file=transcript_file)
    else:
        await log_channel.send(embed=embed)


async def close_ticket_channel(channel: discord.TextChannel, closed_by: discord.Member):
    ticket = get_ticket_record(channel.id)
    if not ticket or ticket.get("status") != "open":
        return False, "this channel aint an open ticket."

    transcript_text = await build_transcript(channel)
    transcript_name = f"{channel.name}-transcript.txt"
    transcript_file = discord.File(
        io.BytesIO(transcript_text.encode("utf-8")),
        filename=transcript_name,
    )

    owner_id = ticket.get("owner_id")
    owner_text = f"<@{owner_id}>" if owner_id else "unknown"
    close_ticket_record(channel.id, closed_by.id)

    await send_log_message(
        channel.guild,
        "Ticket Closed",
        f"ticket: {channel.name}\nowner: {owner_text}\nclosed by: {closed_by.mention}",
        transcript_file=transcript_file,
    )

    await channel.delete(reason=f"Ticket closed by {closed_by}")
    return True, "ticket closed."


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, custom_id="ticket:open")
    async def open_ticket(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("this only works in a server.", ephemeral=True)
            return

        config = get_guild_config(interaction.guild.id)
        category = interaction.guild.get_channel(config.get("category_id"))
        log_channel = interaction.guild.get_channel(config.get("log_channel_id"))

        if not isinstance(category, discord.CategoryChannel) or not isinstance(log_channel, discord.TextChannel):
            await interaction.response.send_message(
                "ticket system aint setup right yet. tell an admin to run -ticket setup.",
                ephemeral=True,
            )
            return

        existing_ticket_id = find_open_ticket_for_user(interaction.guild.id, interaction.user.id)
        if existing_ticket_id:
            existing_channel = interaction.guild.get_channel(existing_ticket_id)
            if existing_channel:
                await interaction.response.send_message(
                    f"you already got a ticket open: {existing_channel.mention}",
                    ephemeral=True,
                )
                return

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
        }

        me = interaction.guild.me or interaction.guild.get_member(bot.user.id)
        if me:
            overwrites[me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            )

        channel_name = f"ticket-{slugify_name(interaction.user.display_name)}"
        ticket_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket owner: {interaction.user.id}",
            reason=f"Ticket opened by {interaction.user}",
        )

        create_ticket_record(ticket_channel.id, interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="Ticket Opened",
            description=(
                f"support will talk here.\n\n"
                f"owner: {interaction.user.mention}\n"
                f"when this is done hit the close button."
            ),
            color=EMBED_COLOR,
        )
        await ticket_channel.send(embed=embed, view=TicketCloseView())

        await send_log_message(
            interaction.guild,
            "Ticket Opened",
            f"ticket: {ticket_channel.mention}\nowner: {interaction.user.mention}",
        )

        await interaction.response.send_message(
            f"ticket made: {ticket_channel.mention}",
            ephemeral=True,
        )


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("this only works in a server.", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("this only works in a ticket channel.", ephemeral=True)
            return

        ticket = get_ticket_record(interaction.channel.id)
        if not ticket or ticket.get("status") != "open":
            await interaction.response.send_message("this channel aint an open ticket.", ephemeral=True)
            return

        owner_id = ticket.get("owner_id")
        if interaction.user.id != owner_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("only the ticket owner or an admin can close this.", ephemeral=True)
            return

        await interaction.response.send_message("closing ticket now.", ephemeral=True)
        await close_ticket_channel(interaction.channel, interaction.user)


@bot.event
async def on_ready():
    global views_registered

    if not views_registered:
        bot.add_view(TicketPanelView())
        bot.add_view(TicketCloseView())
        views_registered = True

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
        description=f"{ctx.author.mention} rolled {die_one} & {die_two}",
        color=discord.Color.yellow(),
    )

    await ctx.send(embed=embed)


@bot.group(name="ticket", invoke_without_command=True)
@commands.has_permissions(administrator=True)
async def ticket_group(ctx: commands.Context):
    embed = discord.Embed(
        title="Ticket Commands",
        description=(
            "-ticket setup #panel-channel #log-channel\n"
            "-ticket panel\n"
            "-ticket config\n"
            "-ticket close"
        ),
        color=EMBED_COLOR,
    )
    await ctx.send(embed=embed)


@ticket_group.command(name="setup")
@commands.has_permissions(administrator=True)
async def ticket_setup(ctx: commands.Context, panel_channel: discord.TextChannel, log_channel: discord.TextChannel):
    category = discord.utils.get(ctx.guild.categories, name="Tickets")
    if category is None:
        category = await ctx.guild.create_category("Tickets", reason=f"Ticket setup by {ctx.author}")

    update_guild_config(
        ctx.guild.id,
        panel_channel_id=panel_channel.id,
        log_channel_id=log_channel.id,
        category_id=category.id,
    )

    embed = discord.Embed(
        title="Ticket Setup Saved",
        description=(
            f"panel channel: {panel_channel.mention}\n"
            f"log channel: {log_channel.mention}\n"
            f"category: {category.name}"
        ),
        color=EMBED_COLOR,
    )
    await ctx.send(embed=embed)


@ticket_group.command(name="panel")
@commands.has_permissions(administrator=True)
async def ticket_panel(ctx: commands.Context):
    config = get_guild_config(ctx.guild.id)
    panel_channel = ctx.guild.get_channel(config.get("panel_channel_id"))
    log_channel = ctx.guild.get_channel(config.get("log_channel_id"))
    category = ctx.guild.get_channel(config.get("category_id"))

    if not isinstance(panel_channel, discord.TextChannel) or not isinstance(log_channel, discord.TextChannel) or not isinstance(category, discord.CategoryChannel):
        await ctx.send("run -ticket setup first.")
        return

    embed = discord.Embed(
        title="Support Tickets",
        description="hit the button below to open a private ticket.",
        color=EMBED_COLOR,
    )
    panel_message = await panel_channel.send(embed=embed, view=TicketPanelView())
    update_guild_config(ctx.guild.id, panel_message_id=panel_message.id)
    await ctx.send(f"ticket panel sent in {panel_channel.mention}")


@ticket_group.command(name="config")
@commands.has_permissions(administrator=True)
async def ticket_config(ctx: commands.Context):
    config = get_guild_config(ctx.guild.id)
    panel_channel = ctx.guild.get_channel(config.get("panel_channel_id"))
    log_channel = ctx.guild.get_channel(config.get("log_channel_id"))
    category = ctx.guild.get_channel(config.get("category_id"))

    embed = discord.Embed(
        title="Ticket Config",
        description=(
            f"panel channel: {panel_channel.mention if panel_channel else 'not set'}\n"
            f"log channel: {log_channel.mention if log_channel else 'not set'}\n"
            f"category: {category.name if category else 'not set'}"
        ),
        color=EMBED_COLOR,
    )
    await ctx.send(embed=embed)


@ticket_group.command(name="close")
@commands.has_permissions(administrator=True)
async def ticket_close_from_command(ctx: commands.Context):
    if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("this only works in a ticket channel.")
        return

    closed, message = await close_ticket_channel(ctx.channel, ctx.author)
    if not closed:
        await ctx.send(message)


@bot.command(name="close")
async def close_command(ctx: commands.Context):
    if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("this only works in a ticket channel.")
        return

    ticket = get_ticket_record(ctx.channel.id)
    if not ticket or ticket.get("status") != "open":
        await ctx.send("this channel aint an open ticket.")
        return

    if ctx.author.id != ticket.get("owner_id") and not ctx.author.guild_permissions.administrator:
        await ctx.send("only the ticket owner or an admin can close this.")
        return

    closed, message = await close_ticket_channel(ctx.channel, ctx.author)
    if not closed:
        await ctx.send(message)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("you need admin for that.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("missing stuff in that cmd. use -ticket to see the ticket cmds.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("that channel or value dont look right.")
        return

    if isinstance(error, commands.CommandNotFound):
        return

    raise error


def main():
    token = get_bot_token()
    if not token:
        raise RuntimeError("no bot token env var found. set DISCORD_TOKEN (or BOT_TOKEN/TOKEN) in railway vars.")

    bot.run(token)


if __name__ == "__main__":
    main()
