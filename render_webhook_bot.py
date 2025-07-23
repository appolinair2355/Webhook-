#!/usr/bin/env python3
"""
Bot Telegram avec webhook Flask pour Render.com
"""

import os
import logging
import sys
import signal
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
from compteur import get_compteurs, update_compteurs, reset_compteurs_canal
from style import afficher_compteurs_canal
import re
import json
)
from style import afficher_compteurs_canal
from compteur import get_compteurs, update_compteurs, reset_compteurs_canal
from dotenv import load_dotenv

# Chargement des variables d’environnement
load_dotenv()

# Configuration du logger
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app pour Render Web Service
app = Flask(__name__)

# Application Telegram (sera initialisée dans setup_bot)
bot_app = None
processed_messages = {}

# ========================
# Fonctions de Commandes
# ========================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot actif et prêt !")


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = str(update.effective_chat.id)
    reset_compteurs_canal(channel_id)
    await update.message.reply_text("🔄 Compteurs réinitialisés !")


async def style_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎨 Cette commande changera le style (à implémenter).")


# ========================
# Gestion des messages
# ========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    text = message.text or ""
    if "(" in text:
        cards = extract_cards(text)
        if cards:
            canal_id = str(update.effective_chat.id)
            update_compteurs(canal_id, cards)
            await message.reply_text(afficher_compteurs_canal(canal_id))
            save_processed_message(update.effective_chat.id, message.message_id)


def extract_cards(text):
    import re
    match = re.search(r"\((.*?)\)", text)
    if match:
        cards_text = match.group(1)
        return [c.strip() for c in cards_text.split() if c.strip()]
    return []

# ========================
# Sauvegarde des messages
# ========================

def save_processed_message(channel_id, message_id):
    global processed_messages
    channel_id = str(channel_id)
    if channel_id not in processed_messages:
        processed_messages[channel_id] = []
    if message_id not in processed_messages[channel_id]:
        processed_messages[channel_id].append(message_id)
        with open("processed.json", "w") as f:
            json.dump(processed_messages, f)


def load_processed_messages():
    global processed_messages
    if os.path.exists("processed.json"):
        with open("processed.json", "r") as f:
            processed_messages = json.load(f)


# ========================
# Configuration du bot
# ========================

def setup_bot():
    global bot_app
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN non défini dans les variables d’environnement.")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot_app = Application.builder().token(token).build()

    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("reset", reset_cmd))
    bot_app.add_handler(CommandHandler("style", style_cmd))
    bot_app.add_handler(MessageHandler(filters.ALL, handle_message))

    loop.run_until_complete(bot_app.initialize())

    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if render_host:
        webhook_url = f"https://{render_host}/webhook"
        loop.run_until_complete(bot_app.bot.set_webhook(url=webhook_url))
        logger.info(f"✅ Webhook configuré : {webhook_url}")
    else:
        logger.warning("RENDER_EXTERNAL_HOSTNAME non défini.")

    load_processed_messages()
    logger.info("✅ Bot prêt.")


# ========================
# Route Flask pour Webhook
# ========================

@app.route("/webhook", methods=["POST"])
async def webhook():
    if request.method == "POST":
        try:
            update = Update.de_json(request.get_json(force=True), bot_app.bot)
            await bot_app.process_update(update)
        except Exception as e:
            logger.error(f"Erreur dans le webhook : {e}")
        return "ok", 200


# ========================
# Point d’entrée Render
# ========================

if __name__ == "__main__":
    setup_bot()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
