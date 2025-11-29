from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("BOT_TOKEN")

# --- INIZIO CODICE SERVER FAKE PER RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_fake_server():
    port = int(os.environ.get("PORT", 10000))  # Render ci dà la porta qui
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Server fake avviato sulla porta {port}")
    server.serve_forever()
# --- FINE CODICE SERVER FAKE ---

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

def main():
    # Avvia il server fake in un thread separato PRIMA del bot
    server_thread = threading.Thread(target=run_fake_server)
    server_thread.daemon = True
    server_thread.start()

    # Avvia il bot
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot avviato su Render ✔️")
    app.run_polling()

if __name__ == "__main__":
    main()