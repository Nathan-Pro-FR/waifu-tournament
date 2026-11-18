# Waifu Tournament — Bot Discord (Supabase + Render)

Bot Discord de tournoi de personnages hébergeable gratuitement avec persistance des données sur PostgreSQL (Supabase).

## 1. Configuration de Supabase (Base de données gratuite)

1. Créez un compte gratuit sur [Supabase](https://supabase.com/) et lancez un nouveau projet.
2. Allez dans **Project Settings** (icône engrenage) > **Database**.
3. Copiez la **Connection String (URI)** en sélectionnant le mode **Transaction pooler** (port `6543`).
4. Remplacez `[YOUR-PASSWORD]` dans l'URL par le mot de passe choisi lors de la création du projet.

## 2. Déploiement sur Render (Hébergement gratuit)

1. Placez les fichiers (`main.py`, `database.py`, `requirements.txt`) sur un dépôt **GitHub** (public ou privé).
2. Créez un compte sur [Render](https://render.com/) et cliquez sur **New + > Web Service**.
3. Connectez votre dépôt GitHub et configurez :
   - **Runtime** : `Python 3`
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `python main.py`
   - **Instance Type** : `Free`
4. Dans l'onglet **Environment**, ajoutez vos variables :
   - `DISCORD_TOKEN` : Le token de votre bot Discord.
   - `DATABASE_URL` : L'URL PostgreSQL récupérée sur Supabase.
   - `GUILD_ID` : *(Optionnel)* L'ID de votre serveur Discord.
5. Cliquez sur **Deploy Web Service**.

## 3. Maintenir le bot éveillé 24h/24

1. Une fois déployé, copiez l'URL de votre service Render (ex. `https://waifu-bot.onrender.com`).
2. Créez un compte gratuit sur [UptimeRobot](https://uptimerobot.com/) ou [Cron-job.org](https://cron-job.org/).
3. Ajoutez un moniteur HTTP(S) pointant vers l'URL de votre bot avec un intervalle de **5 minutes**.
