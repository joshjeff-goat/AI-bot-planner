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
ALLOWED_USER_ID = int(os.environ.get("TELEGRAM_USER_ID"))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BIN_URL = os.environ.get("BIN_URL")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('models/-gemini-1.5-flash')

def get_data_from_bin():
    try:
        response = requests.get(BIN_URL)
        if response.status_code == 200:
            return response.json().get('record', {})
    except Exception as e:
        logging.error(f"Error reading bin: {e}")
    return {}

def update_data_in_bin(data):
    try:
        requests.put(BIN_URL, json={'record': data}, headers={'Content-Type': 'application/json'})
    except Exception as e:
        logging.error(f"Error updating bin: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text="AI Planner Ready.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
        
    user_prompt = update.message.text
    context_data = get_data_from_bin()
    
    prompt = f"Context: {context_data}\n\nTask: {user_prompt}"
    response = model.generate_content(prompt)
    reply_text = response.text
    
    context_data['last_interaction'] = user_prompt
    update_data_in_bin(context_data)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    application.add_handler(start_handler)
    application.add_handler(msg_handler)
    
    application.run_polling()
