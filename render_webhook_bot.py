#!/usr/bin/env python3
"""
Bot Telegram avec webhook pour déploiement Render.com
"""
import os
import logging
import json
import re
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import launch_bot
from compteur import get_compteurs, update_compteurs, reset_compteurs_canal
from style import afficher_compteurs_canal

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(name)

# Flask app pour webhook
app = Flask(name)

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
        # Récupère le message de n'importe quelle source
        msg = update.message or update.channel_post or update.edited_channel_post or update.edited_message
        if not msg or not msg.text:
            return
        
        text = msg.text
        chat_id = msg.chat_id
        
        # Détecte si c'est un message édité
        is_edited = update.edited_channel_post or update.edited_message
        
        logger.info(f"Canal {chat_id}: {'[EDITÉ] ' if is_edited else ''}{text[:80]}")
        
        # Vérifie le numéro de message
        match_numero = re.search(r"#n(\d+)", text)
        if not match_numero:
            # Trouve les PREMIÈRES parenthèses seulement pour les messages sans numéro
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
            
            # Si le message a des indicateurs de progression sans confirmation, attendre la version finale
            if has_progress and not has_confirmation:
                logger.info(f"Message #{numero} a des indicateurs de progression, attente de la version finale")
                return
            
            # Pour les messages finaux : vérifier si déjà traité sauf si édité
            if is_message_processed(message_key):
                if not is_edited:
                    logger.info(f"Message #{numero} déjà traité et non édité, ignoré")
                    return
                else:
                    logger.info(f"Message #{numero} a été édité, retraitement...")
            
            # Marquer comme traité
            mark_message_processed(message_key)
            save_processed_messages()


# Trouve les PREMIÈRES parenthèses seulement
            match = re.search(r'\(([^()]*)\)', text)
            if not match:
                return
            content = match.group(1)
        
        logger.info(f"Canal {chat_id} - Contenu: '{content}'")
        
        # Compte TOUS les symboles de cartes dans le contenu
        cards_found = {}
        total_cards = 0
        
        # Vérifie les coeurs (les deux symboles)
        heart_count = content.count("❤️") + content.count("♥️")
        if heart_count > 0:
            update_compteurs(chat_id, "❤️", heart_count)
            cards_found["❤️"] = heart_count
            total_cards += heart_count
        
        # Vérifie les autres symboles
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
        
        # Récupère les compteurs mis à jour et envoie la réponse
        compteurs_updated = get_compteurs(chat_id)
        response = afficher_compteurs_canal(compteurs_updated, style_affichage)
        await msg.reply_text(response)
        logger.info(f"Réponse envoyée au canal {chat_id}")
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {e}")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande de reset"""
    try:
        if not update.message:
            return
            
        chat_id = update.message.chat_id
        reset_compteurs_canal(chat_id)
        
        # Nettoie les messages traités pour ce canal
        global processed_messages
        processed_messages = {key for key in processed_messages if not key.startswith(f"{chat_id}_")}
        save_processed_messages()
        
        await update.message.reply_text("✅ Reset effectué pour ce canal")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande reset: {e}")
