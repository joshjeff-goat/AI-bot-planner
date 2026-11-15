import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import google.generativeai as genai
import requests

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.environ.get("TELEGRAM_USER_ID", "0"))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BIN_URL = os.environ.get("BIN_URL")

genai.configure(api_key=GEMINI_KEY)

def get_working_model():
    # Use the latest active Flash alias, with fallbacks to current models
    preferred_models = [
        'gemini-flash-latest',
        'gemini-2.5-flash',
        'gemini-2.0-flash'
    ]
    try:
        available = [
            m.name.replace('models/', '') 
            for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        logging.info(f"Available Gemini models for this key: {available}")
        for pref in preferred_models:
            if pref in available:
                logging.info(f"Selected model: {pref}")
                return genai.GenerativeModel(pref)
        if available:
            logging.info(f"Using first available model: {available[0]}")
            return genai.GenerativeModel(available[0])
    except Exception as e:
        logging.error(f"Error listing models: {e}")
    
    return genai.GenerativeModel('gemini-flash-latest')

model = get_working_model()

def get_data_from_bin():
    if not BIN_URL:
        return {}
    try:
        response = requests.get(BIN_URL, timeout=10)
        if response.status_code == 200:
            return response.json().get('record', {})
    except Exception as e:
        logging.error(f"Error reading bin: {e}")
    return {}

def update_data_in_bin(data):
    if not BIN_URL:
        return
    try:
        requests.put(
            BIN_URL, 
            json={'record': data}, 
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
    except Exception as e:
        logging.error(f"Error updating bin: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        await update.message.reply_text(f"Unauthorized. Your Telegram ID is {user_id}.")
        return
    await update.message.reply_text("AI Planner Ready. Send me your plans!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        await update.message.reply_text(f"Unauthorized. Your Telegram ID is {user_id}.")
        return

    user_prompt = update.message.text
    
    try:
        context_data = get_data_from_bin()
        prompt = (
            f"You are a helpful daily planner assistant.\n"
            f"Previous Context: {context_data}\n"
            f"User message: {user_prompt}"
        )
        
        response = model.generate_content(prompt)
        reply_text = response.text

        if isinstance(context_data, dict):
            context_data['last_interaction'] = user_prompt
            update_data_in_bin(context_data)

        await update.message.reply_text(reply_text)
        
    except Exception as e:
        logging.error(f"Error handling message: {e}")
        await update.message.reply_text(f"⚠️ Bot Error: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    app.add_handler(start_handler)
    app.add_handler(msg_handler)
    
    app.run_polling(drop_pending_updates=True)
