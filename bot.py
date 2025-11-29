from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("BOT_TOKEN")
# INSERISCI QUI IL TUO USERNAME TELEGRAM (senza @)
CONTACT_USERNAME = "CHEFTONY_OG" 

# --- DATABASE PRODOTTI (Modifica qui i prodotti) ---
PRODUCTS = {
    "prod_1": {"name": "🍝 Spaghetti Amnesia", "price": 10, "unit": "g"},
    "prod_2": {"name": "🍫 Hashish Carbonara", "price": 12, "unit": "g"}
}

# --- SERVER FAKE PER RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_fake_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Server fake avviato sulla porta {port}")
    server.serve_forever()

# --- FUNZIONI BOT ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Inizializza il carrello se non esiste
    if 'cart' not in context.user_data:
        context.user_data['cart'] = {}

    text = (
        "Last seen: recently\n"
        "Ships from: 🇮🇹 🇪🇸 🇺🇸 -> 🇪🇺\n"
        "Currency: EUR\n\n"
        "🍝 SPAGHETTIMAFIA SHOP 🍝\n\n"
        "🔔 BEFORE ORDERING -> READ OUR POLICY\n\n"
        "✅ Premium Quality\n"
        "✅ Europe Delivery\n"
        "✅ Best Prices\n"
        "✅ 24/7 Customer Service"
    )

    keyboard = [
        [InlineKeyboardButton("💊 Listings", callback_data="listings")],
        [
            InlineKeyboardButton("📣 OUR POLICY", callback_data="policy"),
            InlineKeyboardButton("📞 Contacts", url=f"https://t.me/{CONTACT_USERNAME}")
        ],
        [InlineKeyboardButton("🛒 Il mio Carrello", callback_data="show_cart")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Se viene chiamato da un bottone (Indietro) o dal comando /start
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)

async def policy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    policy_text = (
        "📣 **OUR POLICY**\n\n"
        "**1. Spedizioni** 🚚\n"
        "Tutti gli ordini vengono spediti entro 24h dal pagamento. "
        "Utilizziamo metodi stealth avanzati per garantire la sicurezza.\n\n"
        "**2. Rimborsi (Reship)** 🔄\n"
        "Offriamo 100% reship se il pacco viene fermato in dogana (con lettera di sequestro). "
        "Nessun rimborso per indirizzi errati forniti dal cliente.\n\n"
        "**3. Pagamenti** 💶\n"
        "Accettiamo solo Crypto (BTC, XMR, USDT). Pagamento anticipato.\n\n"
        "**4. Privacy** 🔒\n"
        "I dati del cliente vengono cancellati subito dopo la spedizione.\n\n"
        "⚠️ *Ordinando accetti automaticamente queste condizioni.*"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
    await query.edit_message_text(text=policy_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    # Genera bottoni per ogni prodotto
    for key, prod in PRODUCTS.items():
        btn_text = f"{prod['name']} - {prod['price']}€/{prod['unit']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"sel_{key}")])
    
    keyboard.append([InlineKeyboardButton("🛒 Vedi Carrello", callback_data="show_cart")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])

    await query.edit_message_text("💊 **LISTINGS**\nSeleziona un prodotto per scegliere la quantità:", 
                                  reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Recupera l'ID del prodotto dal callback (es. "sel_prod_1")
    prod_id = query.data.split("_")[1] + "_" + query.data.split("_")[2] # ricostruisce "prod_1"
    product = PRODUCTS[prod_id]

    # Salva temporaneamente quale prodotto sta guardando l'utente
    context.user_data['active_product'] = prod_id

    text = f"Hai selezionato: **{product['name']}**\nPrezzo: {product['price']}€ al {product['unit']}.\n\nQuanto ne vuoi?"
    
    # Bottoni quantità
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data=f"add_{prod_id}_1"),
            InlineKeyboardButton("2", callback_data=f"add_{prod_id}_2"),
            InlineKeyboardButton("5", callback_data=f"add_{prod_id}_5")
        ],
        [
            InlineKeyboardButton("10", callback_data=f"add_{prod_id}_10"),
            InlineKeyboardButton("50", callback_data=f"add_{prod_id}_50")
        ],
        [InlineKeyboardButton("🔙 Torna ai Prodotti", callback_data="listings")]
    ]
    
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Aggiunto al carrello! ✅")
    
    # Data format: add_prod_1_5 (Azione_Prodotto_Quantità)
    parts = query.data.split("_")
    prod_id = f"{parts[1]}_{parts[2]}"
    quantity = int(parts[3])
    
    cart = context.user_data.get('cart', {})
    
    # Aggiorna il carrello
    if prod_id in cart:
        cart[prod_id] += quantity
    else:
        cart[prod_id] = quantity
    
    context.user_data['cart'] = cart
    
    # Torna alla lista prodotti o mostra conferma
    product_name = PRODUCTS[prod_id]['name']
    await query.edit_message_text(
        f"✅ Aggiunti **{quantity}** di **{product_name}** al carrello.\n\nCosa vuoi fare?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Continua lo shopping", callback_data="listings")],
            [InlineKeyboardButton("🛒 Vai al pagamento (Vedi Carrello)", callback_data="show_cart")]
        ]),
        parse_mode="Markdown"
    )

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cart = context.user_data.get('cart', {})
    
    if not cart:
        text = "🛒 **Il tuo carrello è vuoto!**"
        keyboard = [[InlineKeyboardButton("🔙 Torna allo Shop", callback_data="listings")]]
    else:
        text = "🛒 **IL TUO CARRELLO**\n\n"
        total = 0
        for prod_id, qty in cart.items():
            prod = PRODUCTS[prod_id]
            subtotal = prod['price'] * qty
            total += subtotal
            text += f"▪️ {prod['name']} x{qty} = {subtotal}€\n"
        
        text += f"\n💰 **TOTALE: {total}€**"
        text += "\n\nPer ordinare, scrivici in chat privata o clicca sotto:"
        
        keyboard = [
            [InlineKeyboardButton("🗑 Svuota Carrello", callback_data="clear_cart")],
            [InlineKeyboardButton("📞 Contatta per Ordinare", url=f"https://t.me/{CONTACT_USERNAME}")],
            [InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")]
        ]

    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Carrello svuotato 🗑")
    context.user_data['cart'] = {}
    await show_cart(update, context)

# --- GESTORE PRINCIPALE ---
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "main_menu":
        await start(update, context)
    elif data == "policy":
        await policy(update, context)
    elif data == "listings":
        await listings(update, context)
    elif data.startswith("sel_"): # Selezione prodotto
        await select_quantity(update, context)
    elif data.startswith("add_"): # Aggiunta quantità
        await add_to_cart(update, context)
    elif data == "show_cart":
        await show_cart(update, context)
    elif data == "clear_cart":
        await clear_cart(update, context)

def main():
    # Avvia Server Fake
    server_thread = threading.Thread(target=run_fake_server)
    server_thread.daemon = True
    server_thread.start()

    # Avvia Bot
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(router))

    print("Bot avviato su Render ✔️")
    app.run_polling()

if __name__ == "__main__":
    main()