from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
import threading
import requests # Serve per i prezzi crypto
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("BOT_TOKEN")
CONTACT_USERNAME = "tuo_username_qui"  # Solo username, senza @

# IMPORTANTE: Inserisci qui il tuo Chat ID Numerico per ricevere gli ordini.
# Se non lo sai, avvia il bot, scrivi /start e guarda i log di Render: lo stamperà lì.
ADMIN_CHAT_ID = 123456789 

# I TUOI WALLET (Dove ricevi i soldi)
WALLETS = {
    "BTC": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", # Esempio, metti il tuo
    "LTC": "LhyQNrqfehN6y7rQj1...MettiIlTuoIndirizzo",
    "USDC": "0x...MettiIlTuoIndirizzoERC20oTRC20"
}

# --- DATABASE PRODOTTI ---
PRODUCTS = {
    "prod_1": {"name": "🍝 Spaghetti Amnesia", "price": 50, "unit": "g"},
    "prod_2": {"name": "🍫 Hashish Carbonara", "price": 12, "unit": "g"}
}

# --- METODI DI SPEDIZIONE ---
SHIPPING_METHODS = {
    "ship_std": {"name": "🇮🇹 Poste Italiane (Standard)", "price": 10},
    "ship_exp": {"name": "🚀 Express Courier (24h)", "price": 20},
    "ship_stl": {"name": "🕵️‍♂️ Stealth Pro (Insurance)", "price": 35}
}

# --- SERVER FAKE PER RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def do_HEAD(self): # Fix per errori log
        self.send_response(200)
        self.end_headers()

def run_fake_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Server fake avviato sulla porta {port}")
    server.serve_forever()

# --- FUNZIONI UTILI ---
def get_crypto_price(crypto_symbol, fiat_amount):
    """Converte EUR in Crypto usando CoinGecko"""
    try:
        # CoinGecko usa id specifici: bitcoin, litecoin, usd-coin
        ids = {"BTC": "bitcoin", "LTC": "litecoin", "USDC": "usd-coin"}
        cg_id = ids.get(crypto_symbol)
        
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=eur"
        response = requests.get(url).json()
        price_in_eur = response[cg_id]['eur']
        
        crypto_amount = fiat_amount / price_in_eur
        return round(crypto_amount, 6) # Arrotonda a 6 decimali
    except Exception as e:
        print(f"Errore API Crypto: {e}")
        return None

# --- GESTIONE BOT ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Logga l'ID dell'utente per permetterti di settare ADMIN_CHAT_ID
    print(f"📢 ID UTENTE CHE HA DIGITATO START: {update.effective_chat.id}")

    if 'cart' not in context.user_data:
        context.user_data['cart'] = {}
    
    # Resetta stati di pagamento
    context.user_data['awaiting_txid'] = False

    text = (
        "Last seen: recently\n"
        "Ships from: 🇮🇹 🇪🇸 🇺🇸 -> 🇪🇺\n"
        "Currency: EUR\n\n"
        "🍝 SPAGHETTIMAFIA SHOP 🍝\n\n"
        "🔔 BEFORE ORDERING -> READ OUR POLICY\n\n"
        "✅ Premium Quality\n✅ Europe Delivery\n✅ Best Prices\n✅ 24/7 Customer Service"
    )

    keyboard = [
        [InlineKeyboardButton("💊 Listings", callback_data="listings")],
        [
            InlineKeyboardButton("📣 OUR POLICY", callback_data="policy"),
            InlineKeyboardButton("📞 Contacts", url=f"https://t.me/{CONTACT_USERNAME}")
        ],
        [InlineKeyboardButton("🛒 Il mio Carrello", callback_data="show_cart")]
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=markup)
    else:
        await update.message.reply_text(text=text, reply_markup=markup)

async def listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = []
    for key, prod in PRODUCTS.items():
        btn_text = f"{prod['name']} - {prod['price']}€/{prod['unit']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"sel_{key}")])
    
    keyboard.append([InlineKeyboardButton("🛒 Vedi Carrello", callback_data="show_cart")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])

    await query.edit_message_text("💊 **LISTINGS**\nSeleziona un prodotto:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = query.data.split("_")[1] + "_" + query.data.split("_")[2]
    product = PRODUCTS[prod_id]
    
    text = f"Hai selezionato: **{product['name']}**\nPrezzo: {product['price']}€ al {product['unit']}.\n\nQuanto ne vuoi?"
    keyboard = [
        [InlineKeyboardButton("1", callback_data=f"add_{prod_id}_1"), InlineKeyboardButton("2", callback_data=f"add_{prod_id}_2"), InlineKeyboardButton("5", callback_data=f"add_{prod_id}_5")],
        [InlineKeyboardButton("10", callback_data=f"add_{prod_id}_10"), InlineKeyboardButton("50", callback_data=f"add_{prod_id}_50")],
        [InlineKeyboardButton("🔙 Torna ai Prodotti", callback_data="listings")]
    ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    prod_id = f"{parts[1]}_{parts[2]}"
    qty = int(parts[3])
    
    cart = context.user_data.get('cart', {})
    cart[prod_id] = cart.get(prod_id, 0) + qty
    context.user_data['cart'] = cart
    
    await query.answer("Aggiunto! ✅")
    await show_cart(update, context)

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    cart = context.user_data.get('cart', {})
    if not cart:
        await (query.edit_message_text if query else update.message.reply_text)(
            "🛒 **Carrello vuoto!**", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Shop", callback_data="listings")]]),
            parse_mode="Markdown"
        )
        return

    text = "🛒 **IL TUO CARRELLO**\n\n"
    total = 0
    for prod_id, qty in cart.items():
        prod = PRODUCTS[prod_id]
        subtotal = prod['price'] * qty
        total += subtotal
        text += f"▪️ {prod['name']} x{qty} = {subtotal}€\n"
    
    context.user_data['cart_total_products'] = total # Salviamo il totale parziale
    text += f"\n💰 **Totale Prodotti: {total}€**"
    
    keyboard = [
        [InlineKeyboardButton("🚚 Procedi alla Spedizione", callback_data="choose_shipping")],
        [InlineKeyboardButton("🗑 Svuota", callback_data="clear_cart"), InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    await (query.edit_message_text if query else update.message.reply_text)(
        text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cart'] = {}
    await show_cart(update, context)

# --- FASE 1: SPEDIZIONE ---
async def choose_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = "🚚 **Scegli il metodo di spedizione:**"
    keyboard = []
    for code, method in SHIPPING_METHODS.items():
        keyboard.append([InlineKeyboardButton(f"{method['name']} (+{method['price']}€)", callback_data=f"ship_{code}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Indietro", callback_data="show_cart")])
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- FASE 2: PAGAMENTO (Scelta Crypto) ---
async def choose_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Se arriva da selezione spedizione, salviamo la scelta
    if query.data.startswith("ship_"):
        ship_code = query.data.replace("ship_", "")
        context.user_data['selected_shipping'] = ship_code
    
    # Calcolo totale finale
    cart_total = context.user_data.get('cart_total_products', 0)
    ship_price = SHIPPING_METHODS[context.user_data['selected_shipping']]['price']
    final_total = cart_total + ship_price
    context.user_data['final_total_eur'] = final_total

    text = (
        f"📦 Spedizione: {SHIPPING_METHODS[context.user_data['selected_shipping']]['name']}\n"
        f"💰 **TOTALE ORDINE: {final_total}€**\n\n"
        "Scegli come vuoi pagare:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🟠 Bitcoin (BTC)", callback_data="pay_BTC")],
        [InlineKeyboardButton("🔵 Litecoin (LTC)", callback_data="pay_LTC")],
        [InlineKeyboardButton("🟢 USDC (ERC20/TRC20)", callback_data="pay_USDC")],
        [InlineKeyboardButton("🔙 Indietro", callback_data="choose_shipping")]
    ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- FASE 3: CHECKOUT E CONVERSIONE ---
async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    crypto_symbol = query.data.replace("pay_", "")
    total_eur = context.user_data['final_total_eur']
    
    await query.edit_message_text(f"🔄 Calcolo cambio {crypto_symbol} in corso...")
    
    # Calcola importo crypto
    crypto_amount = get_crypto_price(crypto_symbol, total_eur)
    
    if crypto_amount is None:
        await query.edit_message_text("❌ Errore nel recupero dei prezzi. Riprova più tardi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Indietro", callback_data="show_cart")]]))
        return

    wallet = WALLETS.get(crypto_symbol, "Errore Wallet")
    
    # Salviamo i dati per la verifica
    context.user_data['pending_order'] = {
        "crypto": crypto_symbol,
        "amount": crypto_amount,
        "wallet": wallet,
        "eur": total_eur
    }
    context.user_data['awaiting_txid'] = True # Attiviamo la modalità "attesa TXID"

    text = (
        f"💳 **PAGAMENTO INIZIATO**\n\n"
        f"Invia esattamente: `{crypto_amount} {crypto_symbol}`\n"
        f"A questo indirizzo:\n`{wallet}`\n\n"
        "⚠️ **IMPORTANTE:**\n"
        "1. Copia indirizzo e importo esatto.\n"
        "2. Effettua il pagamento dal tuo wallet.\n"
        "3. Una volta inviato, **copia l'ID della Transazione (TXID)** e incollalo qui in chat per confermare l'ordine."
    )
    
    # Bottone annulla
    keyboard = [[InlineKeyboardButton("❌ Annulla Ordine", callback_data="main_menu")]]
    
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- FASE 4: RICEZIONE TXID E NOTIFICA ADMIN ---
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Se l'utente non sta aspettando di pagare, ignora o rispondi generico
    if not context.user_data.get('awaiting_txid'):
        return

    txid = update.message.text
    user = update.message.from_user
    order_data = context.user_data.get('pending_order')
    cart = context.user_data.get('cart')
    
    # 1. Conferma all'utente
    await update.message.reply_text(
        "✅ **Transazione Ricevuta!**\n\n"
        "Il nostro team sta verificando la blockchain. Riceverai una notifica di spedizione appena confermato.\n"
        "Grazie per aver scelto Spaghettimafia Shop! 🍝",
        parse_mode="Markdown"
    )
    
    # 2. Resetta carrello e stato
    context.user_data['cart'] = {}
    context.user_data['awaiting_txid'] = False
    
    # 3. CREA MESSAGGIO PER L'ADMIN
    # Formatta la lista prodotti
    cart_text = ""
    for pid, qty in cart.items():
        cart_text += f"- {PRODUCTS[pid]['name']} x{qty}\n"

    admin_msg = (
        f"🚨 **NUOVO ORDINE RICEVUTO!** 🚨\n\n"
        f"👤 Cliente: @{user.username} (ID: {user.id})\n"
        f"💰 Totale: {order_data['eur']}€\n"
        f"💎 Crypto: {order_data['amount']} {order_data['crypto']}\n\n"
        f"🛒 **Articoli:**\n{cart_text}\n"
        f"🚚 Spedizione: {context.user_data['selected_shipping']}\n\n"
        f"🔗 **TXID FORNITO:**\n`{txid}`\n\n"
        "⚠️ Verifica il TXID sulla blockchain e contatta il cliente per spedire."
    )
    
    # Invia notifica all'admin
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"ERRORE INVIO NOTIFICA ADMIN: {e} - Probabilmente ADMIN_CHAT_ID è sbagliato o il bot non ha mai chattato con l'admin.")

# --- ROUTER ---
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "main_menu": await start(update, context)
    elif data == "listings": await listings(update, context)
    elif data == "policy": 
        # (Codice policy di prima, puoi rimetterlo se vuoi, qui l'ho omesso per brevità ma va inserito)
        pass 
    elif data == "show_cart": await show_cart(update, context)
    elif data == "clear_cart": await clear_cart(update, context)
    elif data.startswith("sel_"): await select_quantity(update, context)
    elif data.startswith("add_"): await add_to_cart(update, context)
    
    # NUOVI HANDLER
    elif data == "choose_shipping" or data.startswith("ship_"): 
        if data == "choose_shipping": await choose_shipping(update, context)
        else: await choose_payment(update, context)
    
    elif data.startswith("pay_"): await process_payment(update, context)

def main():
    server_thread = threading.Thread(target=run_fake_server)
    server_thread.daemon = True
    server_thread.start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(router))
    
    # Aggiungi il gestore per i messaggi di testo (per il TXID)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))

    print("Bot avviato su Render ✔️")
    app.run_polling()

if __name__ == "__main__":
    main()