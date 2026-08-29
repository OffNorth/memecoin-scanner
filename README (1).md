# 🤖 Memecoin Scanner Bot

Bot Telegram pour scanner et analyser les memecoins en temps réel. Détecte les scams, honeypots, rug pulls et autres red flags avant que tu ne perdes ton argent.

---

## 📋 Sommaire

- [Fonctionnalités](#-fonctionnalités)
- [Prérequis](#-prérequis)
- [Installation sur Linux](#-installation-sur-linux)
- [Configuration avec .env](#-configuration-avec-env)
- [Lancement](#-lancement)
- [Commandes Telegram](#-commandes-telegram)
- [Déploiement 24/7](#-déploiement-247)
- [Mise à jour](#-mise-à-jour)
- [Dépannage](#-dépannage)
- [Limites](#-limites)

---

## ✨ Fonctionnalités

| Vérification | Source | Description |
|--------------|--------|-------------|
| 💧 **Liquidité** | DexScreener | Détecte les liquidités trop faibles (< $5k = danger) |
| 🔒 **Contrat** | Etherscan / BscScan / RugCheck | Fonctions suspectes (mint, blacklist, pause, proxy) |
| 🫧 **Holders** | Bubblemaps | Concentration des wallets (top 1% et top 10%) |
| 🐝 **Honeypot** | RugCheck (Solana) | Score de risque et fonctions dangereuses |
| 📊 **Marché** | DexScreener | Prix, market cap, volume 24h, wash trading |
| 🔗 **Liens rapides** | — | Boutons directs vers Explorer + DexScreener |

---

## 📦 Prérequis

- **Linux** (Ubuntu 22.04+ recommandé)
- **Python 3.9+**
- **pip**
- Un **bot Telegram** (créé via @BotFather)
- (Optionnel) Clés API gratuites Etherscan / BscScan / Bubblemaps

---

## 🐧 Installation sur Linux

### 1. Mettre à jour le système

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Installer Python et les outils

```bash
sudo apt install -y python3 python3-pip python3-venv git
```

Vérifie la version :

```bash
python3 --version   # Doit afficher 3.9 ou plus
pip3 --version
```

### 3. Créer un dossier pour le bot

```bash
mkdir -p ~/memecoin-scanner
cd ~/memecoin-scanner
```

### 4. Créer un environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
```

> 💡 Ton terminal doit afficher `(venv)` au début. Pour quitter : `deactivate`

### 5. Copier les fichiers du projet

Place ces 4 fichiers dans `~/memecoin-scanner` :

```
memecoin-scanner/
├── memecoin_telegram_bot.py   # Le bot
├── requirements.txt           # Dépendances
├── .env                       # Configuration (clés API)
└── README.md                  # Ce fichier
```

### 6. Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration avec .env

Toute la configuration se fait dans le fichier `.env`. **Ne le partage jamais.**

### Étape 1 : Créer le bot Telegram

1. Ouvre Telegram et cherche **@BotFather**
2. Envoie `/newbot`
3. Donne un nom puis un username (ex: `mon_scanner_bot`)
4. **Copie le token** (ex: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Étape 2 : Remplir le fichier .env

```bash
nano .env
```

Colle ce contenu et remplace les valeurs :

```env
# === OBLIGATOIRE ===
TELEGRAM_BOT_TOKEN=123456789:TON_TOKEN_ICI

# === OPTIONNEL MAIS RECOMMANDÉ ===
ETHERSCAN_API_KEY=TON_API_KEY_ICI
BSCSCAN_API_KEY=TON_API_KEY_ICI
BUBBLEMAPS_API_KEY=TON_API_KEY_ICI
```

Sauvegarde : `Ctrl+O` puis `Entrée`, quitte : `Ctrl+X`

> 🔑 **Où trouver les clés API ?**
> - [Etherscan API](https://etherscan.io/apis) — gratuit, 5 appels/sec
> - [BscScan API](https://bscscan.com/apis) — gratuit, 5 appels/sec
> - [Bubblemaps API](https://app.bubblemaps.io/api) — nécessite un compte

### Étape 3 : Sécuriser le fichier .env

```bash
chmod 600 .env
```

> ⚠️ **Important** : Ajoute `.env` à ton `.gitignore` si tu pushes sur GitHub :
> ```bash
> echo ".env" >> .gitignore
> ```

---

## 🚀 Lancement

### Lancer le bot (mode interactif)

```bash
cd ~/memecoin-scanner
source venv/bin/activate
python memecoin_telegram_bot.py
```

Tu devrais voir :

```
🤖 Bot démarré ! Appuie sur Ctrl+C pour arrêter.
```

Va sur Telegram et envoie `/start` à ton bot pour tester !

### Arrêter le bot

Appuie sur `Ctrl+C` dans le terminal.

---

## 💬 Commandes Telegram

| Commande | Description | Exemple |
|----------|-------------|---------|
| `/start` | Message de bienvenue + guide | `/start` |
| `/scan <adresse>` | Analyse un token (Solana par défaut) | `/scan EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| `/scan <adresse> --chain <nom>` | Analyse sur une chaîne spécifique | `/scan 0x... --chain base` |
| `/chains` | Liste les chaînes supportées | `/chains` |
| `/help` | Guide complet d'utilisation | `/help` |
| *(texte libre)* | Colle une adresse directement | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |

### Chaînes supportées

| Chaîne | Argument |
|--------|----------|
| Solana | `solana` (défaut) |
| Ethereum | `ethereum` |
| Base | `base` |
| BNB Chain | `bsc` |
| Arbitrum | `arbitrum` |
| Polygon | `polygon` |

---

## 🌙 Déploiement 24/7

### Option A : Screen (simple)

```bash
sudo apt install -y screen
screen -S memescan
cd ~/memecoin-scanner && source venv/bin/activate && python memecoin_telegram_bot.py
```

**Détacher** : `Ctrl+A` puis `D`

**Réattacher** : `screen -r memescan`

**Arrêter** : `screen -r memescan` puis `Ctrl+C`

### Option B : Systemd (robuste)

```bash
sudo nano /etc/systemd/system/memescan.service
```

Colle :

```ini
[Unit]
Description=Memecoin Scanner Bot
After=network.target

[Service]
Type=simple
User=TON_USERNAME
WorkingDirectory=/home/TON_USERNAME/memecoin-scanner
Environment="PATH=/home/TON_USERNAME/memecoin-scanner/venv/bin"
EnvironmentFile=/home/TON_USERNAME/memecoin-scanner/.env
ExecStart=/home/TON_USERNAME/memecoin-scanner/venv/bin/python /home/TON_USERNAME/memecoin-scanner/memecoin_telegram_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Remplace `TON_USERNAME` par ton vrai nom d'utilisateur.

```bash
sudo systemctl daemon-reload
sudo systemctl enable memescan
sudo systemctl start memescan
```

Commandes :

```bash
sudo systemctl status memescan     # État
sudo systemctl restart memescan    # Redémarrer
sudo systemctl stop memescan       # Arrêter
sudo journalctl -u memescan -f     # Logs en temps réel
```

### Option C : PM2

```bash
sudo npm install -g pm2
pm2 start memecoin_telegram_bot.py --interpreter python3 --name memescan
pm2 save
pm2 startup
```

---

## 🔄 Mise à jour

```bash
cd ~/memecoin-scanner
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Redémarrer selon ta méthode :
sudo systemctl restart memescan    # systemd
# ou
pm2 restart memescan               # PM2
# ou
screen -r memescan                 # screen, puis relancer
```

---

## 🛠️ Dépannage

### ❌ "TELEGRAM_BOT_TOKEN non configuré !"

Vérifie que le fichier `.env` existe bien à côté du script et contient :
```env
TELEGRAM_BOT_TOKEN=123456789:TON_TOKEN_ICI
```

### ❌ "ModuleNotFoundError"

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### ❌ "API rate limit exceeded"

Les clés API gratuites sont limitées. Attends quelques secondes entre les scans.

### ❌ Analyse très lente

- Vérifie ta connexion
- Les API gratuites peuvent être lentes en heure de pointe
- Bubblemaps sans clé API retourne une erreur (normal)

---

## ⚠️ Limites

| Ce qu'il détecte | Ce qu'il ne détecte PAS |
|------------------|------------------------|
| ✅ Fonctions suspectes dans le contrat | ❌ Les intentions du dev |
| ✅ Liquidité faible / honeypot évident | ❌ Les rug pulls "soft" sur plusieurs semaines |
| ✅ Concentration des holders | ❌ Les hacks de compte Twitter |
| ✅ Wash trading basique | ❌ Les wallets liés non détectés |

> 🛡️ **Règle d'or** : Teste toujours avec **$5 maximum** avant d'investir gros.

---

## 📄 Structure du projet

```
memecoin-scanner/
├── memecoin_telegram_bot.py   # Code source
├── requirements.txt           # Dépendances
├── .env                       # Configuration (NE PAS PARTAGER)
├── .gitignore                 # Ignore .env et venv/
├── venv/                      # Environnement virtuel (auto)
└── README.md                  # Ce fichier
```

---

*Bot créé avec ❤️ pour ne plus se faire rug pull.*
