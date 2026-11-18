import os
import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web
from dotenv import load_dotenv
import database as db

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
PORT = int(os.getenv("PORT", 10000))


# --- MINI SERVEUR WEB POUR RENDER / UPTIMEROBOT ---

async def handle_ping(request):
    html_content = """
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"><title>Waifu Tournament Bot</title></head>
    <body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
        <h1>🟢 Bot Waifu Tournament en ligne</h1>
        <p>Le bot Discord est actif et connecté à Supabase.</p>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Serveur web démarré sur le port {PORT}")


# --- COMPOSANTS DISCORD ---

class VoteView(discord.ui.View):
    def __init__(self, duel_id: int, w1: dict, w2: dict):
        super().__init__(timeout=None)
        self.duel_id = duel_id
        self.w1 = w1
        self.w2 = w2

        btn1 = discord.ui.Button(
            label=f"Voter {w1['name']}",
            style=discord.ButtonStyle.primary,
            custom_id=f"vote_{duel_id}_{w1['id']}",
        )
        btn1.callback = self.make_callback(w1)

        btn2 = discord.ui.Button(
            label=f"Voter {w2['name']}",
            style=discord.ButtonStyle.danger,
            custom_id=f"vote_{duel_id}_{w2['id']}",
        )
        btn2.callback = self.make_callback(w2)

        self.add_item(btn1)
        self.add_item(btn2)

    def make_callback(self, waifu: dict):
        async def callback(interaction: discord.Interaction):
            success = db.cast_vote(self.duel_id, interaction.user.id, waifu["id"])
            if not success:
                await interaction.response.send_message(
                    "❌ Ce duel est clôturé, il n'est plus possible de voter.", ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"✅ Ton vote pour **{waifu['name']}** ({waifu['series']}) a bien été enregistré !",
                ephemeral=True,
            )

        return callback


def build_duel_embed(duel: dict) -> discord.Embed:
    w1, w2 = duel["waifu1"], duel["waifu2"]
    v1, v2 = duel["votes1"], duel["votes2"]
    total = v1 + v2

    p1 = round((v1 / total) * 100) if total > 0 else 0
    p2 = round((v2 / total) * 100) if total > 0 else 0

    embed = discord.Embed(
        title=f"⚔️ Duel #{duel['id']} : {w1['name']} VS {w2['name']}",
        description="Cliquez sur l'un des boutons ci-dessous pour soutenir votre favorite !",
        color=discord.Color.magenta(),
    )
    embed.add_field(
        name=f"🔵 {w1['name']}",
        value=f"Œuvre : *{w1['series']}*\nVotes : **{v1}** ({p1}%)",
        inline=True,
    )
    embed.add_field(
        name=f"🔴 {w2['name']}",
        value=f"Œuvre : *{w2['series']}*\nVotes : **{v2}** ({p2}%)",
        inline=True,
    )

    if w1.get("image_url"):
        embed.set_thumbnail(url=w1["image_url"])
    if w2.get("image_url"):
        embed.set_image(url=w2["image_url"])

    embed.set_footer(text=f"Total des votes : {total}")
    return embed


class WaifuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        db.init_db()
        await start_web_server()
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = WaifuBot()


# --- COMMANDES JOUEURS ---

@bot.tree.command(name="waifu-proposer", description="Proposer un personnage pour le tournoi")
@app_commands.describe(
    nom="Nom du personnage",
    oeuvre="Anime, jeu ou manga d'origine",
    image_url="Lien direct vers une image (optionnel)",
)
async def waifu_proposer(
    interaction: discord.Interaction, nom: str, oeuvre: str, image_url: str = None
):
    await interaction.response.defer()
    added = db.add_waifu(nom, oeuvre, image_url, interaction.user.id)
    if added:
        await interaction.followup.send(
            f"✨ **{nom}** (*{oeuvre}*) a été ajouté(e) à la liste des participantes !"
        )
    else:
        await interaction.followup.send(
            f"⚠️ **{nom}** est déjà inscrit(e) dans la base de données.", ephemeral=True
        )


@bot.tree.command(name="duel", description="Afficher le duel actuellement en cours")
async def duel_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    duel = db.get_active_duel()
    if not duel:
        await interaction.followup.send("Aucun duel n'est ouvert pour le moment.", ephemeral=True)
        return

    embed = build_duel_embed(duel)
    view = VoteView(duel["id"], duel["waifu1"], duel["waifu2"])
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name="vote", description="Ouvrir les boutons de vote pour le duel actuel")
async def vote_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    duel = db.get_active_duel()
    if not duel:
        await interaction.followup.send("Aucun duel n'est ouvert pour le moment.", ephemeral=True)
        return

    view = VoteView(duel["id"], duel["waifu1"], duel["waifu2"])
    await interaction.followup.send(
        f"🗳️ Votez pour le **Duel #{duel['id']}** :", view=view, ephemeral=True
    )


@bot.tree.command(name="classement", description="Afficher le classement des participantes")
async def classement_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    waifus = db.get_all_waifus()
    if not waifus:
        await interaction.followup.send("Aucune participante enregistrée pour le moment.", ephemeral=True)
        return

    lines = []
    for idx, w in enumerate(waifus[:15], start=1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"**#{idx}**"
        lines.append(f"{medal} **{w['name']}** (*{w['series']}*) — `{w['wins']}` victoire(s)")

    embed = discord.Embed(
        title="🏆 Classement du Waifu Tournament",
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    await interaction.followup.send(embed=embed)


# --- COMMANDES DE MODÉRATION ---

async def waifu_autocomplete(interaction: discord.Interaction, current: str):
    waifus = db.get_all_waifus()
    return [
        app_commands.Choice(name=f"{w['name']} ({w['series']})", value=w["id"])
        for w in waifus
        if current.lower() in w["name"].lower()
    ][:25]


@bot.tree.command(name="duel-creer", description="[Modération] Créer et ouvrir un nouveau duel")
@app_commands.default_permissions(manage_guild=True)
@app_commands.autocomplete(waifu1=waifu_autocomplete, waifu2=waifu_autocomplete)
async def duel_creer(interaction: discord.Interaction, waifu1: int, waifu2: int):
    await interaction.response.defer()
    duel_id = db.create_duel(waifu1, waifu2)
    if not duel_id:
        await interaction.followup.send(
            "❌ Impossible de créer le duel (choisissez deux personnages différents).",
            ephemeral=True,
        )
        return

    duel = db.get_active_duel()
    embed = build_duel_embed(duel)
    view = VoteView(duel["id"], duel["waifu1"], duel["waifu2"])
    await interaction.followup.send(
        content="🚨 **Un nouveau duel vient de commencer !**", embed=embed, view=view
    )


@bot.tree.command(name="duel-ouvrir", description="[Modération] Réouvrir un duel existant via son ID")
@app_commands.default_permissions(manage_guild=True)
async def duel_ouvrir(interaction: discord.Interaction, duel_id: int):
    await interaction.response.defer()
    if db.set_duel_status(duel_id, "open"):
        await interaction.followup.send(f"🔓 Le duel **#{duel_id}** est de nouveau ouvert aux votes.")
    else:
        await interaction.followup.send(f"❌ Duel **#{duel_id}** introuvable.", ephemeral=True)


@bot.tree.command(name="duel-cloturer", description="[Modération] Clôturer le duel actuel et désigner la gagnante")
@app_commands.default_permissions(manage_guild=True)
async def duel_cloturer(interaction: discord.Interaction):
    await interaction.response.defer()
    result = db.close_active_duel()
    if not result:
        await interaction.followup.send("Aucun duel ouvert à clôturer.", ephemeral=True)
        return

    w1, w2 = result["waifu1"], result["waifu2"]
    v1, v2 = result["votes1"], result["votes2"]

    if result["winner_id"] == w1["id"]:
        verdict = f"🎉 **{w1['name']}** remporte le duel ({v1} contre {v2}) !"
    elif result["winner_id"] == w2["id"]:
        verdict = f"🎉 **{w2['name']}** remporte le duel ({v2} contre {v1}) !"
    else:
        verdict = f"🤝 **Égalité parfaite** ({v1} à {v2}) ! Aucun point attribué."

    await interaction.followup.send(f"🔒 **Duel #{result['id']} clôturé !**\n{verdict}")


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("La variable DISCORD_TOKEN est manquante dans le fichier .env")
    bot.run(TOKEN)
