import discord
from discord.ext import commands
import psycopg2
import os
 
# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ELITE_ROLE_NAME = "Elite"      # Name of the role to assign
WINS_FOR_ELITE = 10            # Wins required for Elite role
# ─────────────────────────────────────────────
 
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
 
bot = commands.Bot(command_prefix="!", intents=intents)
 
# Connect to database
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS wins (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        win_count INTEGER DEFAULT 0
    )
""")
conn.commit()
 
 
def get_wins(user_id: int) -> int:
    cursor.execute("SELECT win_count FROM wins WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0
 
 
def add_win(user_id: int, username: str) -> int:
    cursor.execute("SELECT win_count FROM wins WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    if row:
        new_count = row[0] + 1
        cursor.execute("UPDATE wins SET win_count = %s, username = %s WHERE user_id = %s",
                       (new_count, username, user_id))
    else:
        new_count = 1
        cursor.execute("INSERT INTO wins (user_id, username, win_count) VALUES (%s, %s, %s)",
                       (user_id, username, new_count))
    conn.commit()
    return new_count
 
 
def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)
 
 
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
 
 
@bot.command(name="win")
@is_admin()
async def win(ctx, member: discord.Member):
    """Give a user +1 win (admins only)"""
    new_count = add_win(member.id, member.display_name)
 
    embed = discord.Embed(
        title="🏆 Win recorded!",
        description=f"{member.mention} now has **{new_count} win{'s' if new_count != 1 else ''}**!",
        color=discord.Color.gold()
    )
 
    if new_count >= WINS_FOR_ELITE:
        elite_role = discord.utils.get(ctx.guild.roles, name=ELITE_ROLE_NAME)
        if elite_role:
            if elite_role not in member.roles:
                await member.add_roles(elite_role)
                embed.add_field(
                    name="🌟 Elite unlocked!",
                    value=f"{member.mention} has been given the **{ELITE_ROLE_NAME}** role!",
                    inline=False
                )
        else:
            embed.add_field(
                name="⚠️ Note",
                value=f"Role '{ELITE_ROLE_NAME}' not found. Please create it on your server.",
                inline=False
            )
 
    await ctx.send(embed=embed)
 
 
@bot.command(name="wins")
async def wins(ctx, member: discord.Member = None):
    """Show a user's wins"""
    target = member or ctx.author
    count = get_wins(target.id)
 
    embed = discord.Embed(
        title=f"🏅 Wins for {target.display_name}",
        description=f"**{count} win{'s' if count != 1 else ''}**",
        color=discord.Color.blue()
    )
 
    remaining = max(0, WINS_FOR_ELITE - count)
    if remaining > 0:
        embed.set_footer(text=f"{remaining} more win{'s' if remaining != 1 else ''} until Elite role")
    else:
        embed.set_footer(text="✅ Elite status reached!")
 
    await ctx.send(embed=embed)
 
 
@bot.command(name="leaderboard", aliases=["lb", "top"])
async def leaderboard(ctx):
    """Show the top 10 winners"""
    cursor.execute("SELECT username, win_count FROM wins ORDER BY win_count DESC LIMIT 10")
    rows = cursor.fetchall()
 
    if not rows:
        await ctx.send("No wins recorded yet!")
        return
 
    embed = discord.Embed(
        title="🏆 Win Leaderboard",
        color=discord.Color.gold()
    )
 
    medals = ["🥇", "🥈", "🥉"]
    description = ""
    for i, (username, count) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"`#{i+1}`"
        description += f"{prefix} **{username}** — {count} win{'s' if count != 1 else ''}\n"
 
    embed.description = description
    await ctx.send(embed=embed)
 
 
@bot.command(name="removewins")
@is_admin()
async def removewins(ctx, member: discord.Member, amount: int = 1):
    """Remove wins from a user (admins only)"""
    current = get_wins(member.id)
    new_count = max(0, current - amount)
    cursor.execute("UPDATE wins SET win_count = %s WHERE user_id = %s", (new_count, member.id))
    conn.commit()
 
    await ctx.send(f"✅ {member.mention} now has **{new_count} wins** (-{amount}).")
 
 
@win.error
@removewins.error
async def admin_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only administrators can use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Please mention a user. Example: `!win @Username`")
 
 
bot.run(BOT_TOKEN)
