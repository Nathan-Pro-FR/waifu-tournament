import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import database as db

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("waifu_tournament")

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()
MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID", "0") or 0)

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN absent du fichier .env")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def is_moderator(interaction):
    if interaction.guild is None:
        return False

    permissions = interaction.user.guild_permissions

    if permissions.manage_guild or permissions.administrator:
        return True

    if MOD_ROLE_ID:
        return any(
            role.id == MOD_ROLE_ID
            for role in interaction.user.roles
        )

    return False


def create_embed(duel):
    labels = {
        "draft": "Brouillon",
        "open": "Votes ouverts",
        "closed": "Clôturé"
    }

    embed = discord.Embed(
        title=f"🏆 Waifu Tournament — Duel #{duel['id']}",
        description=(
            f"**{duel['participant_a']['name']}**"
            f" VS "
            f"**{duel['participant_b']['name']}**"
        ),
        color=discord.Color.from_rgb(126, 200, 255)
    )

    embed.add_field(
        name="Statut",
        value=labels[duel["status"]],
        inline=True
    )

    embed.add_field(
        name="Votes",
        value=str(duel["vote_count"]),
        inline=True
    )

    if duel["participant_a"]["image_url"]:
        embed.set_thumbnail(
            url=duel["participant_a"]["image_url"]
        )

    if duel["participant_b"]["image_url"]:
        embed.set_image(
            url=duel["participant_b"]["image_url"]
        )

    embed.set_footer(
        text="Waifu Tournament • Votes modifiables"
    )

    return embed


class VoteButton(discord.ui.Button):

    def __init__(self, duel_id, participant_id, side):
        super().__init__(
            label=f"Voter {side.upper()}",
            style=discord.ButtonStyle.primary,
            custom_id=f"wt:vote:{duel_id}:{participant_id}"
        )

        self.duel_id = duel_id
        self.participant_id = participant_id

    async def callback(self, interaction):

        try:
            result = db.cast_vote(
                duel_id=self.duel_id,
                participant_id=self.participant_id,
                user_id=str(interaction.user.id),
                username=str(interaction.user),
                source="discord"
            )

            message = (
                f"✅ Vote enregistré pour "
                f"**{result['participant_name']}**."
            )

            if result["changed"]:
                message += "\nTon ancien vote a été remplacé."

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

        except (ValueError, LookupError) as exc:
            await interaction.response.send_message(
                f"⚠️ {exc}",
                ephemeral=True
            )

        except Exception:
            log.exception("Erreur de vote")

            await interaction.response.send_message(
                "Une erreur est survenue.",
                ephemeral=True
            )


class DuelVoteView(discord.ui.View):

    def __init__(self, duel_id, participant_a, participant_b):
        super().__init__(timeout=None)

        self.add_item(
            VoteButton(duel_id, participant_a, "a")
        )

        self.add_item(
            VoteButton(duel_id, participant_b, "b")
        )


@bot.event
async def on_ready():

    db.init_db()

    log.info("Bot connecté : %s", bot.user)

    for duel in db.list_open_duels():
        bot.add_view(
            DuelVoteView(
                duel["id"],
                duel["participant_a"]["id"],
                duel["participant_b"]["id"]
            )
        )

    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        else:
            await bot.tree.sync()

    except Exception:
        log.exception("Erreur de synchronisation Discord")


@bot.tree.command(
    name="duel",
    description="Afficher le duel actuel"
)
async def duel(interaction):

    current = db.get_current_duel()

    if not current:
        await interaction.response.send_message(
            "Aucun duel actuellement ouvert.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        embed=create_embed(current)
    )


@bot.tree.command(
    name="vote",
    description="Afficher les boutons de vote"
)
async def vote(interaction):

    current = db.get_current_duel()

    if not current:
        await interaction.response.send_message(
            "Aucun duel ouvert.",
            ephemeral=True
        )
        return

    view = DuelVoteView(
        current["id"],
        current["participant_a"]["id"],
        current["participant_b"]["id"]
    )

    await interaction.response.send_message(
        embed=create_embed(current),
        view=view
    )


@bot.tree.command(
    name="classement",
    description="Afficher le classement"
)
async def classement(interaction):

    results = db.get_leaderboard()

    if not results:
        await interaction.response.send_message(
            "Le classement est vide."
        )
        return

    lines = []

    for index, participant in enumerate(results[:15], 1):
        lines.append(
            f"**{index}. {participant['name']}** "
            f"— {participant['votes']} vote(s)"
        )

    embed = discord.Embed(
        title="🏅 Classement Waifu Tournament",
        description="\n".join(lines),
        color=discord.Color.from_rgb(183, 148, 246)
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="waifu-proposer",
    description="Proposer un personnage"
)
@app_commands.describe(
    nom="Nom du personnage",
    image_url="URL HTTPS de son image (facultatif)"
)
async def waifu_proposer(
    interaction,
    nom: str,
    image_url: str = ""
):

    try:
        participant = db.propose_participant(
            nom,
            image_url or None,
            str(interaction.user.id),
            str(interaction.user)
        )

        await interaction.response.send_message(
            f"✨ Proposition enregistrée : "
            f"**{participant['name']}**.\n"
            "Elle attend une validation.",
            ephemeral=True
        )

    except ValueError as exc:
        await interaction.response.send_message(
            f"⚠️ {exc}",
            ephemeral=True
        )


@bot.tree.command(
    name="duel-creer",
    description="Créer un duel"
)
@app_commands.describe(
    nom_a="Première participante",
    nom_b="Deuxième participante"
)
async def duel_creer(interaction, nom_a: str, nom_b: str):

    if not is_moderator(interaction):
        await interaction.response.send_message(
            "Permission de modération requise.",
            ephemeral=True
        )
        return

    try:
        result = db.create_duel(nom_a, nom_b)

        await interaction.response.send_message(
            f"✅ Duel #{result['id']} créé : "
            f"**{nom_a} VS {nom_b}**"
        )

    except ValueError as exc:
        await interaction.response.send_message(
            f"⚠️ {exc}",
            ephemeral=True
        )


@bot.tree.command(
    name="duel-ouvrir",
    description="Ouvrir les votes d'un duel"
)
async def duel_ouvrir(interaction, duel_id: int):

    if not is_moderator(interaction):
        await interaction.response.send_message(
            "Permission de modération requise.",
            ephemeral=True
        )
        return

    try:
        result = db.set_duel_status(duel_id, "open")

        view = DuelVoteView(
            result["id"],
            result["participant_a"]["id"],
            result["participant_b"]["id"]
        )

        await interaction.response.send_message(
            "🗳️ Les votes sont ouverts !",
            embed=create_embed(result),
            view=view
        )

    except (ValueError, LookupError) as exc:
        await interaction.response.send_message(
            f"⚠️ {exc}",
            ephemeral=True
        )


@bot.tree.command(
    name="duel-cloturer",
    description="Clôturer les votes d'un duel"
)
async def duel_cloturer(interaction, duel_id: int):

    if not is_moderator(interaction):
        await interaction.response.send_message(
            "Permission de modération requise.",
            ephemeral=True
        )
        return

    try:
        result = db.set_duel_status(duel_id, "closed")

        await interaction.response.send_message(
            f"🔒 Duel #{duel_id} clôturé.\n"
            f"Total : {result['vote_count']} vote(s).",
            embed=create_embed(result)
        )

    except (ValueError, LookupError) as exc:
        await interaction.response.send_message(
            f"⚠️ {exc}",
            ephemeral=True
        )


if __name__ == "__main__":
    db.init_db()
    bot.run(TOKEN)
