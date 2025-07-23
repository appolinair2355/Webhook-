#!/usr/bin/env python3
"""
Bot Telegram avec webhook Flask + interface API pour Render.com
"""
import os
import logging
import json
import re
import asyncio
import launch_bot
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)
from compteur import get_compteurs, update_compteurs, reset_compteurs_canal
from style import afficher_compteurs_canal, get_all_styles
from historique import (
    message_deja_traite, ajouter_message_traite,
    get_messages_count, reset_messages_traite
)
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)
current_style = 1  # Style d'affichage par défaut

# ========== ROUTES FLASK API ==========
def get_bot_status():
    try:
        with open("bot_status.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"running": False, "last_message": "Bot not started", "error": None}
    except json.JSONDecodeError:
        return {"running": False, "last_message": "Error reading status", "error": "JSON decode error"}

@app.route('/')
def index():
    return "🤖 Joker Bot Webhook en ligne !"

@app.route('/api/status')
def api_status():
    status = get_bot_status()
    try:
        with open("compteurs_global.json", "r") as f:
            counters = json.load(f)
    except:
        counters = {"❤️": 0, "♦️": 0, "♣️": 0, "♠️": 0}

    messages_count = get_messages_count()
    styles = get_all_styles()

    return jsonify({
        'bot_status': status,
        'counters': counters,
        'messages_processed': messages_count,
        'current_style': current_style,
        'styles': styles
    })

@app.route('/api/reset', methods=['POST'])
def api_reset():
    try:
        import glob
        for file in glob.glob("compteurs_*.json"):
            os.remove(file)
        reset_messages_traite()
        return jsonify({'success': True, 'message': 'Reset completed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/style', methods=['POST'])
def api_style():
    global current_style
    try:
        data = request.get_json()
        new_style = int(data.get('style', 1))
        if 1 <= new_style <= 5:
            current_style = new_style
            return jsonify({'success': True, 'message': f'Style {new_style} sélectionné'})
        else:
            return jsonify({'success': False, 'error': 'Style doit être entre 1 et 5'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== TELEGRAM BOT ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Joker 3K est en ligne !")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    canal_id = update.effective_chat.id
    reset_compteurs_canal(canal_id)
    reset_messages_traite()
    await update.message.reply_text("Compteurs et historique réinitialisés.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    canal_id = update.effective_chat.id
    message_id = message.message_id

    # Mise à jour du statut dans un fichier
    status = {
        "running": True,
        "last_message": message.text[:100] if message.text else "",
        "error": None
    }
    with open("bot_status.json", "w", encoding="utf-8") as f:
        json.dump(status, f)

    if not message.text:
        return

    if message_deja_traite(canal_id, message_id):
        return

    text = message.text
    cartes = re.findall(r"\(([^\(\)]+)\)", text)
    if not cartes:
        return

    premiere_parenthese = cartes[0]
    symboles = re.findall(r"[❤️♦️♣️♠️]", premiere_parenthese)
    if not symboles:
        return

    update_compteurs(canal_id, symboles)
    ajouter_message_traite(canal_id, message_id)

    compteur_text = afficher_compteurs_canal(canal_id, current_style)
    await message.reply_text(compteur_text)

# ========== LANCEMENT ==========
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        await application.update_queue.put(update)
        return "OK", 200

if __name__ == "__main__":
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    bot = application.bot

    # Démarrer le bot dans un thread asyncio
    async def run_bot():
        await application.initialize()
        await application.start()
        logger.info("Bot démarré avec succès")
        await application.updater.start_polling()
        await application.updater.idle()

    import threading
    loop = asyncio.get_event_loop()
    threading.Thread(target=loop.run_until_complete, args=(run_bot(),)).start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
