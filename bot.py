from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("BOT_TOKEN")
CONTACT_USERNAME = "CHEFTONY_OG" 

# IL TUO CHAT ID
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
    "prod_3": {"name": "🥦 Broccoli Kush", "price": 15, "unit": "g"}
}

# --- SPEDIZIONI ---
SHIPPING_METHODS = {
    "std": {"name": "🇮🇹 Poste Italiane", "price": 10},
    "exp": {"name": "🚀 Express (24h)", "price": 20},
    "stl": {"name": "🕵️‍♂️ Stealth Pro", "price": 35}
}

# --- SERVER FAKE ---
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
    server.serve_forever()

# --- FUNZIONE CAMBIO (API COINBASE) ---
def get_crypto_price(crypto_symbol, fiat_amount):
    try:
        pair = f"{crypto_symbol}-EUR"
        url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
        response = requests.get(url).json()
        price_one_coin = float(response['data']['amount'])
        return round(fiat_amount / price_one_coin, 6)
    except Exception as e:
        print(f"ERRORE API COINBASE: {e}")
        try:
            print("Tentativo con Binance...")
            pair_binance = f"{crypto_symbol}EUR" 
            if crypto_symbol == "USDC": pair_binance = "EURUSDC"
            url_bin = f"https://api.binance.com/api/v3/ticker/price?symbol={pair_binance}"
            res_bin = requests.get(url_bin).json()
            price = float(res_bin['price'])
            if crypto_symbol == "USDC": return round(fiat_amount * price, 6)
            return round(fiat_amount / price, 6)
        except:
            return None

# --- LOGICA BOT ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📢 ID UTENTE: {update.effective_chat.id}")
    if 'cart' not in context.user_data: context.user_data['cart'] = {}
    context.user_data['awaiting_txid'] = False
    context.user_data['awaiting_qty_prod'] = None 

    text = (
        "Last seen: recently\nShips from: 🇮🇹 🇪🇸 🇺🇸 -> 🇪🇺\nCurrency: EUR\n\n"
        "🍝 SPAGHETTIMAFIA SHOP 🍝\n\n🔔 BEFORE ORDERING -> READ OUR POLICY\n\n"
        "✅ Premium Quality\n✅ Europe Delivery\n✅ Best Prices"
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
    context.user_data['awaiting_qty_prod'] = None 

    keyboard = []
    for key, prod in PRODUCTS.items():
        btn_text = f"{prod['name']} - {prod['price']}€/{prod['unit']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"sel_{key}")])
    
    keyboard.append([InlineKeyboardButton("🛒 Vai al Carrello", callback_data="show_cart")])
    keyboard.append([InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")])
    await query.edit_message_text("💊 **LISTINGS**\nScegli un prodotto:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- SELETTORE QUANTITÀ ---

async def init_quantity_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = query.data.split("_")[1] + "_" + query.data.split("_")[2]
    await update_quantity_view(query, prod_id, 5)

async def manage_quantity_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    action = parts[1]
    prod_id = f"{parts[2]}_{parts[3]}"
    current_qty = int(parts[4])
    new_qty = current_qty + 5 if action == "inc" else current_qty - 5
    
    if new_qty < 5:
        await query.answer("Minimo 5!")
        return

    await update_quantity_view(query, prod_id, new_qty)
    await query.answer()

async def ask_manual_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = query.data.replace("type_qty_", "")
    context.user_data['awaiting_qty_prod'] = prod_id
    prod_name = PRODUCTS[prod_id]['name']
    
    await query.edit_message_text(
        f"⌨️ **SCRIVI LA QUANTITÀ**\nProdotto: **{prod_name}**\n\nScrivi un numero intero qui sotto (es: 25) e invia.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Annulla", callback_data=f"sel_{prod_id}")]])
    )

async def update_quantity_view(query, prod_id, qty):
    product = PRODUCTS[prod_id]
    tot_price = product['price'] * qty
    text = (
        f"💊 **{product['name']}**\nPrezzo: {product['price']}€/{product['unit']}\n\n"
        f"🔢 Quantità: **{qty} {product['unit']}**\n💰 Totale Parziale: **{tot_price}€**"
    )
    keyboard = [
        [
            InlineKeyboardButton("➖ 5", callback_data=f"qty_dec_{prod_id}_{qty}"), 
            InlineKeyboardButton(f" {qty} ", callback_data="noop"),
            InlineKeyboardButton("➕ 5", callback_data=f"qty_inc_{prod_id}_{qty}")
        ],
        [InlineKeyboardButton("⌨️ Scrivi a mano", callback_data=f"type_qty_{prod_id}")],
        [InlineKeyboardButton(f"✅ Aggiungi {qty} al Carrello", callback_data=f"add_{prod_id}_{qty}")],
        [InlineKeyboardButton("🔙 Torna ai Prodotti", callback_data="listings")]
    ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def add_to_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    prod_id = f"{parts[1]}_{parts[2]}"
    qty = int(parts[3])
    text, markup = add_to_cart_logic(context, prod_id, qty)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode="Markdown")

def add_to_cart_logic(context, prod_id, qty):
    cart = context.user_data.get('cart', {})
    cart[prod_id] = cart.get(prod_id, 0) + qty
    context.user_data['cart'] = cart
    context.user_data['awaiting_qty_prod'] = None
    
    product_name = PRODUCTS[prod_id]['name']
    text = f"✅ Aggiunti **{qty}** di **{product_name}** al carrello!\n\nCosa vuoi fare ora?"
    keyboard = [
        [InlineKeyboardButton("🛍 Continua Shopping", callback_data="listings")],
        [InlineKeyboardButton("🛒 Vai al Carrello", callback_data="show_cart")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

# --- CARRELLO ---
async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    context.user_data['awaiting_qty_prod'] = None 

    cart = context.user_data.get('cart', {})
    if not cart:
        await (query.edit_message_text if query else update.message.reply_text)(
            "🛒 **Carrello vuoto!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Shop", callback_data="listings")]]), parse_mode="Markdown"
        )
        return

    text = "🛒 **IL TUO CARRELLO**\n\n"
    total = 0
    keyboard = []
    for prod_id, qty in cart.items():
        prod = PRODUCTS[prod_id]
        subtotal = prod['price'] * qty
        total += subtotal
        text += f"▪️ {prod['name']} x{qty} = {subtotal}€\n"
        keyboard.append([InlineKeyboardButton(f"❌ Rimuovi {prod['name']}", callback_data=f"rem_{prod_id}")])
    
    context.user_data['cart_total_products'] = total
    text += f"\n💰 **Totale Merce: {total}€**"
    
    keyboard.append([InlineKeyboardButton("🚚 Procedi alla Spedizione", callback_data="choose_shipping")])
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="main_menu")])

    await (query.edit_message_text if query else update.message.reply_text)(
        text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    prod_id = query.data.replace("rem_", "")
    cart = context.user_data.get('cart', {})
    if prod_id in cart: del cart[prod_id]
    context.user_data['cart'] = cart
    await show_cart(update, context)

# --- CHECKOUT ---
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
        context.user_data['selected_shipping'] = query.data.split("_")[1]
    
    ship_code = context.user_data.get('selected_shipping')
    cart = context.user_data.get('cart', {})
    
    if ship_code not in SHIPPING_METHODS or not cart:
        await choose_shipping(update, context)
        return

    total = context.user_data.get('cart_total_products', 0) + SHIPPING_METHODS[ship_code]['price']
    context.user_data['final_total_eur'] = total
    ship_name = SHIPPING_METHODS[ship_code]['name']

    prod_txt = "\n".join([f"▪️ {PRODUCTS[pid]['name']} (x{qty})" for pid, qty in cart.items()])

    text = (
        "🧾 **RIEPILOGO ORDINE**\n\n"
        f"{prod_txt}\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"📦 Sped: {ship_name}\n"
        f"💰 **DA PAGARE: {total}€**\n\n"
        "Scegli metodo di pagamento:"
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
        await query.edit_message_text("❌ Errore API Crypto.\nControlla i log.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Indietro", callback_data="show_cart")]]))
        return

    wallet = WALLETS.get(crypto, "Chiedere in chat")
    context.user_data['pending_order'] = {"crypto": crypto, "amount": amount, "wallet": wallet, "eur": eur}
    context.user_data['awaiting_txid'] = True
    
    # Recuperiamo il codice spedizione per usarlo nel tasto indietro
    ship_code = context.user_data.get('selected_shipping')

    text = (
        f"💳 **PAGAMENTO {crypto}**\n\n"
        f"Invia esattamente: `{amount} {crypto}`\n"
        f"Address:\n`{wallet}`\n\n"
        "⬇️ **APPENA INVIATO:**\nCopia il **TXID** e incollalo qui in chat."
    )
    
    # MODIFICA RICHIESTA: TASTO INDIETRO AGGIUNTO
    keyboard = [
        [InlineKeyboardButton("🔙 Cambia Metodo di Pagamento", callback_data=f"ship_{ship_code}")],
        [InlineKeyboardButton("❌ Annulla Ordine", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- INPUT TESTO ---
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if context.user_data.get('awaiting_qty_prod'):
        prod_id = context.user_data['awaiting_qty_prod']
        try:
            qty = int(user_text)
            if qty <= 0: raise ValueError
            text, markup = add_to_cart_logic(context, prod_id, qty)
            await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Numero non valido. Scrivi un numero intero (es: 10).")
        return

    if context.user_data.get('awaiting_txid'):
        txid = user_text
        user = update.message.from_user
        order = context.user_data['pending_order']
        cart = context.user_data['cart']
        
        ship_key = context.user_data.get('selected_shipping', 'std')
        ship = SHIPPING_METHODS.get(ship_key, {'name': 'Unknown'})['name']
        
        await update.message.reply_text("✅ **Ordine Ricevuto!**\nVerifica in corso.", parse_mode="Markdown")
        
        cart_txt = "\n".join([f"- {PRODUCTS[pid]['name']} x{qty}" for pid, qty in cart.items()])
        admin_msg = (
            f"🚨 **NUOVO ORDINE** 🚨\n👤 @{user.username} (ID: {user.id})\n"
            f"💶 {order['eur']}€  -> 🪙 {order['amount']} {order['crypto']}\n\n"
            f"🛒 **Articoli:**\n{cart_txt}\n\n🚚 {ship}\n\n🔗 **TXID:**\n`{txid}`"
        )
        try: await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown")
        except: print("⚠️ Errore notifica Admin")
        
        context.user_data['cart'] = {}
        context.user_data['awaiting_txid'] = False
        context.user_data['pending_order'] = None

# --- MAIN ---
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "main_menu": await start(update, context)
    elif data == "listings": await listings(update, context)
    elif data == "policy": 
        await update.callback_query.edit_message_text("📣 **OUR POLICY**\n\nPolicy...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]))
    elif data == "show_cart": await show_cart(update, context)
    elif data == "noop": await update.callback_query.answer()
    
    elif data.startswith("sel_"): await init_quantity_selector(update, context)
    elif data.startswith("qty_"): await manage_quantity_buttons(update, context)
    elif data.startswith("type_qty_"): await ask_manual_quantity(update, context)
    elif data.startswith("add_"): await add_to_cart_handler(update, context)
    elif data.startswith("rem_"): await remove_item(update, context)
    
    elif data == "choose_shipping" or data.startswith("ship_"): 
        if data == "choose_shipping": await choose_shipping(update, context)
        else: await choose_payment(update, context)
    elif data.startswith("pay_"): await process_payment(update, context)

def main():
    threading.Thread(target=run_fake_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))
    print("Bot avviato su Render ✔️")
    app.run_polling()

if __name__ == "__main__":
    main()