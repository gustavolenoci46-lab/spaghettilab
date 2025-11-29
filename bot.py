from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("BOT_TOKEN")
CONTACT_USERNAME = "CHEFTONY_OG"  # Metti il tuo username senza @

# IMPORTANTE: Inserisci qui il tuo Chat ID Numerico (lo vedi nei log all'avvio)
ADMIN_CHAT_ID = 123456789 

# I TUOI WALLET
WALLETS = {
    "BTC": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 
    "LTC": "LhyQNrqfehN6y7rQj1...MettiIlTuoIndirizzo",
    "USDC": "0x...MettiIlTuoIndirizzoERC20oTRC20"
}

# --- DATABASE PRODOTTI ---
PRODUCTS = {
    "prod_1": {"name": "🍝 Spaghetti Amnesia", "price": 50, "unit": "g"},
    "prod_2": {"name": "🍫 Hashish Carbonara", "price": 12, "unit": "g"},
    "prod_3": {"name": "🥦 Broccoli Kush", "price": 15, "unit": "g"} # Aggiunto prodotto per test
}

# --- METODI DI SPEDIZIONE ---
SHIPPING_METHODS = {
    "std": {"name": "🇮🇹 Poste Italiane (Standard)", "price": 10},
    "exp": {"name": "🚀 Express Courier (24h)", "price": 20},
    "stl": {"name": "🕵️‍♂️ Stealth Pro (Insurance)", "price": 35}
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

# --- UTILS ---
def get_crypto_price(crypto_symbol, fiat_amount):
    try:
        ids = {"BTC": "bitcoin", "LTC": "litecoin", "USDC": "usd-coin"}
        cg_id = ids.get(crypto_symbol)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=eur"
        response = requests.get(url).json()
        price_in_eur = response[cg_id]['eur']
        return round(fiat_amount / price_in_eur, 6)
    except:
        return None

# --- BOT LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📢 ID UTENTE: {update.effective_chat.id}") # Copia questo ID per ADMIN_CHAT_ID
    if 'cart' not in context.user_data: context.user_data['cart'] = {}
    context.user_data['awaiting_txid'] = False

    text = (
        "Last seen: recently\nShips from: 🇮🇹 🇪🇸 🇺🇸 -> 🇪🇺\nCurrency: EUR\n\n"
        "🍝 SPAGHETTIMAFIA SHOP 🍝\n\n🔔 BEFORE ORDERING -> READ OUR POLICY\n\n"
        "✅ Premium Quality\n✅ Europe Delivery\n✅ Best Prices\n✅ 24/7 Customer Service"
    )
    keyboard = [
        [InlineKeyboardButton("💊 Listings (Prodotti)", callback_data="listings")],
        [InlineKeyboardButton("📣 POLICY", callback_data="policy"), InlineKeyboardButton("📞 Contacts", url=f"https://t.me/{CONTACT_USERNAME}")],
        [InlineKeyboardButton("🛒 Il mio Carrello", callback_data="show_cart")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query: await update.callback_query.edit_message_text(text=text, reply_markup=markup)
    else: await update.message.reply_text(text=text, reply_markup=markup)

async def listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = []
    for key, prod in PRODUCTS.items():
        btn_text = f"{prod['name']} - {prod['price']}€/{prod['unit']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"sel_{key}")])
    
    keyboard.append([InlineKeyboardButton("🛒 Vai al Carrello", callback_data="show_cart")])
    keyboard.append([InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")])
    await query.edit_message_text("💊 **LISTINGS**\nScegli un prodotto da aggiungere:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = query.data.split("_")[1] + "_" + query.data.split("_")[2]
    product = PRODUCTS[prod_id]
    
    text = f"Hai scelto: **{product['name']}**\nPrezzo: {product['price']}€ al {product['unit']}.\n\nQuanto ne vuoi aggiungere?"
    keyboard = [
        [InlineKeyboardButton("1", callback_data=f"add_{prod_id}_1"), InlineKeyboardButton("2", callback_data=f"add_{prod_id}_2"), InlineKeyboardButton("5", callback_data=f"add_{prod_id}_5")],
        [InlineKeyboardButton("10", callback_data=f"add_{prod_id}_10"), InlineKeyboardButton("50", callback_data=f"add_{prod_id}_50")],
        [InlineKeyboardButton("🔙 Indietro", callback_data="listings")]
    ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    prod_id = f"{parts[1]}_{parts[2]}"
    qty = int(parts[3])
    
    cart = context.user_data.get('cart', {})
    # Accumula quantità se il prodotto esiste già
    cart[prod_id] = cart.get(prod_id, 0) + qty
    context.user_data['cart'] = cart
    
    product_name = PRODUCTS[prod_id]['name']
    
    text = f"✅ Aggiunti **{qty}** di **{product_name}** al carrello!\n\nCosa vuoi fare ora?"
    keyboard = [
        [InlineKeyboardButton("🛍 Continua Shopping (Aggiungi altro)", callback_data="listings")],
        [InlineKeyboardButton("🛒 Vai al Carrello (Paga)", callback_data="show_cart")]
    ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    cart = context.user_data.get('cart', {})
    
    if not cart:
        await (query.edit_message_text if query else update.message.reply_text)(
            "🛒 **Il tuo carrello è vuoto!**", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Torna allo Shop", callback_data="listings")]]),
            parse_mode="Markdown"
        )
        return

    text = "🛒 **IL TUO CARRELLO**\n\n"
    total = 0
    keyboard = []

    # Genera lista prodotti con tasto Rimuovi per ognuno
    for prod_id, qty in cart.items():
        prod = PRODUCTS[prod_id]
        subtotal = prod['price'] * qty
        total += subtotal
        text += f"▪️ {prod['name']} x{qty} = {subtotal}€\n"
        
        # Tasto per rimuovere il singolo prodotto
        keyboard.append([InlineKeyboardButton(f"❌ Rimuovi {prod['name']}", callback_data=f"rem_{prod_id}")])
    
    context.user_data['cart_total_products'] = total
    text += f"\n💰 **Totale parziale: {total}€**"
    
    # Tasti azione finali
    keyboard.append([InlineKeyboardButton("🚚 Procedi alla Spedizione", callback_data="choose_shipping")])
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]) # Tolto "Svuota tutto" per pulizia, si usa il tasto rimuovi singolo

    await (query.edit_message_text if query else update.message.reply_text)(
        text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    prod_id = query.data.replace("rem_", "")
    
    cart = context.user_data.get('cart', {})
    if prod_id in cart:
        del cart[prod_id]
        context.user_data['cart'] = cart
        await query.answer("Prodotto rimosso!")
    else:
        await query.answer("Prodotto già rimosso.")
    
    await show_cart(update, context)

# --- SPEDIZIONE & PAGAMENTO ---
async def choose_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "🚚 **Scegli spedizione:**"
    keyboard = []
    for code, method in SHIPPING_METHODS.items():
        keyboard.append([InlineKeyboardButton(f"{method['name']} (+{method['price']}€)", callback_data=f"ship_{code}")])
    keyboard.append([InlineKeyboardButton("🔙 Indietro", callback_data="show_cart")])
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def choose_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("ship_"):
        ship_code = query.data.split("_")[1]
        context.user_data['selected_shipping'] = ship_code
    
    ship_code = context.user_data.get('selected_shipping')
    if ship_code not in SHIPPING_METHODS:
         # Fallback se c'è errore
        await choose_shipping(update, context)
        return

    total_prod = context.user_data.get('cart_total_products', 0)
    ship_price = SHIPPING_METHODS[ship_code]['price']
    final_total = total_prod + ship_price
    context.user_data['final_total_eur'] = final_total

    text = (
        f"📦 Spedizione: {SHIPPING_METHODS[ship_code]['name']}\n"
        f"💰 **TOTALE ORDINE: {final_total}€**\n\nScegli metodo di pagamento:"
    )
    keyboard = [
        [InlineKeyboardButton("🟠 Bitcoin (BTC)", callback_data="pay_BTC")],
        [InlineKeyboardButton("🔵 Litecoin (LTC)", callback_data="pay_LTC")],
        [InlineKeyboardButton("🟢 USDC (ERC20/TRC20)", callback_data="pay_USDC")],
        [InlineKeyboardButton("🔙 Indietro", callback_data="choose_shipping")]
    ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    crypto = query.data.replace("pay_", "")
    eur = context.user_data['final_total_eur']
    
    await query.edit_message_text(f"🔄 Calcolo cambio {crypto}...")
    amount = get_crypto_price(crypto, eur)
    
    if not amount:
        await query.edit_message_text("❌ Errore cambio. Riprova.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Indietro", callback_data="show_cart")]]))
        return

    wallet = WALLETS.get(crypto, "Chiedere in chat")
    context.user_data['pending_order'] = {"crypto": crypto, "amount": amount, "wallet": wallet, "eur": eur}
    context.user_data['awaiting_txid'] = True

    text = (
        f"💳 **PAGAMENTO {crypto}**\n\nInvia esattamente: `{amount} {crypto}`\n"
        f"All'indirizzo:\n`{wallet}`\n\n"
        "⬇️ **APPENA INVIATO:**\nCopia il **TXID** (ID Transazione) e incollalo qui in chat per confermare l'ordine."
    )
    keyboard = [[InlineKeyboardButton("❌ Annulla", callback_data="main_menu")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_txid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_txid'): return
    
    txid = update.message.text
    user = update.message.from_user
    order = context.user_data['pending_order']
    cart = context.user_data['cart']
    ship = SHIPPING_METHODS[context.user_data['selected_shipping']]['name']
    
    await update.message.reply_text("✅ **Ordine Ricevuto!**\nStiamo verificando il pagamento. A breve riceverai conferma.", parse_mode="Markdown")
    
    cart_txt = "\n".join([f"- {PRODUCTS[pid]['name']} x{qty}" for pid, qty in cart.items()])
    
    admin_msg = (
        f"🚨 **NUOVO ORDINE** 🚨\n👤 @{user.username} (ID: {user.id})\n"
        f"💶 {order['eur']}€  -> 🪙 {order['amount']} {order['crypto']}\n\n"
        f"🛒 **Articoli:**\n{cart_txt}\n\n🚚 {ship}\n\n🔗 **TXID:**\n`{txid}`"
    )
    try: await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown")
    except: print("⚠️ Errore invio notifica Admin")

    context.user_data['cart'] = {}
    context.user_data['awaiting_txid'] = False

async def policy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text(
        "📣 **OUR POLICY**\n\nSpedizioni rapide, pacchi anonimi.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]), parse_mode="Markdown"
    )

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "main_menu": await start(update, context)
    elif data == "listings": await listings(update, context)
    elif data == "policy": await policy(update, context)
    elif data == "show_cart": await show_cart(update, context)
    elif data.startswith("sel_"): await select_quantity(update, context)
    elif data.startswith("add_"): await add_to_cart(update, context)
    elif data.startswith("rem_"): await remove_item(update, context) # Nuovo handler rimozione
    elif data == "choose_shipping" or data.startswith("ship_"): 
        if data == "choose_shipping": await choose_shipping(update, context)
        else: await choose_payment(update, context)
    elif data.startswith("pay_"): await process_payment(update, context)

def main():
    threading.Thread(target=run_fake_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_txid))
    print("Bot avviato su Render ✔️")
    app.run_polling()

if __name__ == "__main__":
    main()