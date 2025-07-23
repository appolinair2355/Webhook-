
#!/usr/bin/env python3
"""
Bot Telegram avec webhook optimisé pour Render.com - Version finale
"""
import os
import logging
import json
import re
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, Bot
from launch_bot
from 
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from compteur import get_compteurs, update_compteurs, reset_compteurs_canal
from style import afficher_compteurs_canal

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app pour webhook
app = Flask(__name__)

# Variables globales
bot_app = None
style_affichage = 1
processed_messages = set()

def load_processed_messages():
    """Charge les messages traités depuis le fichier"""
    global processed_messages
    try:
        with open("processed_messages.json", "r") as f:
            processed_messages = set(json.load(f))
    except:
        processed_messages = set()

def save_processed_messages():
    """Sauvegarde les messages traités"""
    try:
        with open("processed_messages.json", "w") as f:
            json.dump(list(processed_messages), f)
    except:
        pass

def is_message_processed(message_key):
    """Vérifie si un message a déjà été traité"""
    return message_key in processed_messages

def mark_message_processed(message_key):
    """Marque un message comme traité"""
    processed_messages.add(message_key)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages entrants et édités"""
    global style_affichage
    
    try:
        msg = update.message or update.channel_post or update.edited_channel_post or update.edited_message
        if not msg or not msg.text:
            return
        
        text = msg.text
        chat_id = msg.chat_id
        is_edited = update.edited_channel_post or update.edited_message
        
        logger.info(f"Canal {chat_id}: {'[EDITÉ] ' if is_edited else ''}{text[:80]}")
        
        # Vérifie le numéro de message
        match_numero = re.search(r"#n(\d+)", text)
        if not match_numero:
            match = re.search(r'\(([^()]*)\)', text)
            if not match:
                return
            content = match.group(1)
        else:
            numero = int(match_numero.group(1))
            message_key = f"{chat_id}_{numero}"
            
            # Vérifie les indicateurs de progression
            progress_indicators = ['⏰', '▶', '🕐', '➡️']
            confirmation_symbols = ['✅', '🔰']
            
            has_progress = any(indicator in text for indicator in progress_indicators)
            has_confirmation = any(symbol in text for symbol in confirmation_symbols)
            
            if has_progress and not has_confirmation:
                logger.info(f"Message #{numero} a des indicateurs de progression, attente de la version finale")
                return
            
            if is_message_processed(message_key):
                if not is_edited:
                    logger.info(f"Message #{numero} déjà traité et non édité, ignoré")
                    return
                else:
                    logger.info(f"Message #{numero} a été édité, retraitement...")
            
            mark_message_processed(message_key)
            save_processed_messages()
            
            match = re.search(r'\(([^()]*)\)', text)
            if not match:
                return
            content = match.group(1)
        
        logger.info(f"Canal {chat_id} - Contenu: '{content}'")
        
        # Compte les symboles de cartes
        cards_found = {}
        total_cards = 0
        
        heart_count = content.count("❤️") + content.count("♥️")
        if heart_count > 0:
            update_compteurs(chat_id, "❤️", heart_count)
            cards_found["❤️"] = heart_count
            total_cards += heart_count
        
        for symbol in ["♦️", "♣️", "♠️"]:
            count = content.count(symbol)
            if count > 0:
                update_compteurs(chat_id, symbol, count)
                cards_found[symbol] = count
                total_cards += count
        
        if not cards_found:
            logger.info(f"Aucun symbole de carte trouvé dans: '{content}'")
            return
        
        logger.info(f"Canal {chat_id} - Cartes comptées: {cards_found}")
        
        compteurs_updated = get_compteurs(chat_id)
        response = afficher_compteurs_canal(compteurs_updated, style_affichage)
        
        try:
            await msg.reply_text(response)
            logger.info(f"Réponse envoyée au canal {chat_id}")
        except Exception as send_error:
            if "Flood control exceeded" in str(send_error):
                logger.warning(f"Anti-flood activé, message ignoré: {send_error}")
            else:
                logger.error(f"Erreur envoi réponse: {send_error}")
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {e}")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande de reset"""
    try:
        if not update.message:
            return
            
        chat_id = update.message.chat_id
        reset_compteurs_canal(chat_id)
        
        global processed_messages
        processed_messages = {key for key in processed_messages if not key.startswith(f"{chat_id}_")}
        save_processed_messages()
        
        await update.message.reply_text("✅ Reset effectué pour ce canal")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande reset: {e}")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande start"""
    try:
        welcome_msg = (
            "🤖 **Bot de Comptage de Cartes** 🃏\n\n"
            "Bonjour ! Je compte les cartes séparément pour chaque canal.\n\n"
            "📝 **Comment ça marche :**\n"
            "• Envoyez un message avec des cartes entre parenthèses\n"
            "• Exemple : Résultat du tirage (❤️♦️♣️♠️)\n\n"
            "🎯 **Symboles reconnus :**\n"
            "❤️ Cœurs • ♦️ Carreaux • ♣️ Trèfles • ♠️ Piques\n\n"
            "📊 **Compteurs séparés par canal !**\n"
            "⚡ Bot actif avec webhook sur Render.com !"
        )
        await update.message.reply_text(welcome_msg)
        
    except Exception as e:
        logger.error(f"Erreur dans la commande start: {e}")

# Route webhook principal
@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint webhook pour recevoir les mises à jour de Telegram"""
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, bot_app.bot)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot_app.process_update(update))
        finally:
            loop.close()
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Erreur webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Route de santé pour Render.com
@app.route('/health')
def health():
    """Endpoint de santé pour Render.com"""
    return jsonify({
        "status": "healthy", 
        "bot": "running",
        "service": "webhook_active",
        "timestamp": str(__import__('datetime').datetime.now())
    })

# Route principale
@app.route('/')
def index():
    """Page d'accueil avec informations du service"""
    return jsonify({
        "service": "Bot Telegram Webhook - Render.com Ready",
        "status": "active",
        "webhook_url": "/webhook",
        "health_url": "/health",
        "port": os.environ.get("PORT", "Auto-detected"),
        "version": "2.0.0"
    })

def setup_bot():
    """Configure le bot Telegram avec webhook"""
    global bot_app
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN non défini dans les variables d'environnement!")
        raise ValueError("TELEGRAM_BOT_TOKEN non défini - Configurez-le dans Render.com")
    
    logger.info(f"✅ Token détecté: {token[:10]}...")
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN non défini!")
        raise ValueError("TELEGRAM_BOT_TOKEN non défini")
    
    bot_app = Application.builder().token(token).build()
    
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("reset", reset_cmd))
    bot_app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        # Auto-détecter l'URL Render.com
        render_service_name = os.getenv("RENDER_SERVICE_NAME", "telegram-bot-webhook")
        webhook_url = f"https://{render_service_name}.onrender.com"
        logger.info(f"🔧 WEBHOOK_URL auto-détectée: {webhook_url}")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            webhook_full_url = f"{webhook_url}/webhook"
            loop.run_until_complete(bot_app.bot.set_webhook(url=webhook_full_url))
            logger.info(f"✅ Webhook configuré: {webhook_full_url}")
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ Erreur configuration webhook: {e}")
        # Ne pas arrêter le serveur si webhook échoue
        logger.info("🔄 Le serveur continuera de démarrer...")
    
    load_processed_messages()
    logger.info("✅ Bot configuré avec succès")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    logger.info(f"🚀 Démarrage du serveur webhook sur le port {port}")
    logger.info(f"🌐 Configuration Render.com détectée")
    logger.info(f"🔧 Variables d'environnement disponibles: {list(os.environ.keys())}")
    
    try:
        logger.info("📱 Configuration du bot Telegram...")
        setup_bot()
        logger.info("✅ Bot configuré avec succès")
        
        logger.info(f"🌐 Démarrage serveur Flask sur 0.0.0.0:{port}")
        app.run(
            host="0.0.0.0", 
            port=port, 
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        logger.error(f"❌ Erreur critique au démarrage: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
