from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_fake_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# ==========================================
# 🔧 FUNZIONI UTILI (Prezzi, Recap, Cleanup)
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
    """Genera lo scontrino."""
    cart = context.user_data.get('cart', {})
    text = ""
    for prod_id, qty in cart.items():
        prod = PRODUCTS[prod_id]
        subtotal = prod['price'] * qty
        text += f"▪️ {prod['name']} x{qty} = {subtotal}€\n"
    
    ship_code = context.user_data.get('selected_shipping')
    if ship_code:
        method = SHIPPING_METHODS[ship_code]
        text += f"▪️ 🚚 Spedizione {method['name']} = {method['price']}€\n"
    text += "-------------------\n"
    return text

def verify_tx_on_blockchain(crypto, txid, expected_amount, my_wallet_address):
    """Verifica Sicura TXID."""
    txid = txid.strip()
    if len(txid) < 10: return False, "❌ TXID troppo corto."

    try:
        if crypto == "BTC":
            url = f"https://blockchain.info/rawtx/{txid}"
            resp = requests.get(url)
            if resp.status_code != 200: return False, "⚠️ TXID non trovato su Bitcoin."
            data = resp.json()
            found = False
            amount_received = 0.0
            for output in data.get('out', []):
                if 'addr' in output and output['addr'] == my_wallet_address:
                    amount_received = float(output['value']) / 100000000.0
                    found = True
                    break
            if not found: return False, "❌ TXID esistente ma destinatario errato."
            if amount_received < (expected_amount * 0.99): return False, f"⚠️ Importo insufficiente."
            return True, "✅ Pagamento BTC Verificato!"

        elif crypto == "LTC":
            url = f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}"
            resp = requests.get(url)
            if resp.status_code != 200: return False, "⚠️ TXID non trovato su Litecoin."
            data = resp.json()
            found = False
            amount_received = 0.0
            for output in data.get('outputs', []):
                if my_wallet_address in output.get('addresses', []):
                    amount_received = float(output['value']) / 100000000.0
                    found = True
                    break
            if not found: return False, "❌ TXID esistente ma destinatario errato."
            if amount_received < (expected_amount * 0.99): return False, f"⚠️ Importo insufficiente."
            return True, "✅ Pagamento LTC Verificato!"

        elif crypto == "USDC":
            if (txid.startswith("0x") and len(txid) == 66) or (len(txid) == 64):
                return True, "⚠️ Formato USDC valido. CONTROLLA MANUALMENTE."
            return False, "❌ Formato TXID non valido."

    except Exception:
        return True, "⚠️ Errore API temporaneo."
    return False, "❌ TXID non valido."

async def cleanup_messages(context, chat_id):
    """
    Cancella i messaggi temporanei (Avviso attesa e Indirizzo Wallet inviato)
    per mantenere la chat pulita quando l'utente torna indietro.
    """
    # 1. Cancella Messaggio Avviso "In Attesa"
    msg_id = context.user_data.get('warning_msg_id')
    if msg_id:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except: pass
        context.user_data['warning_msg_id'] = None
    
    # 2. Cancella Messaggio "Indirizzo Wallet" (quello copiabile)
    wallet_msg_id = context.user_data.get('wallet_msg_id')
    if wallet_msg_id:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=wallet_msg_id)
        except: pass
        context.user_data['wallet_msg_id'] = None

# ==========================================
# 🤖 LOGICA BOT
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu Principale (RIPRISTINATO COMPLETO)"""
    if 'cart' not in context.user_data: context.user_data['cart'] = {}
    context.user_data['step'] = None 
    context.user_data['awaiting_qty_prod'] = None
    
    await cleanup_messages(context, update.effective_chat.id)

    # Testo completo come richiesto all'inizio
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
    
    # Bottoni originali ripristinati
    keyboard = [
        [InlineKeyboardButton("💊 Listings (Prodotti)", callback_data="listings")],
        [InlineKeyboardButton("📣 POLICY", callback_data="policy"), InlineKeyboardButton("📞 Contacts", url=f"https://t.me/{CONTACT_USERNAME}")],
        [InlineKeyboardButton("🛒 Il mio Carrello", callback_data="show_cart")]
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query: 
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode="Markdown")
    else: 
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode="Markdown")

async def listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
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
    """Pagina Policy"""
    query = update.callback_query
    await query.answer()
    text = "📣 **OUR POLICY**\n\n1. No refunds without video opening.\n2. Shipping time 2-5 days.\n3. Be polite."
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- QUANTITA' (CON INSERIMENTO MANUALE RIPRISTINATO) ---

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
    """Attiva l'input manuale da tastiera"""
    query = update.callback_query
    await query.answer()
    prod_id = query.data.replace("type_qty_", "")
    
    context.user_data['step'] = 'qty_manual'
    context.user_data['awaiting_qty_prod'] = prod_id
    
    prod_name = PRODUCTS[prod_id]['name']
    await query.edit_message_text(
        f"⌨️ **QUANTITÀ MANUALE**\n\nProdotto: **{prod_name}**\nScrivi in chat il numero esatto (es. 25) e invia.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Annulla", callback_data=f"sel_{prod_id}")]])
    )

async def update_quantity_view(query, prod_id, qty):
    product = PRODUCTS[prod_id]
    tot_price = product['price'] * qty
    text = (
        f"💊 **{product['name']}**\n"
        f"Prezzo: {product['price']}€/{product['unit']}\n\n"
        f"🔢 Quantità: **{qty} {product['unit']}**\n"
        f"💰 Totale Parziale: **{tot_price}€**"
    )
    keyboard = [
        [
            InlineKeyboardButton("➖ 5", callback_data=f"qty_dec_{prod_id}_{qty}"), 
            InlineKeyboardButton(f" {qty} ", callback_data="noop"), 
            InlineKeyboardButton("➕ 5", callback_data=f"qty_inc_{prod_id}_{qty}")
        ],
        # BOTTONE SCRIVI A MANO RIPRISTINATO
        [InlineKeyboardButton("⌨️ Scrivi a mano", callback_data=f"type_qty_{prod_id}")],
        [InlineKeyboardButton(f"✅ Aggiungi {qty} al Carrello", callback_data=f"add_{prod_id}_{qty}")],
        [InlineKeyboardButton("🔙 Torna ai Prodotti", callback_data="listings")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def add_to_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler per bottone Aggiungi"""
    query = update.callback_query
    parts = query.data.split("_")
    prod_id = f"{parts[1]}_{parts[2]}"
    qty = int(parts[3])
    return await execute_add_to_cart(update, context, prod_id, qty)

async def execute_add_to_cart(update, context, prod_id, qty):
    """Logica condivisa aggiunta al carrello (da bottone o manuale)"""
    cart = context.user_data.get('cart', {})
    cart[prod_id] = cart.get(prod_id, 0) + qty
    context.user_data['cart'] = cart
    context.user_data['step'] = None # Reset step input
    
    text = f"✅ Aggiunti **{qty}** di **{PRODUCTS[prod_id]['name']}** al carrello!"
    keyboard = [[InlineKeyboardButton("🛍 Continua Shopping", callback_data="listings")], [InlineKeyboardButton("🛒 Vai al Carrello", callback_data="show_cart")]]
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart = context.user_data.get('cart', {})
    
    if not cart: 
        await query.edit_message_text(
            "🛒 **Carrello vuoto!**", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Shop", callback_data="listings")]]), 
            parse_mode="Markdown"
        )
        return
    
    total = sum([PRODUCTS[pid]['price'] * q for pid, q in cart.items()])
    context.user_data['cart_total_products'] = total
    recap = get_order_recap(context)
    
    keyboard = [
        [InlineKeyboardButton("❌ Svuota Carrello", callback_data="empty_cart")],
        [InlineKeyboardButton("🚚 Procedi alla Spedizione", callback_data="choose_shipping")], 
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    await query.edit_message_text(f"🛒 **CARRELLO**\n\n{recap}\n💰 **Totale Merce: {total}€**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def empty_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cart'] = {}
    await show_cart(update, context)

# --- SPEDIZIONE & PAGAMENTO ---

async def choose_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(f"{m['name']} (+{m['price']}€)", callback_data=f"ship_{c}")] for c, m in SHIPPING_METHODS.items()]
    keyboard.append([InlineKeyboardButton("🔙 Indietro", callback_data="show_cart")])
    await query.edit_message_text("🚚 **Scegli Spedizione:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def ask_shipping_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ship_"): context.user_data['selected_shipping'] = query.data.split("_")[1]
    context.user_data['step'] = 'address_input'
    await query.edit_message_text("📫 **DATI DI SPEDIZIONE**\n\nScrivi ora in chat il tuo indirizzo completo.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Indietro", callback_data="choose_shipping")]], parse_mode="Markdown"))

async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE, from_text=False):
    """Mostra i bottoni crypto IMPILATI (uno per riga)"""
    
    # IMPORTANTE: Cancella l'indirizzo wallet se l'utente torna indietro
    await cleanup_messages(context, update.effective_chat.id)

    ship_code = context.user_data.get('selected_shipping')
    total = context.user_data.get('cart_total_products', 0) + SHIPPING_METHODS[ship_code]['price']
    context.user_data['final_total_eur'] = total
    address = context.user_data.get('shipping_address', 'Non inserito')
    recap_products = get_order_recap(context)

    text = (
        f"📝 **RIEPILOGO ORDINE**\n\n"
        f"🏠 **INDIRIZZO:**\n`{address}`\n\n"
        f"📦 **CONTENUTO:**\n{recap_products}"
        f"💰 **TOTALE FINALE: {total}€**\n\n"
        "👇 **Seleziona metodo di pagamento:**"
    )
    
    # MODIFICA: Bottoni crypto impilati verticalmente
    keyboard = [
        [InlineKeyboardButton("🟠 Bitcoin (BTC)", callback_data="pay_BTC")],
        [InlineKeyboardButton("🔵 Litecoin (LTC)", callback_data="pay_LTC")],
        [InlineKeyboardButton("🟢 USDC (ERC20/TRC20)", callback_data="pay_USDC")],
        [InlineKeyboardButton("✏️ Cambia Indirizzo", callback_data="ship_" + ship_code)],
        [InlineKeyboardButton("❌ Annulla Ordine", callback_data="main_menu")]
    ]
    
    if from_text: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else: 
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cleanup_messages(context, update.effective_chat.id)

    crypto = query.data.replace("pay_", "")
    eur = context.user_data['final_total_eur']
    address = context.user_data.get('shipping_address')
    recap_products = get_order_recap(context)

    await query.edit_message_text(f"🔄 Calcolo cambio {crypto}...")
    
    amount = get_crypto_price(crypto, eur)
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
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def copy_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    crypto = query.data.replace("copy_", "")
    wallet = WALLETS.get(crypto, "Errore")
    
    # Invia indirizzo e SALVA L'ID per cancellarlo dopo
    wallet_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"`{wallet}`", parse_mode="Markdown")
    context.user_data['wallet_msg_id'] = wallet_msg.message_id
    
    # Invia avviso e SALVA L'ID
    warn_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ **IN ATTESA...**\nDopo aver pagato, incolla qui sotto il **TXID**.", parse_mode="Markdown")
    context.user_data['warning_msg_id'] = warn_msg.message_id
    
    await query.answer("Copiato!")

# --- GESTIONE TESTO (Input Manuale, Indirizzo, TXID) ---

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    step = context.user_data.get('step')

    # 1. INPUT QUANTITÀ MANUALE (Ripristinato)
    if step == 'qty_manual':
        prod_id = context.user_data['awaiting_qty_prod']
        try:
            qty = int(user_text)
            if qty <= 0: raise ValueError
            await execute_add_to_cart(update, context, prod_id, qty)
        except ValueError:
            await update.message.reply_text("❌ Quantità non valida. Inserisci un numero intero (es. 10).")
        return

    # 2. INPUT INDIRIZZO
    if step == 'address_input':
        if len(user_text) < 5: 
            await update.message.reply_text("⚠️ Indirizzo troppo corto.")
            return
        context.user_data['shipping_address'] = user_text
        context.user_data['step'] = None 
        await show_payment_methods(update, context, from_text=True)
        return

    # 3. INPUT TXID
    if step == 'txid_input':
        txid = user_text
        order = context.user_data['pending_order']
        expected, wallet, crypto = order['amount'], order['wallet'], order['crypto']
        
        await cleanup_messages(context, update.effective_chat.id)
        
        check_msg = await update.message.reply_text("🛰 **Verifica Blockchain in corso...**", parse_mode="Markdown")
        valid, msg_verify = verify_tx_on_blockchain(crypto, txid, expected, wallet)
        
        if not valid:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=check_msg.message_id, text=f"{msg_verify}\n\nRiprova.")
            return 
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=check_msg.message_id, text=f"{msg_verify}\n\n🎉 **ORDINE CONFERMATO!**")
        
        try: 
            addr = context.user_data['shipping_address']
            recap = get_order_recap(context)
            await context.bot.send_message(ADMIN_CHAT_ID, f"🚨 NUOVO ORDINE!\n\n{recap}\n🏠 {addr}\n🔗 TXID: `{txid}`")
        except: pass
        
        context.user_data['cart'] = {}
        context.user_data['step'] = None

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    
    # Se premo Main Menu o Cambio Metodo, pulisco i messaggi
    if data in ["main_menu", "to_pay_methods"]: 
        await cleanup_messages(context, update.effective_chat.id)

    if data == "main_menu": await start(update, context)
    elif data == "listings": await listings(update, context)
    elif data == "policy": await policy_page(update, context)
    elif data == "show_cart": await show_cart(update, context)
    elif data == "empty_cart": await empty_cart(update, context)
    elif data == "choose_shipping": await choose_shipping(update, context)
    elif data.startswith("ship_"): await ask_shipping_address(update, context)
    elif data == "to_pay_methods": await show_payment_methods(update, context, from_text=False)
    
    elif data.startswith("sel_"): await init_quantity_selector(update, context)
    elif data.startswith("qty_"): await manage_quantity_buttons(update, context)
    elif data.startswith("type_qty_"): await ask_manual_quantity(update, context)
    elif data.startswith("add_"): await add_to_cart_handler(update, context)
    
    elif data.startswith("pay_"): await process_payment(update, context)
    elif data.startswith("copy_"): await copy_address_handler(update, context)
    elif data == "noop": await update.callback_query.answer()

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