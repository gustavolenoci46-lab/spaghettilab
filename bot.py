from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
# Non serve più importare asyncio esplicitamente per il main

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔍 Info", callback_data="info"),
            InlineKeyboardButton("📞 Contatti", callback_data="contatti")
        ],
        [
            InlineKeyboardButton("❓ Aiuto", callback_data="aiuto")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Benvenuto! Scegli un'opzione:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "info":
        await query.edit_message_text("ℹ️ Ecco le informazioni richieste!")
    elif query.data == "contatti":
        await query.edit_message_text("📞 Contatti: esempio@mail.com")
    elif query.data == "aiuto":
        await query.edit_message_text("❓ In cosa posso aiutarti?")

# NOTA: Ho rimosso 'async' qui sotto
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot avviato su Render ✔️")
    
    # NOTA: Ho rimosso 'await' qui sotto
    app.run_polling()

if __name__ == "__main__":
    # NOTA: Ho rimosso asyncio.run(...)
    main()