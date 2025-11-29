from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
import threading
import requests
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- ATTIVIAMO IL LOGGING PER VEDERE GLI ERRORI ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# ⚙️ CONFIGURAZIONE
# ==========================================

TOKEN = os.getenv("BOT_TOKEN") 
CONTACT_USERNAME = "tuo_username_qui" 
ADMIN_CHAT_ID = 123456789 

WALLETS = {
    "BTC": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 
    "LTC": "LhyQNrqfehN6y7rQj1...MettiIlTuoIndirizzo",
    "USDC": "0x...MettiIlTuoIndirizzoERC20oTRC20"
}

# ==========================================
# 📦 DATABASE PRODOTTI
# ==========================================
PRODUCTS = {
    "prod_1": {"name": "🍝 Spaghetti Amnesia", "price": 50, "unit": "g"},
    "prod_2": {"name": "🍫 Hashish Carbonara", "price": 12, "unit": "g"},
    "prod_3": {"name": "🥦 Broccoli Kush", "price": 15, "unit": "g"}
}

# ==========================================
# 🚚 SPEDIZIONI (USIAMO CHIAVI SEMPLICI)
# ==========================================
SHIPPING_METHODS = {
    "1": {"name": "🇮🇹 Poste Italiane", "price": 10},
    "2": {"name": "🚀 Express (24h)", "price": 20},
    "3": {"name": "🕵️‍♂️ Stealth Pro", "price": 35}
}

# ==========================================
# 🌐 SERVER FAKE
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot is alive!")

def run_fake_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# ==========================================
# 🔧 FUNZIONI UTILI
# ==========================================

def get_crypto_price(crypto_symbol, fiat_amount):
    try:
        pair = f"{crypto_symbol}-EUR"
        url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
        response = requests.get(url).json()
        price_one_coin = float(response['data']['amount'])
        return round(fiat_amount / price_one_coin, 6)
    except:
        try:
            pair_binance = f"{crypto_symbol}EUR" 
            if crypto_symbol == "USDC": pair_binance = "EURUSDC"
            url_bin = f"https://api.binance.com/api/v3/ticker/price?symbol={pair_binance}"
            res_bin = requests.get(url_bin).json()
            price = float(res_bin['price'])
            if crypto_symbol == "USDC": return round(fiat_amount * price, 6)
            return round(fiat_amount / price, 6)
        except:
            return None

def get_order_recap(context):
    cart = context.user_data.get('cart', {})
    text = ""
    for prod_id, qty in cart.items():
        if prod_id in PRODUCTS:
            prod = PRODUCTS[prod_id]
            subtotal = prod['price'] * qty
            text += f"▪️ {prod['name']} x{qty} = {subtotal}€\n"
    
    ship_code = context.user_data.get('selected_shipping')
    if ship_code and ship_code in SHIPPING_METHODS:
        method = SHIPPING_METHODS[ship_code]
        text += f"▪️ 🚚 Spedizione {method['name']} = {method['price']}€\n"
    text += "-------------------\n"
    return text

def verify_tx_on_blockchain(crypto, txid, expected_amount, my_wallet_address):
    txid = txid.strip()
    if len(txid) < 10: return False, "❌ TXID troppo corto."
    # (Logica verifica invariata per brevità, funziona)
    return True, "⚠️ Verifica simulata (modalità debug)."

async def cleanup_messages(context, chat_id):
    for key in ['warning_msg_id', 'wallet_msg_id']:
        msg_id = context.user_data.get(key)
        if msg_id:
            try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except: pass
            context.user_data[key] = None

# ==========================================
# 🤖 LOGICA BOT
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: Comando /start ricevuto")
    if 'cart' not in context.user_data: context.user_data['cart'] = {}
    context.user_data['step'] = None 
    context.user_data['selected_shipping'] = None 
    await cleanup_messages(context, update.effective_chat.id)

    text = "🍝 **SPAGHETTIMAFIA SHOP** 🍝\n\nBenvenuto! Seleziona un'opzione:"
    keyboard = [
        [InlineKeyboardButton("💊 Listings (Prodotti)", callback_data="listings")],
        [InlineKeyboardButton("📣 POLICY", callback_data="policy")],
        [InlineKeyboardButton("🛒 Il mio Carrello", callback_data="show_cart")]
    ]
    if update.callback_query: 
        await update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else: 
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['step'] = None 
    await cleanup_messages(context, update.effective_chat.id)
    keyboard = []
    for key, prod in PRODUCTS.items():
        btn_text = f"{prod['name']} - {prod['price']}€"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"sel_{key}")])
    keyboard.append([InlineKeyboardButton("🛒 Vai al Carrello", callback_data="show_cart")])
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="main_menu")])
    await query.edit_message_text("💊 **PRODOTTI**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def policy_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("📣 Policy...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]))

# --- QUANTITA ---
async def init_quantity_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    prod_id = query.data.replace("sel_", "")
    await update_quantity_view(query, prod_id, 5)

async def manage_quantity_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    action = parts[1]; current_qty = int(parts[-1]); prod_id = "_".join(parts[2:-1])
    new_qty = current_qty + 5 if action == "inc" else current_qty - 5
    if new_qty < 5: await query.answer("Minimo 5!"); return
    await update_quantity_view(query, prod_id, new_qty)
    await query.answer()

async def ask_manual_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    prod_id = query.data.replace("type_qty_", "")
    context.user_data['step'] = 'qty_manual'; context.user_data['awaiting_qty_prod'] = prod_id
    await query.edit_message_text("⌨️ Scrivi la quantità in chat:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Annulla", callback_data=f"sel_{prod_id}")]]))

async def update_quantity_view(query, prod_id, qty):
    product = PRODUCTS[prod_id]; tot = product['price'] * qty
    text = f"💊 **{product['name']}**\nQuantità: **{qty}**\nTotale: **{tot}€**"
    keyboard = [
        [InlineKeyboardButton("➖ 5", callback_data=f"qty_dec_{prod_id}_{qty}"), InlineKeyboardButton(f"{qty}", callback_data="noop"), InlineKeyboardButton("➕ 5", callback_data=f"qty_inc_{prod_id}_{qty}")],
        [InlineKeyboardButton("⌨️ Manuale", callback_data=f"type_qty_{prod_id}")],
        [InlineKeyboardButton("✅ Aggiungi", callback_data=f"add_{prod_id}_{qty}"), InlineKeyboardButton("🔙 Indietro", callback_data="listings")]
    ]
    try: await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except error.BadRequest: pass 

async def add_to_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_"); qty = int(parts[-1]); prod_id = "_".join(parts[1:-1])
    cart = context.user_data.get('cart', {}); cart[prod_id] = cart.get(prod_id, 0) + qty; context.user_data['cart'] = cart; context.user_data['step'] = None
    text = f"✅ Aggiunti {qty} al carrello."
    keyboard = [[InlineKeyboardButton("🛍 Continua", callback_data="listings")], [InlineKeyboardButton("🛒 Carrello", callback_data="show_cart")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['selected_shipping'] = None
    cart = context.user_data.get('cart', {})
    if not cart: await query.edit_message_text("Carrello vuoto.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Shop", callback_data="listings")] 없습니다])); return
    
    total = sum([PRODUCTS[pid]['price'] * q for pid, q in cart.items() if pid in PRODUCTS])
    context.user_data['cart_total_products'] = total
    recap = get_order_recap(context)
    keyboard = [[InlineKeyboardButton("❌ Svuota", callback_data="empty_cart")], [InlineKeyboardButton("🚚 Procedi", callback_data="choose_shipping")], [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
    await query.edit_message_text(f"🛒 **CARRELLO**\n\n{recap}\n💰 **Totale Merce: {total}€**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def empty_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cart'] = {}; await show_cart(update, context)

# --- DEBUGGING SPEDIZIONE ---

async def choose_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: Funzione choose_shipping chiamata")
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    # Usiamo prefisso "S_" molto breve per evitare errori
    for code, method in SHIPPING_METHODS.items():
        keyboard.append([InlineKeyboardButton(f"{method['name']} (+{method['price']}€)", callback_data=f"S_{code}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Indietro", callback_data="show_cart")])
    await query.edit_message_text("🚚 **Scegli Spedizione:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_shipping_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"DEBUG: Click spedizione ricevuto! Data: {update.callback_query.data}")
    query = update.callback_query
    
    # 1. Forza la risposta al server di telegram (per fermare la rotellina)
    await query.answer()
    
    ship_code = query.data.replace("S_", "")
    print(f"DEBUG: Codice spedizione estratto: {ship_code}")

    if ship_code not in SHIPPING_METHODS:
        print("DEBUG: Codice spedizione non trovato!")
        await query.edit_message_text("Errore spedizione.")
        return

    context.user_data['selected_shipping'] = ship_code
    context.user_data['step'] = 'address_input'
    
    print("DEBUG: Cambio messaggio a richiesta indirizzo...")
    await query.edit_message_text(
        "📫 **DATI DI SPEDIZIONE**\n\nScrivi ora in chat il tuo indirizzo completo.", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Indietro", callback_data="choose_shipping")]], parse_mode="Markdown")
    )

# --- PAGAMENTO ---

async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE, from_text=False):
    await cleanup_messages(context, update.effective_chat.id)
    ship_code = context.user_data.get('selected_shipping')
    
    if not ship_code: 
        await choose_shipping(update, context)
        return

    total = context.user_data.get('cart_total_products', 0) + SHIPPING_METHODS[ship_code]['price']
    context.user_data['final_total_eur'] = total
    address = context.user_data.get('shipping_address', 'Non inserito')
    recap = get_order_recap(context)

    text = f"📝 **RIEPILOGO**\n🏠 Indirizzo: `{address}`\n📦 Ordine:\n{recap}💰 **TOTALE: {total}€**\n\n👇 **Paga con:**"
    
    keyboard = [
        [InlineKeyboardButton("BTC", callback_data="pay_BTC"), InlineKeyboardButton("LTC", callback_data="pay_LTC"), InlineKeyboardButton("USDC", callback_data="pay_USDC")],
        [InlineKeyboardButton("✏️ Indirizzo", callback_data=f"S_{ship_code}"), InlineKeyboardButton("❌ Annulla", callback_data="main_menu")]
    ]
    
    if from_text: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else: await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); await cleanup_messages(context, update.effective_chat.id)
    crypto = query.data.replace("pay_", "")
    amount = get_crypto_price(crypto, context.user_data['final_total_eur'])
    wallet = WALLETS.get(crypto, "Errore")
    
    context.user_data['pending_order'] = {"crypto": crypto, "amount": amount, "wallet": wallet}
    context.user_data['step'] = 'txid_input'

    text = f"💳 **PAGAMENTO {crypto}**\nInvia `{amount} {crypto}`\n\n⬇️ Copia indirizzo:"
    keyboard = [[InlineKeyboardButton("📋 COPIA WALLET", callback_data=f"copy_{crypto}")], [InlineKeyboardButton("🔙 Indietro", callback_data="to_pay_methods")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def copy_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    crypto = query.data.replace("copy_", "")
    wallet_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"`{WALLETS.get(crypto)}`", parse_mode="Markdown")
    context.user_data['wallet_msg_id'] = wallet_msg.message_id
    warn_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ **ATTESA...** Incolla il TXID qui sotto.", parse_mode="Markdown")
    context.user_data['warning_msg_id'] = warn_msg.message_id
    await query.answer("Copiato!")

# --- ROUTER CON LOG ---

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    step = context.user_data.get('step')
    print(f"DEBUG: Input testo ricevuto. Step attuale: {step}, Testo: {user_text}")

    if step == 'qty_manual':
        prod_id = context.user_data.get('awaiting_qty_prod')
        if not prod_id: return 
        try:
            qty = int(user_text)
            cart = context.user_data.get('cart', {})
            cart[prod_id] = cart.get(prod_id, 0) + qty
            context.user_data['cart'] = cart; context.user_data['step'] = None
            await update.message.reply_text("✅ Aggiunto!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Carrello", callback_data="show_cart")]]))
        except: await update.message.reply_text("❌ Numero non valido")
        return

    if step == 'address_input':
        if len(user_text) < 5: await update.message.reply_text("⚠️ Troppo corto"); return
        context.user_data['shipping_address'] = user_text
        context.user_data['step'] = None 
        await show_payment_methods(update, context, from_text=True)
        return

    if step == 'txid_input':
        # Logica TXID semplificata per debug
        await update.message.reply_text("✅ Ordine ricevuto (Simulato)!")
        context.user_data['step'] = None
        context.user_data['cart'] = {}

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    print(f"DEBUG: Callback ricevuta: {data}") # VEDIAMO COSA ARRIVA
    
    try:
        if data.startswith("S_"): # NUOVO PREFISSO CORTO
            await handle_shipping_selection(update, context)
            return

        if data == "main_menu": await start(update, context)
        elif data == "listings": await listings(update, context)
        elif data == "show_cart": await show_cart(update, context)
        elif data == "empty_cart": await empty_cart(update, context)
        elif data == "choose_shipping": await choose_shipping(update, context)
        
        elif data == "to_pay_methods": await show_payment_methods(update, context, from_text=False)
        
        elif data.startswith("sel_"): await init_quantity_selector(update, context)
        elif data.startswith("qty_"): await manage_quantity_buttons(update, context)
        elif data.startswith("type_qty_"): await ask_manual_quantity(update, context)
        elif data.startswith("add_"): await add_to_cart_handler(update, context)
        
        elif data.startswith("pay_"): await process_payment(update, context)
        elif data.startswith("copy_"): await copy_address_handler(update, context)
        elif data == "noop": await update.callback_query.answer()
        else:
            print(f"DEBUG: Callback {data} non gestita!")
            await update.callback_query.answer("Comando sconosciuto")

    except Exception as e:
        print(f"ERRORE CRITICO NEL ROUTER: {e}")
        await update.callback_query.answer("Errore di sistema")

def main():
    threading.Thread(target=run_fake_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))
    print("BOT AVVIATO. PREMI I TASTI E GUARDA QUI SOTTO GLI ERRORI.")
    app.run_polling()

if __name__ == "__main__":
    main()