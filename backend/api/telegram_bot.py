import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I am Hermes V2, your UPSC Intelligence System. Ask me a question.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    # 1. Send initial "thinking" message
    status_message = await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Thinking... ⏳\nDetecting topic..."
    )
    
    # TODO: Pass question to LangGraph Orchestrator here
    # The orchestrator can emit events that we use to update the status_message
    
    # Mock response for now
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=status_message.message_id,
        text="Retrieving context from Qdrant and Neo4j... 📚"
    )
    
    answer = f"Drafted answer for: {question}"
    
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=status_message.message_id,
        text=answer
    )

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logging.error("TELEGRAM_BOT_TOKEN not found in environment variables.")
        return

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logging.info("Starting Telegram Bot Polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
