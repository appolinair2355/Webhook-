#!/usr/bin/env python3
"""
Bot Telegram avec webhook optimisé pour Render.com
"""
import os
import logging
import json
import re
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv

# Charger .env (utile pour local)
load_dotenv()

# Config logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Variables globales
bot_app = None
style_affichage = 1
processed_messages = set()
DATA_FILE = "data.json"

# Fonctions de compteur
def charger_donnees():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def sauvegarder_donnees(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_compteurs(channel_id):
    data = charger_donnees()
    return data.get(str(channel_id), {"❤️": 0, "♦️": 0, "♣️": 0, "♠️": 0})

def update_compteurs(channel_id, symbole, count):
    data = charger_donnees()
    if str(channel_id) not in data:
        data[str(channel_id)] = {"❤️": 0, "♦️": 0, "♣️": 0, "♠️": 0}
    data[str(channel_id)][symbole] += count
    sauvegarder_donnees(data)

def reset_compteurs_canal(channel_id):
    data = charger_donnees()
    data[str(channel_id)] = {"❤️": 0, "♦️": 0, "♣️": 0, "♠️": 0}
    sauvegarder_donnees(data)

# Style d'affichage
def afficher_compteurs_canal(compteurs, style):
    if style == 1:
        return "\n".join([f"{sym} : {val}" for sym, val in compteurs.items()])
    elif style == 2:
        return " | ".join([f"{sym}={val}" for sym, val in compteurs.items()])
    elif style == 3:
        return "\n".join([f"{sym} {'🟩'*val}" for sym, val in compteurs.items()])
    elif style == 4:
        return "\n".join([f"{sym} → {val}" for sym, val in compteurs.items()])
    elif style == 5:
        return "\n".join([f"{sym}: {val} 🔢" for sym, val in compteurs.items()])
    else:
        return str(compteurs)

# Messages déjà traités
def load_processed_messages():
    global processed_messages
    try:
        with open("processed_messages.json", "r") as f:
            processed_messages = set(json.load(f))
    except:
        processed_messages = set()

def save_processed_messages():
    with open("processed_messages.json", "w") as f:
        json.dump(list(processed_messages), f)

def is_message_processed(key):
    return key in processed_messages

def mark_message_processed(key):
    processed_messages.add(key)

# Gestion des messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global style_affichage
    try:
        msg = update.message or update.channel_post or update.edited_channel_post or update.edited_message
        if not msg or not msg.text:
            return

        text = msg.text
        chat_id = msg.chat_id
        match_num = re.search(r"#n(\d+)", text)
        is_edit = update.edited_message or update.edited_channel_post

        if match_num:
            numero = int(match_num.group(1))
            key = f"{chat_id}_{numero}"
            if is_message_processed(key) and not is_edit:
                return
            mark_message_processed(key)
            save_processed_messages()

        match = re.search(r"\(([^()]*)\)", text)
        if not match:
            return
        content = match.group(1)

        found = {}
        total = 0
        coeur = content.count("❤️") + content.count("♥️")
        if coeur > 0:
            update_compteurs(chat_id, "❤️", coeur)
            found["❤️"] = coeur

        for sym in ["♦️", "♣️", "♠️"]:
            count = content.count(sym)
            if count > 0:
                update_compteurs(chat_id, sym, count)
                found[sym] = count

        if not found:
            return

        compteurs = get_compteurs(chat_id)
        response = afficher_compteurs_canal(compteurs, style_affichage)
        await msg.reply_text(response)

    except Exception as e:
        logger.error(f"Erreur traitement message : {e}")

# Commande /start
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🃏 Bienvenue ! Envoyez un message contenant des cartes entre parenthèses, exemple : (❤️♦️♣️♠️)\n\n"
        "Commandes disponibles :\n"
        "/reset — Réinitialiser les compteurs\n"
        "/style 1-5 — Changer le style d'affichage"
    )

# Commande /reset
async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reset_compteurs_canal(chat_id)
    await update.message.reply_text("✅ Compteurs réinitialisés.")

# Commande /style
async def style_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global style_affichage
    if not context.args:
        await update.message.reply_text("Utilisation : /style [1-5]")
        return
    try:
        val = int(context.args[0])
        if 1 <= val <= 5:
            style_affichage = val
            await update.message.reply_text(f"🎨 Style changé : {val}")
        else:
            await update.message.reply_text("Style invalide. Choisir entre 1 et 5.")
    except:
        await update.message.reply_text("Erreur : /style [1-5]")

# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, bot_app.bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.process_update(update))
        loop.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Erreur webhook : {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "telegram_bot", "webhook": True})

@app.route("/")
def index():
    return jsonify({"status": "active", "info": "Telegram bot via Flask + webhook"})

# Initialisation
def setup_bot():
    global bot_app
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN non défini dans les variables d’environnement.")
    bot_app = Application.builder().token(token).build()
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("reset", reset_cmd))
    bot_app.add_handler(CommandHandler("style", style_cmd))
    bot_app.add_handler(MessageHandler(filters.ALL, handle_message))

    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if render_host:
        webhook_url = f"https://{render_host}/webhook"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.bot.set_webhook(url=webhook_url))
        loop.close()
        logger.info(f"✅ Webhook configuré : {webhook_url}")
    else:
        logger.warning("RENDER_EXTERNAL_HOSTNAME non défini.")

    load_processed_messages()
    logger.info("✅ Bot prêt.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Lancement serveur Flask sur le port {port}")
    setup_bot()
    app.run(host="0.0.0.0", port=port)
