from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
import threading
import requests
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# ⚙️ CONFIGURAZIONE
# ==========================================

TOKEN = os.getenv("BOT_TOKEN") 
CONTACT_USERNAME = "CHEFTONY_OG" 
ADMIN_CHAT_ID = 123456789 

WALLETS = {
    "BTC": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 
    "LTC": "LhyQNrqfehN6y7rQj1...MettiIlTuoIndirizzo",
    "USDC": "0x...MettiIlTuoIndirizzoERC20oTRC20"
}

# ==========================================
# 📦 PRODOTTI
# ==========================================
PRODUCTS = {
    "prod_1": {"name": "🍝 Spaghetti Amnesia", "price": 50, "unit": "g"},
    "prod_2": {"name": "🍫 Hashish Carbonara", "price": 12, "unit": "g"},
    "prod_3": {"name": "🥦 Broccoli Kush", "price": 15, "unit": "g"}
}

# ==========================================
# 🚚 SPEDIZIONI
# ==========================================
SHIPPING_METHODS = {
    "std": {"name": "🇮🇹 Poste Italiane", "price": 10},
    "exp": {"name": "🚀 Express (24h)", "price": 20},
    "stl": {"name": "🕵️‍♂️ Stealth Pro", "price": 35}
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
    # Simulazione OK
    return True, "✅ Verifica OK"

async def cleanup_messages(context, chat_id):
    """Pulisce i messaggi temporanei."""
    for key in ['warning_msg_id', 'wallet_msg_id', 'address_req_id']:
        msg_id = context.user_data.get(key)
        if msg_id:
            try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except: pass
            context.user_data[key] = None

# ==========================================
# 🤖 LOGICA BOT
# ==========================================

async def safe_send(context, chat_id, text, reply_markup):
    """Invia messaggi in modo sicuro senza Markdown per evitare crash."""
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: Start")
    if 'cart' not in context.user_data: context.user_data['cart'] = {}
    context.user_data['step'] = None 
    context.user_data['selected_shipping'] = None 
    await cleanup_messages(context, update.effective_chat.id)

    text = (
        "Last seen: recently\n"
        "Ships from: 🇮🇹 🇪🇸 🇺🇸 -> 🇪🇺\n"
        "Currency: EUR\n\n"
        "🍝 **SPAGHETTIMAFIA SHOP** 🍝\n\n"
        "🔔 BEFORE ORDERING -> READ OUR POLICY\n\n"
        "✅ Premium Quality\n"
        "✅ Europe Delivery\n"
        "✅ Best Prices"
    )
    keyboard = [
        [InlineKeyboardButton("💊 Listings (Prodotti)", callback_data="listings")],
        [InlineKeyboardButton("📣 POLICY", callback_data="policy"), InlineKeyboardButton("📞 Contacts", url=f"https://t.me/{CONTACT_USERNAME}")],
        [InlineKeyboardButton("🛒 Il mio Carrello", callback_data="show_cart")]
    ]
    
    if update.callback_query:
        # Qui usiamo markdown perché il testo è statico e sicuro
        await update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['step'] = None 
    await cleanup_messages(context, update.effective_chat.id)

    keyboard = []
    for key, prod in PRODUCTS.items():
        btn_text = f"{prod['name']} - {prod['price']}€/{prod['unit']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"sel_{key}")])
    
    keyboard.append([InlineKeyboardButton("🛒 Vai al Carrello", callback_data="show_cart")])
    keyboard.append([InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")])
    
    await query.edit_message_text("💊 **LISTINGS**\nScegli un prodotto:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def policy_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    text = "📣 **OUR POLICY**\n\n1. No refunds without video opening.\n2. Shipping time 2-5 days.\n3. Be polite."
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- QUANTITA' ---

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
    
    prod_name = PRODUCTS[prod_id]['name']
    await query.edit_message_text(
        f"⌨️ **QUANTITÀ MANUALE**\n\nProdotto: **{prod_name}**\nScrivi in chat il numero esatto (es. 25) e invia.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Annulla", callback_data=f"sel_{prod_id}")]])
    )

async def update_quantity_view(query, prod_id, qty):
    product = PRODUCTS[prod_id]; tot = product['price'] * qty
    text = f"💊 **{product['name']}**\nPrezzo: {product['price']}€/{product['unit']}\n\n🔢 Quantità: **{qty} {product['unit']}**\n💰 Totale Parziale: **{tot}€**"
    keyboard = [
        [InlineKeyboardButton("➖ 5", callback_data=f"qty_dec_{prod_id}_{qty}"), InlineKeyboardButton(f"{qty}", callback_data="noop"), InlineKeyboardButton("➕ 5", callback_data=f"qty_inc_{prod_id}_{qty}")],
        [InlineKeyboardButton("⌨️ Scrivi a mano", callback_data=f"type_qty_{prod_id}")],
        [InlineKeyboardButton(f"✅ Aggiungi {qty} al Carrello", callback_data=f"add_{prod_id}_{qty}")],
        [InlineKeyboardButton("🔙 Torna ai Prodotti", callback_data="listings")]
    ]
    try: await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except error.BadRequest: pass 

async def add_to_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_"); qty = int(parts[-1]); prod_id = "_".join(parts[1:-1])
    return await execute_add_to_cart(update, context, prod_id, qty)

async def execute_add_to_cart(update, context, prod_id, qty):
    cart = context.user_data.get('cart', {})
    current = cart.get(prod_id, 0)
    cart[prod_id] = current + qty
    context.user_data['cart'] = cart; context.user_data['step'] = None 
    
    prod_name = PRODUCTS[prod_id]['name']
    text = f"✅ Aggiunti {qty} di {prod_name}!\nOra ne hai {cart[prod_id]} nel carrello."
    keyboard = [[InlineKeyboardButton("🛍 Continua Shopping", callback_data="listings")], [InlineKeyboardButton("🛒 Vai al Carrello", callback_data="show_cart")]]
    
    if hasattr(update, 'callback_query') and update.callback_query:
        # NO MARKDOWN QUI PER SICUREZZA
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        try: await update.message.delete()
        except: pass
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['selected_shipping'] = None 
    cart = context.user_data.get('cart', {})
    
    if not cart: 
        await query.edit_message_text("🛒 **Carrello vuoto!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Shop", callback_data="listings")]]), parse_mode="Markdown")
        return
    
    total = sum([PRODUCTS[pid]['price'] * q for pid, q in cart.items() if pid in PRODUCTS])
    context.user_data['cart_total_products'] = total
    recap = get_order_recap(context)
    
    keyboard = [
        [InlineKeyboardButton("❌ Svuota Carrello", callback_data="empty_cart")],
        [InlineKeyboardButton("🚚 Procedi alla Spedizione", callback_data="choose_shipping")], 
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    await query.edit_message_text(f"🛒 **CARRELLO**\n\n{recap}\n💰 **Totale Merce: {total}€**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def empty_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cart'] = {}; await show_cart(update, context)

# --- SPEDIZIONE (PUNTO CRITICO) ---

async def choose_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: Choose Shipping")
    query = update.callback_query; await query.answer()
    context.user_data['selected_shipping'] = None
    
    keyboard = []
    # Usiamo "BTN_SHIP_"
    for code, method in SHIPPING_METHODS.items():
        keyboard.append([InlineKeyboardButton(f"{method['name']} (+{method['price']}€)", callback_data=f"BTN_SHIP_{code}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Indietro", callback_data="show_cart")])
    await query.edit_message_text("🚚 **Scegli Spedizione:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_shipping_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    LOGICA MODIFICATA: CANCELLA IL VECCHIO, MANDA IL NUOVO SENZA MARKDOWN
    """
    query = update.callback_query
    await query.answer()
    
    print(f"DEBUG: Click Spedizione {query.data}")
    
    ship_code = query.data.replace("BTN_SHIP_", "")
    
    if ship_code not in SHIPPING_METHODS:
        print("DEBUG: Codice spedizione non valido")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Errore. Riprova.")
        return

    context.user_data['selected_shipping'] = ship_code
    context.user_data['step'] = 'address_input'
    
    # 1. CANCELLA IL MESSAGGIO DEI BOTTONI (Per evitare che rimanga bloccato lì)
    try:
        await query.message.delete()
    except Exception as e:
        print(f"DEBUG: Errore cancellazione messaggio spedizione: {e}")

    # 2. MANDA IL NUOVO MESSAGGIO (SENZA MARKDOWN per evitare crash)
    print("DEBUG: Invio richiesta indirizzo")
    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📫 DATI DI SPEDIZIONE\n\nScrivi ora in chat il tuo indirizzo completo (Nome, Via, Città, CAP, Nazione).", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Indietro", callback_data="choose_shipping")]])
    )
    # Salviamo ID per cancellarlo dopo
    context.user_data['address_req_id'] = msg.message_id

# --- PAGAMENTO ---

async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE, from_text=False):
    await cleanup_messages(context, update.effective_chat.id)
    
    # CANCELLA LA RICHIESTA INDIRIZZO "DATI SPEDIZIONE" SE ESISTE
    addr_id = context.user_data.get('address_req_id')
    if addr_id:
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=addr_id)
        except: pass
        context.user_data['address_req_id'] = None

    ship_code = context.user_data.get('selected_shipping')
    
    if not ship_code or ship_code not in SHIPPING_METHODS:
        await choose_shipping(update, context); return

    total = context.user_data.get('cart_total_products', 0) + SHIPPING_METHODS[ship_code]['price']
    context.user_data['final_total_eur'] = total
    address = context.user_data.get('shipping_address', 'Non inserito')
    recap_products = get_order_recap(context)

    # Rimuovo Markdown anche qui per sicurezza
    text = (
        f"📝 RIEPILOGO ORDINE\n\n"
        f"🏠 INDIRIZZO:\n{address}\n\n"
        f"📦 CONTENUTO:\n{recap_products}"
        f"💰 TOTALE FINALE: {total}€\n\n"
        "👇 Seleziona metodo di pagamento:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🟠 Bitcoin (BTC)", callback_data="pay_BTC")],
        [InlineKeyboardButton("🔵 Litecoin (LTC)", callback_data="pay_LTC")],
        [InlineKeyboardButton("🟢 USDC (ERC20/TRC20)", callback_data="pay_USDC")],
        [InlineKeyboardButton("✏️ Cambia Indirizzo", callback_data=f"BTN_SHIP_{ship_code}")], 
        [InlineKeyboardButton("❌ Annulla Ordine", callback_data="main_menu")]
    ]
    
    # Se viene da click precedente, cancella il vecchio messaggio
    if not from_text and update.callback_query:
        try: await update.callback_query.message.delete()
        except: pass

    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); await cleanup_messages(context, update.effective_chat.id)
    crypto = query.data.replace("pay_", "")
    eur = context.user_data['final_total_eur']
    address = context.user_data.get('shipping_address')
    recap_products = get_order_recap(context)

    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔄 Calcolo cambio {crypto}...", parse_mode="Markdown")
    amount = get_crypto_price(crypto, eur)
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)

    wallet = WALLETS.get(crypto, "Errore")
    context.user_data['pending_order'] = {"crypto": crypto, "amount": amount, "wallet": wallet, "eur": eur}
    context.user_data['step'] = 'txid_input'

    text = (
        f"🏠 **Indirizzo:** `{address}`\n"
        f"📦 **Ordine:**\n{recap_products}"
        f"💰 **TOTALE: {eur}€**\n\n"
        f"💳 **PAGAMENTO {crypto}**\n"
        f"Invia esattamente: `{amount} {crypto}`\n\n"
        f"⬇️ Premi **COPIA** per ottenere il wallet."
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 COPIA INDIRIZZO WALLET", callback_data=f"copy_{crypto}")],
        [InlineKeyboardButton("🔙 Cambia Metodo", callback_data="to_pay_methods")],
        [InlineKeyboardButton("❌ Annulla Ordine", callback_data="main_menu")]
    ]
    
    try: await query.message.delete()
    except: pass

    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def copy_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; crypto = query.data.replace("copy_", ""); wallet = WALLETS.get(crypto, "Errore")
    
    wallet_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"`{wallet}`", parse_mode="Markdown")
    context.user_data['wallet_msg_id'] = wallet_msg.message_id
    
    warn_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ **IN ATTESA...** Incolla qui sotto il **TXID**.", parse_mode="Markdown")
    context.user_data['warning_msg_id'] = warn_msg.message_id
    await query.answer("Copiato!")

# --- ROUTER ---

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    step = context.user_data.get('step')

    # CANCELLA IL MESSAGGIO DELL'UTENTE
    try: await update.message.delete()
    except: pass

    if step == 'qty_manual':
        prod_id = context.user_data.get('awaiting_qty_prod')
        if not prod_id: return 
        try:
            qty = int(user_text)
            if qty <= 0: raise ValueError
            await execute_add_to_cart(update, context, prod_id, qty)
        except ValueError:
            m = await update.message.reply_text("❌ Numero non valido.")
        return

    if step == 'address_input':
        if len(user_text) < 5: 
            await update.message.reply_text("⚠️ Indirizzo troppo corto.")
            return
        
        context.user_data['shipping_address'] = user_text
        context.user_data['step'] = None 
        
        await show_payment_methods(update, context, from_text=True)
        return

    if step == 'txid_input':
        txid = user_text; order = context.user_data.get('pending_order')
        if not order: return 
        await cleanup_messages(context, update.effective_chat.id)
        check_msg = await update.message.reply_text("🛰 **Verifica Blockchain in corso...**", parse_mode="Markdown")
        valid, msg_verify = verify_tx_on_blockchain(order['crypto'], txid, order['amount'], order['wallet'])
        
        if not valid:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=check_msg.message_id, text=f"{msg_verify}\n\nRiprova.")
            return 
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=check_msg.message_id, text=f"{msg_verify}\n\n🎉 **ORDINE CONFERMATO!**")
        try: 
            addr = context.user_data['shipping_address']; recap = get_order_recap(context)
            await context.bot.send_message(ADMIN_CHAT_ID, f"🚨 NUOVO ORDINE!\n\n{recap}\n🏠 {addr}\n🔗 TXID: `{txid}`")
        except: pass
        context.user_data['cart'] = {}; context.user_data['step'] = None

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    print(f"DEBUG CALLBACK: {data}")
    
    try:
        # PRIORITÀ SPEDIZIONE
        if "BTN_SHIP_" in data:
            await handle_shipping_selection(update, context)
            return

        if data == "main_menu": await start(update, context)
        elif data == "listings": await listings(update, context)
        elif data == "policy": await policy_page(update, context)
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
    
    except Exception as e:
        print(f"Errore Router: {e}")
        try: await update.callback_query.answer("⚠️ Errore (Riprova).")
        except: pass

def main():
    threading.Thread(target=run_fake_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))
    print("Bot avviato! ✔️")
    app.run_polling()

if __name__ == "__main__":
    main()