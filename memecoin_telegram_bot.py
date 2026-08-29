"""
Memecoin Scanner Bot — Telegram
================================
Bot Telegram complet pour scanner les memecoins et détecter les scams.
Lit sa configuration depuis un fichier .env (ne jamais le partager !)

DEPENDANCES :
    pip install -r requirements.txt

CONFIGURATION :
    1. Copie .env.example en .env
    2. Remplis les valeurs dans .env
    3. Lance : python memecoin_telegram_bot.py

COMMANDES :
    /start      — Message de bienvenue + guide
    /scan <adresse> [--chain solana|ethereum|base|bsc]
                — Analyse complète d'un token
    /help       — Liste des commandes et conseils
    /chains     — Chaînes supportées
"""

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional

import aiohttp
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# =============================================================================
# CHARGEMENT DU .ENV
# =============================================================================
# Cherche le .env dans le même dossier que le script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    load_dotenv()  # Cherche dans le répertoire courant

# --- Récupération des variables ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")
BUBBLEMAPS_API_KEY = os.getenv("BUBBLEMAPS_API_KEY", "")

# Chaînes supportées
CHAINS = {
    "solana":   {"name": "Solana",   "explorer": "solscan.io",      "scan_api": None},
    "ethereum": {"name": "Ethereum", "explorer": "etherscan.io",    "scan_api": "https://api.etherscan.io/api"},
    "base":     {"name": "Base",     "explorer": "basescan.org",    "scan_api": "https://api.basescan.org/api"},
    "bsc":      {"name": "BSC",      "explorer": "bscscan.com",     "scan_api": "https://api.bscscan.com/api"},
    "arbitrum": {"name": "Arbitrum", "explorer": "arbiscan.io",     "scan_api": "https://api.arbiscan.io/api"},
    "polygon":  {"name": "Polygon",  "explorer": "polygonscan.com", "scan_api": "https://api.polygonscan.com/api"},
}

DEFAULT_CHAIN = "solana"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =============================================================================
# STRUCTURES DE DONNÉES
# =============================================================================
@dataclass
class RiskReport:
    token_address: str
    chain: str
    token_name: str = "Unknown"
    token_symbol: str = "???"
    price_usd: float = 0.0
    market_cap: float = 0.0
    liquidity_usd: float = 0.0
    volume_24h: float = 0.0
    score: int = 0
    red_flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    green_flags: List[str] = field(default_factory=list)

    def add_red(self, msg: str):
        self.red_flags.append(msg)
        self.score = min(100, self.score + 20)

    def add_yellow(self, msg: str):
        self.warnings.append(msg)
        self.score = min(100, self.score + 8)

    def add_green(self, msg: str):
        self.green_flags.append(msg)

# =============================================================================
# MODULES D'ANALYSE (ASYNC)
# =============================================================================
class DexScreenerModule:
    BASE_URL = "https://api.dexscreener.com/latest/dex"

    @staticmethod
    async def fetch(session: aiohttp.ClientSession, address: str) -> Optional[List[Dict]]:
        url = f"{DexScreenerModule.BASE_URL}/tokens/{address}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("pairs", [])
        except Exception as e:
            logger.warning(f"DexScreener error: {e}")
            return None

    @staticmethod
    def analyze(report: RiskReport, pairs: List[Dict]):
        if not pairs:
            report.add_red("❌ Aucune paire trouvée sur DexScreener — token probablement non listé ou très suspect.")
            return

        best = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))

        report.token_name = best.get("baseToken", {}).get("name", "Unknown")
        report.token_symbol = best.get("baseToken", {}).get("symbol", "???")
        report.price_usd = float(best.get("priceUsd", 0) or 0)
        report.market_cap = float(best.get("marketCap", 0) or 0)
        report.liquidity_usd = float(best.get("liquidity", {}).get("usd", 0) or 0)
        report.volume_24h = float(best.get("volume", {}).get("h24", 0) or 0)

        liq = report.liquidity_usd
        vol = report.volume_24h

        # Liquidité
        if liq < 3000:
            report.add_red(f"💀 Liquidité extrêmement faible : ${liq:,.0f} — rug pull en 1 clic.")
        elif liq < 20000:
            report.add_yellow(f"⚠️ Liquidité faible : ${liq:,.0f} — risque élevé.")
        elif liq < 100000:
            report.add_yellow(f"⚠️ Liquidité modérée : ${liq:,.0f}")
        else:
            report.add_green(f"✅ Liquidité correcte : ${liq:,.0f}")

        # Volume vs Liquidité
        if liq > 0:
            ratio = vol / liq
            if ratio > 100:
                report.add_red(f"🔥 Wash trading suspect : volume {ratio:.0f}x la liquidité !")
            elif ratio > 30:
                report.add_yellow(f"⚠️ Volume anormalement élevé ({ratio:.0f}x la liq) — possible manipulation.")
            else:
                report.add_green(f"✅ Ratio volume/liquidité sain : {ratio:.1f}x")

        # Holders
        holders = best.get("holders", None)
        if isinstance(holders, int):
            if holders < 20:
                report.add_red(f"💀 Seulement {holders} holders — concentration mortelle.")
            elif holders < 100:
                report.add_yellow(f"⚠️ Très peu de holders ({holders})")
            elif holders > 500:
                report.add_green(f"✅ {holders} holders — distribution décente")

        # Créateur
        creator = best.get("creator", "")
        if creator:
            report.add_yellow(f"ℹ️ Créateur : `{creator}` — vérifie son historique sur DeBank/Arkham.")

        # Vérification si la liquidité est brûlée/verrouillée
        lp_burned = best.get("lp", {}).get("burned", False)
        if lp_burned:
            report.add_green("✅ Liquidité brûlée (LP tokens burned)")

class RugCheckModule:
    BASE_URL = "https://api.rugcheck.xyz/v1"

    @staticmethod
    async def fetch(session: aiohttp.ClientSession, address: str) -> Optional[Dict]:
        url = f"{RugCheckModule.BASE_URL}/tokens/{address}/report"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 404:
                    return None
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:
            logger.warning(f"RugCheck error: {e}")
            return None

    @staticmethod
    def analyze(report: RiskReport, data: Optional[Dict]):
        if not data:
            report.add_yellow("❓ RugCheck indisponible pour ce token.")
            return

        score = data.get("score", 0)
        risks = data.get("risks", [])

        if score > 800:
            report.add_red(f"🚨 RugCheck Score CATASTROPHIQUE : {score}/1000 — NE PAS ACHETER.")
        elif score > 400:
            report.add_red(f"🚨 RugCheck Score élevé : {score}/1000 — fuite recommandée.")
        elif score > 150:
            report.add_yellow(f"⚠️ RugCheck Score : {score}/1000 — méfiance.")
        else:
            report.add_green(f"✅ RugCheck Score propre : {score}/1000")

        for risk in risks:
            level = risk.get("level", "unknown")
            name = risk.get("name", "?")
            desc = risk.get("description", "")

            if level == "danger":
                report.add_red(f"🔴 [{name}] {desc}")
            elif level == "warn":
                report.add_yellow(f"🟡 [{name}] {desc}")

class ExplorerModule:
    @staticmethod
    async def fetch_contract(session: aiohttp.ClientSession, chain: str, address: str) -> Optional[Dict]:
        api_url = CHAINS[chain]["scan_api"]
        if not api_url:
            return None

        api_key = ETHERSCAN_API_KEY if chain in ("ethereum", "base", "arbitrum", "polygon") else BSCSCAN_API_KEY

        if not api_key:
            logger.warning(f"Pas de clé API pour {chain} — analyse de contrat limitée.")
            return None

        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": api_key,
        }
        try:
            async with session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("status") == "1" and data.get("result"):
                    return data["result"][0]
        except Exception as e:
            logger.warning(f"Explorer error: {e}")
        return None

    @staticmethod
    def analyze(report: RiskReport, source: Optional[Dict]):
        if source is None:
            report.add_yellow("⚠️ Contrat non vérifié ou clé API manquante — impossible d'analyser le code source.")
            return

        code = source.get("SourceCode", "")
        name = source.get("ContractName", "Unknown")

        report.add_green(f"✅ Contrat vérifié : `{name}`")

        suspicious = [
            ("selfdestruct", "Fonction de destruction du contrat"),
            ("_mint(", "Fonction de mint (création de tokens)"),
            ("mint(", "Fonction de mint (création de tokens)"),
            ("blacklist", "Fonction de blacklist"),
            ("pause", "Fonction de pause"),
            ("unpause", "Fonction de unpause"),
            ("setTaxFee", "Taxe modifiable"),
            ("setMaxTxAmount", "Limites de transaction modifiables"),
            ("renounceOwnership", "Renonciation ownership (peut être bon ou mauvais)"),
            ("transferOwnership", "Transfert d'ownership"),
            ("destroy", "Fonction destroy"),
        ]

        found = []
        for func, desc in suspicious:
            if func.lower() in code.lower():
                found.append(desc)

        if found:
            report.add_yellow(f"⚠️ Fonctions suspectes détectées : {', '.join(found)}")
        else:
            report.add_green("✅ Aucune fonction manifestement dangereuse détectée.")

        if "proxy" in code.lower() or source.get("Proxy") == "1":
            report.add_yellow("⚠️ Contrat proxy — le code peut être modifié à tout moment.")

class BubblemapsModule:
    @staticmethod
    async def fetch(session: aiohttp.ClientSession, chain: str, address: str) -> Optional[Dict]:
        url = f"https://api.bubblemaps.io/v1/token/{chain}/{address}"
        try:
            headers = {}
            if BUBBLEMAPS_API_KEY and BUBBLEMAPS_API_KEY != "TON_API_KEY_ICI":
                headers["Authorization"] = f"Bearer {BUBBLEMAPS_API_KEY}"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except:
            pass
        return None

    @staticmethod
    def analyze(report: RiskReport, data: Optional[Dict]):
        if not data:
            report.add_yellow("❓ Bubblemaps indisponible — vérifie manuellement la concentration.")
            return

        top1 = data.get("top_holder_percentage", 0)
        top10 = data.get("top_10_percentage", 0)

        if top1 > 25:
            report.add_red(f"💀 UN wallet détient {top1:.1f}% du supply — dump imminent possible.")
        elif top1 > 10:
            report.add_yellow(f"⚠️ Top holder : {top1:.1f}% — concentration élevée.")
        else:
            report.add_green(f"✅ Top holder raisonnable : {top1:.1f}%")

        if top10 > 60:
            report.add_red(f"💀 Top 10 détient {top10:.1f}% — distribution catastrophique.")
        elif top10 > 40:
            report.add_yellow(f"⚠️ Top 10 : {top10:.1f}% — concentration significative.")
        else:
            report.add_green(f"✅ Top 10 sain : {top10:.1f}%")

# =============================================================================
# ANALYSE COMPLÈTE
# =============================================================================
async def analyze_token(address: str, chain: str) -> RiskReport:
    report = RiskReport(token_address=address, chain=chain)

    async with aiohttp.ClientSession() as session:
        # 1. DexScreener
        pairs = await DexScreenerModule.fetch(session, address)
        DexScreenerModule.analyze(report, pairs or [])

        # 2. RugCheck (Solana) ou Explorer (EVM)
        if chain == "solana":
            rug_data = await RugCheckModule.fetch(session, address)
            RugCheckModule.analyze(report, rug_data)
        else:
            source = await ExplorerModule.fetch_contract(session, chain, address)
            ExplorerModule.analyze(report, source)

        # 3. Bubblemaps
        bubble_data = await BubblemapsModule.fetch(session, chain, address)
        BubblemapsModule.analyze(report, bubble_data)

    # 4. Honeypot / Checklist finale
    report.add_yellow("🧪 Test honeypot : achète $5 et essaie de revendre immédiatement.")
    report.add_yellow("🔍 Vérifie manuellement : Twitter officiel, site web, team doxxée.")

    return report

# =============================================================================
# FORMATAGE DU RAPPORT POUR TELEGRAM
# =============================================================================
def format_report(report: RiskReport) -> str:
    if report.score >= 60:
        header = f"🚨 *SCAM RISQUE ÉLEVÉ* — Score `{report.score}/100`"
    elif report.score >= 30:
        header = f"⚠️ *RISQUE MODÉRÉ* — Score `{report.score}/100`"
    else:
        header = f"✅ *RISQUE FAIBLE* — Score `{report.score}/100`"

    lines = [
        f"📊 *Analyse de {report.token_name} ({report.token_symbol})*",
        f"`{report.token_address}`",
        f"⛓ Chaîne : *{CHAINS[report.chain]['name']}*",
        "",
        f"💰 Prix : `${report.price_usd:,.6f}`" if report.price_usd else "",
        f"📈 Market Cap : `${report.market_cap:,.0f}`" if report.market_cap else "",
        f"💧 Liquidité : `${report.liquidity_usd:,.0f}`" if report.liquidity_usd else "",
        f"📊 Volume 24h : `${report.volume_24h:,.0f}`" if report.volume_24h else "",
        "",
        f"━ {header} ━",
        "",
    ]

    if report.red_flags:
        lines.append("🔴 *RED FLAGS :*")
        for f in report.red_flags:
            lines.append(f"  • {f}")
        lines.append("")

    if report.warnings:
        lines.append("🟡 *WARNINGS :*")
        for f in report.warnings:
            lines.append(f"  • {f}")
        lines.append("")

    if report.green_flags:
        lines.append("🟢 *BONS SIGNES :*")
        for f in report.green_flags:
            lines.append(f"  • {f}")
        lines.append("")

    lines.extend([
        "━ ━ ━ ━ ━ ━ ━ ━ ━ ━",
        "⚠️ *Disclaimer* : Cet outil est indicatif. Aucun bot ne remplace ton jugement. Ne mets jamais plus que ce que tu peux perdre.",
    ])

    return "\n".join(filter(None, lines))

# =============================================================================
# HANDLERS TELEGRAM
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "👋 *Bienvenue sur Memecoin Scanner Bot !*\n\n"
        "Je scanne les memecoins pour détecter les scams avant que tu ne perdes ton argent.\n\n"
        "*Commandes :*\n"
        "  `/scan <adresse>` — Analyse rapide (Solana par défaut)\n"
        "  `/scan <adresse> --chain ethereum` — Analyse sur Ethereum\n"
        "  `/chains` — Liste des chaînes supportées\n"
        "  `/help` — Guide complet\n\n"
        "⚡ *Exemple :*\n"
        "`/scan EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v --chain solana`"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Guide d'utilisation*\n\n"
        "*1. Comment scanner un token ?*\n"
        "Envoie : `/scan <adresse_du_token>`\n"
        "Par défaut, je scanne sur *Solana*.\n\n"
        "*2. Changer de chaîne*\n"
        "Ajoute `--chain <nom>` :\n"
        "• `--chain ethereum`\n"
        "• `--chain base`\n"
        "• `--chain bsc`\n"
        "• `--chain arbitrum`\n"
        "• `--chain polygon`\n\n"
        "*3. Ce que je vérifie*\n"
        "✅ Liquidité sur DexScreener\n"
        "✅ Fonctions suspectes dans le contrat\n"
        "✅ Concentration des holders (Bubblemaps)\n"
        "✅ Score RugCheck (Solana)\n"
        "✅ Red flags classiques (honeypot, wash trading...)\n\n"
        "*4. Limites*\n"
        "❌ Je ne peux pas lire les intentions des devs\n"
        "❌ Je ne détecte pas les hacks de compte Twitter\n"
        "❌ Un contrat 'propre' peut quand même être un scam\n\n"
        "🛡️ *Règle d'or* : Teste toujours avec $5 avant d'investir gros."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def chains_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "⛓ *Chaînes supportées :*\n\n"
    for key, info in CHAINS.items():
        text += f"• `{key}` — {info['name']} ({info['explorer']})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ *Usage incorrect.*\n"
            "Exemple : `/scan <adresse> --chain solana`",
            parse_mode="Markdown"
        )
        return

    address = args[0]
    chain = DEFAULT_CHAIN

    for i, arg in enumerate(args):
        if arg == "--chain" and i + 1 < len(args):
            chain = args[i + 1].lower()
            break

    if chain not in CHAINS:
        await update.message.reply_text(
            f"❌ Chaîne `{chain}` non supportée.\n"
            f"Utilise `/chains` pour voir la liste.",
            parse_mode="Markdown"
        )
        return

    if len(address) < 30:
        await update.message.reply_text(
            "❌ Adresse invalide. Une adresse de token fait généralement 40+ caractères.",
            parse_mode="Markdown"
        )
        return

    wait_msg = await update.message.reply_text(
        f"🔍 Analyse de `{address[:12]}...` sur *{CHAINS[chain]['name']}* en cours...\n"
        f"⏳ Ça prend ~5-10 secondes.",
        parse_mode="Markdown"
    )

    try:
        report = await analyze_token(address, chain)
        text = format_report(report)

        keyboard = [
            [InlineKeyboardButton("🔗 Voir sur Explorer", url=f"https://{CHAINS[chain]['explorer']}/token/{address}")],
            [InlineKeyboardButton("📊 Voir sur DexScreener", url=f"https://dexscreener.com/{chain}/{address}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await wait_msg.edit_text(text, parse_mode="Markdown", reply_markup=reply_markup, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Scan error: {e}")
        await wait_msg.edit_text(
            f"❌ *Erreur lors de l'analyse.*\n"
            f"Détail : `{str(e)[:200]}`\n"
            f"Vérifie que l'adresse est correcte.",
            parse_mode="Markdown"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if re.match(r'^[A-Za-z0-9]{32,}$', text):
        context.args = [text]
        await scan_cmd(update, context)
        return

    await update.message.reply_text(
        "🤔 Je n'ai pas compris.\n"
        "Envoie une *adresse de token* directement, ou utilise `/scan <adresse>`.",
        parse_mode="Markdown"
    )

# =============================================================================
# MAIN
# =============================================================================
def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz":
        print("=" * 60)
        print("❌ ERREUR : TELEGRAM_BOT_TOKEN non configuré !")
        print("")
        print("   1. Crée un fichier .env à côté du script")
        print("   2. Ajoute : TELEGRAM_BOT_TOKEN=ton_token_ici")
        print("   3. Relance le bot")
        print("=" * 60)
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("chains", chains_cmd))
    application.add_handler(CommandHandler("scan", scan_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot démarré ! Appuie sur Ctrl+C pour arrêter.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
