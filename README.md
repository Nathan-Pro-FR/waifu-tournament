
# 🏆 Waifu Tournament

Bot Discord indépendant et API de synchronisation
pour le projet Waifu Tournament.

## Fonctionnalités

- Commandes slash Discord
- Affichage des duels
- Boutons de vote
- Votes modifiables
- Classement général
- Proposition de personnages
- Modération des duels
- API REST
- Synchronisation site / Discord
- Base de données SQLite
- Compatibilité PostgreSQL

## Technologies

- Python 3.12+
- discord.py
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic

## Installation

Cloner le dépôt :

```bash
git clone https://github.com/TON-COMPTE/waifu-tournament.git

cd waifu-tournament
```

Créer un environnement virtuel :

```bash
python -m venv .venv
```

Activer l'environnement :

Linux :

```bash
source .venv/bin/activate
```

Windows :

```powershell
.venv\Scripts\Activate.ps1
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Créer la configuration :

```bash
cp .env.example .env
```

Configurer les identifiants Discord et API
dans le fichier .env.

## Démarrage

Terminal 1 : API

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Terminal 2 : bot Discord

```bash
python main.py
```

Documentation API :

http://127.0.0.1:8000/docs

## Commandes Discord

| Commande | Fonction |
|---|---|
| /duel | Duel actuel |
| /vote | Boutons de vote |
| /classement | Classement |
| /waifu-proposer | Proposer un personnage |
| /duel-creer | Créer un duel |
| /duel-ouvrir | Ouvrir les votes |
| /duel-cloturer | Fermer les votes |

## API REST

Toutes les routes /v1 nécessitent :

Authorization: Bearer VOTRE_API_KEY

### Participantes

GET /v1/participants

POST /v1/participants

POST /v1/participants/{id}/approve

### Duels

GET /v1/duels/current

GET /v1/duels/{id}

POST /v1/duels

PATCH /v1/duels/{id}

### Votes

POST /v1/duels/{id}/votes

GET /v1/duels/{id}/results

### Classement

GET /v1/leaderboard

## Règles de vote

Chaque utilisateur dispose d'un vote par duel.

Il peut modifier son vote tant que le duel est ouvert.

La clôture empêche toute nouvelle modification.

Les votes Discord utilisent l'identifiant Discord
de l'utilisateur.

Pour les votes sur le site, le backend doit associer
l'utilisateur connecté à un identifiant stable.

Discord OAuth2 est recommandé pour relier les comptes
du site et Discord.

## Synchronisation

Le site et le bot utilisent la même API et la même
base de données.

Une modification effectuée sur le site est donc
visible depuis Discord.

Une modification effectuée depuis Discord est
visible depuis le site.

Ne place jamais la clé API privée dans le JavaScript
public du navigateur.

## Hébergement

Le projet peut être hébergé sur :

- VPS Linux
- Serveur personnel
- Machine Linux
- Docker
- Hébergement Python compatible

Pour une installation multi-instance, PostgreSQL
est recommandé.

## Sécurité

- Ne jamais publier le fichier .env.
- Utiliser HTTPS en production.
- Protéger les routes API.
- Sauvegarder régulièrement la base de données.
- Vérifier les identités des utilisateurs du site.
- Ne jamais faire confiance à un user_id envoyé
  librement par un visiteur.

## Licence

À définir avant publication.
MIT est une possibilité.
