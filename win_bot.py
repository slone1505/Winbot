import discord
from discord.ext import commands
import sqlite3
import os

# ─────────────────────────────────────────────
#  EINSTELLUNGEN – hier anpassen!
# ─────────────────────────────────────────────
BOT_TOKEN = "DEIN_BOT_TOKEN_HIER"
ELITE_ROLE_NAME = "Elite"      # Name der Rolle die vergeben wird
WINS_FOR_ELITE = 10            # Anzahl Wins für die Elite-Rolle
# ─────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Datenbank einrichten
conn = sqlite3.connect("wins.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS wins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        win_count INTEGER DEFAULT 0
    )
""")
conn.commit()


def get_wins(user_id: int) -> int:
    cursor.execute("SELECT win_count FROM wins WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0


def add_win(user_id: int, username: str) -> int:
    cursor.execute("SELECT win_count FROM wins WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        new_count = row[0] + 1
        cursor.execute("UPDATE wins SET win_count = ?, username = ? WHERE user_id = ?",
                       (new_count, username, user_id))
    else:
        new_count = 1
        cursor.execute("INSERT INTO wins (user_id, username, win_count) VALUES (?, ?, ?)",
                       (user_id, username, new_count))
    conn.commit()
    return new_count


def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)


@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")


@bot.command(name="win")
@is_admin()
async def win(ctx, member: discord.Member):
    """Gibt einem User +1 Win (nur Admins)"""
    new_count = add_win(member.id, member.display_name)

    embed = discord.Embed(
        title="🏆 Win vergeben!",
        description=f"{member.mention} hat jetzt **{new_count} Win{'s' if new_count != 1 else ''}**!",
        color=discord.Color.gold()
    )

    # Elite-Rolle vergeben wenn Schwellwert erreicht
    if new_count >= WINS_FOR_ELITE:
        elite_role = discord.utils.get(ctx.guild.roles, name=ELITE_ROLE_NAME)
        if elite_role:
            if elite_role not in member.roles:
                await member.add_roles(elite_role)
                embed.add_field(
                    name="🌟 Elite erreicht!",
                    value=f"{member.mention} hat die **{ELITE_ROLE_NAME}**-Rolle erhalten!",
                    inline=False
                )
        else:
            embed.add_field(
                name="⚠️ Hinweis",
                value=f"Rolle '{ELITE_ROLE_NAME}' nicht gefunden. Bitte erstelle sie im Server.",
                inline=False
            )

    await ctx.send(embed=embed)


@bot.command(name="wins")
async def wins(ctx, member: discord.Member = None):
    """Zeigt die Wins eines Users an"""
    target = member or ctx.author
    count = get_wins(target.id)

    embed = discord.Embed(
        title=f"🏅 Wins von {target.display_name}",
        description=f"**{count} Win{'s' if count != 1 else ''}**",
        color=discord.Color.blue()
    )

    remaining = max(0, WINS_FOR_ELITE - count)
    if remaining > 0:
        embed.set_footer(text=f"Noch {remaining} Win{'s' if remaining != 1 else ''} bis zur Elite-Rolle")
    else:
        embed.set_footer(text="✅ Elite-Status erreicht!")

    await ctx.send(embed=embed)


@bot.command(name="leaderboard", aliases=["lb", "top"])
async def leaderboard(ctx):
    """Zeigt die Top 10 Gewinner"""
    cursor.execute("SELECT username, win_count FROM wins ORDER BY win_count DESC LIMIT 10")
    rows = cursor.fetchall()

    if not rows:
        await ctx.send("Noch keine Wins vergeben!")
        return

    embed = discord.Embed(
        title="🏆 Win Leaderboard",
        color=discord.Color.gold()
    )

    medals = ["🥇", "🥈", "🥉"]
    description = ""
    for i, (username, count) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"`#{i+1}`"
        description += f"{prefix} **{username}** — {count} Win{'s' if count != 1 else ''}\n"

    embed.description = description
    await ctx.send(embed=embed)


@bot.command(name="removewins")
@is_admin()
async def removewins(ctx, member: discord.Member, amount: int = 1):
    """Entfernt Wins von einem User (nur Admins)"""
    current = get_wins(member.id)
    new_count = max(0, current - amount)
    cursor.execute("UPDATE wins SET win_count = ? WHERE user_id = ?", (new_count, member.id))
    conn.commit()

    await ctx.send(f"✅ {member.mention} hat jetzt **{new_count} Wins** (-{amount}).")


@win.error
@removewins.error
async def admin_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Nur Administratoren dürfen diesen Command benutzen.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Bitte einen User angeben. Beispiel: `!win @Username`")


bot.run(BOT_TOKEN)
