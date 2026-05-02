import discord
from discord.ext import commands
import json
import os
import requests
from flask import Flask, request
from threading import Thread
import asyncio
from dotenv import load_dotenv

load_dotenv()

# ========================= CONFIG =========================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

VERIFICATION_ROLE_NAME = "Verified"
VERIFICATION_CHANNEL_ID = int(os.getenv("VERIFICATION_CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIRECT_URI = os.getenv("REDIRECT_URI")
PORT = int(os.getenv("PORT", 5000))

OAUTH2_URL = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=identify+guilds.join"

TOKEN_FILE = "user_tokens.json"

def load_tokens():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except Exception:
            print("⚠️ Token file corrupted. Starting fresh.")
            return {}
    return {}

user_tokens = load_tokens()

def save_tokens():
    with open(TOKEN_FILE, "w") as f:
        json.dump(user_tokens, f, indent=4)

# ====================== FLASK CALLBACK ======================
app = Flask(__name__)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "<h1>❌ No code received</h1>", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post("https://discord.com/api/oauth2/token", data=data)

    if r.status_code != 200:
        return f"<h1>❌ Token error: {r.text}</h1>", 400

    access_token = r.json()["access_token"]

    user_info = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    user_id = str(user_info["id"])
    user_tokens[user_id] = access_token
    save_tokens()

    guild = bot.get_guild(GUILD_ID)
    if guild:
        member = guild.get_member(int(user_id))
        if member:
            role = discord.utils.get(guild.roles, name=VERIFICATION_ROLE_NAME)
            if role:
                asyncio.run_coroutine_threadsafe(member.add_roles(role), bot.loop)

    return """
<!DOCTYPE html>
<html><head><title>Verified</title><style>body{background:#36393f;color:#fff;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}.card{background:#2f3136;padding:60px;border-radius:20px;text-align:center;box-shadow:0 20px 40px rgba(0,0,0,.4)}h1{color:#43b581}</style></head><body><div class="card"><h1>✅ Successfully Verified!</h1><p>You can now close this tab and return to Discord.</p></div></body></html>
""", 200

def run_flask():
    print(f"🌐 Callback running on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ====================== DISCORD BOT ======================
@bot.event
async def on_ready():
    print(f"✅ Bot online as {bot.user}")

@bot.event
async def on_member_remove(member):
    user_id = str(member.id)
    if user_id in user_tokens:
        token = user_tokens[user_id]
        try:
            headers = {"Authorization": f"Bot {BOT_TOKEN}"}
            data = {"access_token": token}
            url = f"https://discord.com/api/guilds/{member.guild.id}/members/{member.id}"
            response = requests.put(url, json=data, headers=headers)
            if response.ok:
                print(f"✅ Auto-rejoined {member}")
        except Exception as e:
            print(f"Auto-rejoin error: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setupverify(ctx):
    embed = discord.Embed(title="Verification Required", description="Click the button below to verify.", color=discord.Color.blue())
    view = discord.ui.View()
    button = discord.ui.Button(label="Verify", style=discord.ButtonStyle.green, url=OAUTH2_URL)
    view.add_item(button)
    await ctx.send(embed=embed, view=view)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(BOT_TOKEN)
