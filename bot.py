from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================
# ⚙️ CONFIGURAZIONE DEL BOT
# ==========================================

# Inserisci qui il Token che ti ha dato BotFather
TOKEN = os.getenv("BOT_TOKEN") 

# Il tuo Username Telegram (per il pulsante contatti)
CONTACT_USERNAME = "tuo_username_qui" 

# Il tuo Chat ID (dove riceverai le notifiche degli ordini pagati)
ADMIN_CHAT_ID = 123456789 

# I TUOI WALLET (IMPORTANTE: Inserisci quelli veri per far funzionare la verifica)
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
# 🚚 METODI DI SPEDIZIONE
# ==========================================
SHIPPING_METHODS = {
    "std": {"name": "🇮🇹 Poste Italiane", "price": 10},
    "exp": {"name": "🚀 Express (24h)", "price": 20},
    "stl": {"name": "🕵️‍♂️ Stealth Pro", "price": 35}
}

# ==========================================
# 🌐 SERVER FAKE (Per mantenere il bot attivo online)
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
# 🔧 FUNZIONI UTILI (Prezzi, Recap, Verifica)
# ==========================================

def get_crypto_price(crypto_symbol, fiat_amount):
    """
    Ottiene il prezzo aggiornato della crypto (BTC/LTC/USDC) in base agli Euro.
    """
    try:
        # Tentativo 1: API Coinbase
        pair = f"{crypto_symbol}-EUR"
        url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
        response = requests.get(url).json()
        price_one_coin = float(response['data']['amount'])
        return round(fiat_amount / price_one_coin, 6)
    except:
        # Tentativo 2: API Binance (Fallback)
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
    """
    Genera una stringa di testo con la lista dei prodotti e i costi.
    Usata per mostrare lo scontrino all'utente.
    """
    cart = context.user_data.get('cart', {})
    text = ""
    
    # Elenco Prodotti
    for prod_id, qty in cart.items():
        prod = PRODUCTS[prod_id]
        subtotal = prod['price'] * qty
        text += f"▪️ {prod['name']} x{qty} = {subtotal}€\n"
    
    # Aggiunta Spedizione
    ship_code = context.user_data.get('selected_shipping')
    if ship_code:
        method = SHIPPING_METHODS[ship_code]
        text += f"▪️ 🚚 Spedizione {method['name']} = {method['price']}€\n"
        
    text += "-------------------\n"
    return text

def verify_tx_on_blockchain(crypto, txid, expected_amount, my_wallet_address):
    """
    Verifica SICURA della transazione sulla Blockchain.
    Controlla: 
    1. Se il TXID esiste.
    2. Se i soldi sono arrivati al TUO wallet.
    3. Se l'importo è corretto (con tolleranza 1%).
    """
    txid = txid.strip()
    
    # Controllo lunghezza minima TXID
    if len(txid) < 10: 
        return False, "❌ TXID troppo corto."

    try:
        # --- VERIFICA BITCOIN (BTC) ---
        if crypto == "BTC":
            url = f"https://blockchain.info/rawtx/{txid}"
            resp = requests.get(url)
            
            if resp.status_code != 200:
                return False, "⚠️ TXID non trovato sulla Blockchain Bitcoin."
            
            data = resp.json()
            found = False
            amount_received = 0.0

            # Cerca il tuo wallet tra gli output della transazione
            for output in data.get('out', []):
                if 'addr' in output and output['addr'] == my_wallet_address:
                    amount_received = float(output['value']) / 100000000.0 # Converte Satoshi in BTC
                    found = True
                    break
            
            if not found:
                return False, "❌ Il TXID esiste, ma i soldi NON sono stati inviati al tuo wallet."
            
            # Controllo importo (Tolleranza 1%)
            if amount_received < (expected_amount * 0.99):
                return False, f"⚠️ Importo insufficiente. Ricevuto: {amount_received:.6f}, Richiesto: {expected_amount:.6f}"

            return True, "✅ Pagamento BTC Verificato e Corretto!"

        # --- VERIFICA LITECOIN (LTC) ---
        elif crypto == "LTC":
            url = f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}"
            resp = requests.get(url)
            
            if resp.status_code != 200:
                return False, "⚠️ TXID non trovato sulla rete Litecoin."
            
            data = resp.json()
            found = False
            amount_received = 0.0

            # Cerca il tuo wallet negli output
            for output in data.get('outputs', []):
                if my_wallet_address in output.get('addresses', []):
                    amount_received = float(output['value']) / 100000000.0 # Converte Litoshi in LTC
                    found = True
                    break
            
            if not found:
                return False, "❌ Il TXID esiste, ma i soldi NON sono stati inviati al tuo wallet."

            if amount_received < (expected_amount * 0.99):
                return False, f"⚠️ Importo insufficiente. Ricevuto: {amount_received:.6f}, Richiesto: {expected_amount:.6f}"

            return True, "✅ Pagamento LTC Verificato e Corretto!"

        # --- VERIFICA USDC (Solo Formale) ---
        elif crypto == "USDC":
            # Controllo solo se il formato sembra un hash valido (0x... per ERC20 o 64 char per TRC20)
            if (txid.startswith("0x") and len(txid) == 66) or (len(txid) == 64):
                return True, "⚠️ Formato USDC valido. CONTROLLA MANUALMENTE L'ARRIVO DEI FONDI NEL WALLET."
            return False, "❌ Formato TXID non valido."

    except Exception as e:
        print(f"Errore API: {e}")
        return True, "⚠️ Errore API temporaneo (Blockchain info). Verifica manualmente."
    
    return False, "❌ TXID non valido."

async def delete_warning_msg(context, chat_id):
    """
    Cancella il messaggio 'In attesa del TXID' per pulire la chat
    quando l'utente cambia menu o completa l'ordine.
    """
    msg_id = context.user_data.get('warning_msg_id')
    if msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass # Il messaggio potrebbe essere già stato cancellato
        context.user_data['warning_msg_id'] = None

# ==========================================
# 🤖 LOGICA DEL BOT (Handlers)
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start: Menu Principale"""
    if 'cart' not in context.user_data:
        context.user_data['cart'] = {}
    
    # Reset stato utente
    context.user_data['step'] = None 
    await delete_warning_msg(context, update.effective_chat.id)

    text = "🍝 **SPAGHETTIMAFIA SHOP** 🍝\n\nBenvenuto! Scegli un'opzione:"
    
    keyboard = [
        [InlineKeyboardButton("💊 Listings (Prodotti)", callback_data="listings")],
        [InlineKeyboardButton("🛒 Il mio Carrello", callback_data="show_cart")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra la lista dei prodotti."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['step'] = None 
    await delete_warning_msg(context, update.effective_chat.id)

    keyboard = []
    # Genera bottoni dinamicamente dai prodotti
    for key, prod in PRODUCTS.items():
        btn_text = f"{prod['name']} - {prod['price']}€"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"sel_{key}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")])
    
    await query.edit_message_text("💊 **PRODOTTI DISPONIBILI**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- GESTIONE CARRELLO E QUANTITÀ ---

async def init_quantity_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inizializza il selettore quantità a 5."""
    query = update.callback_query
    await query.answer()
    prod_id = query.data.split("_")[1] + "_" + query.data.split("_")[2]
    await update_quantity_view(query, prod_id, 5)

async def manage_quantity_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce i tasti Più e Meno."""
    query = update.callback_query
    parts = query.data.split("_")
    action = parts[1]
    prod_id = f"{parts[2]}_{parts[3]}"
    current_qty = int(parts[4])
    
    # Incrementa o decrementa di 5
    new_qty = current_qty + 5 if action == "inc" else current_qty - 5
    
    if new_qty < 5:
        await query.answer("Minimo 5!")
        return
        
    await update_quantity_view(query, prod_id, new_qty)
    await query.answer()

async def update_quantity_view(query, prod_id, qty):
    """Aggiorna la grafica del messaggio quantità."""
    product = PRODUCTS[prod_id]
    tot_price = product['price'] * qty
    
    text = (
        f"💊 **{product['name']}**\n"
        f"Quantità: **{qty} {product['unit']}**\n"
        f"Totale Parziale: **{tot_price}€**"
    )
    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data=f"qty_dec_{prod_id}_{qty}"), 
            InlineKeyboardButton(f"{qty}", callback_data="noop"), 
            InlineKeyboardButton("➕", callback_data=f"qty_inc_{prod_id}_{qty}")
        ],
        [
            InlineKeyboardButton("✅ Aggiungi al Carrello", callback_data=f"add_{prod_id}_{qty}"), 
            InlineKeyboardButton("🔙 Annulla", callback_data="listings")
        ]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def add_to_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Conferma l'aggiunta al carrello."""
    query = update.callback_query
    parts = query.data.split("_")
    prod_id = f"{parts[1]}_{parts[2]}"
    qty = int(parts[3])
    
    cart = context.user_data.get('cart', {})
    cart[prod_id] = cart.get(prod_id, 0) + qty
    context.user_data['cart'] = cart
    
    await query.edit_message_text(
        "✅ Prodotto aggiunto al carrello con successo!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Vai al Carrello", callback_data="show_cart")]])
    )

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra il riepilogo del carrello."""
    query = update.callback_query
    await query.answer()
    
    cart = context.user_data.get('cart', {})
    
    if not cart:
        await query.edit_message_text(
            "🛒 **Il tuo carrello è vuoto.**", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Torna allo Shop", callback_data="listings")]]), 
            parse_mode="Markdown"
        )
        return

    # Calcolo totale merce
    total = sum([PRODUCTS[pid]['price'] * q for pid, q in cart.items()])
    context.user_data['cart_total_products'] = total
    
    recap = get_order_recap(context) # Genera lista prodotti
    
    keyboard = [
        [InlineKeyboardButton("🚚 Procedi (Spedizione)", callback_data="choose_shipping")],
        [InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"🛒 **IL TUO CARRELLO**\n\n{recap}\n💰 **Totale Merce: {total}€**", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

# --- FLUSSO CHECKOUT (SPEDIZIONE E PAGAMENTO) ---

async def choose_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: Scelta metodo spedizione."""
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for code, method in SHIPPING_METHODS.items():
        keyboard.append([InlineKeyboardButton(f"{method['name']} (+{method['price']}€)", callback_data=f"ship_{code}")])
    
    await query.edit_message_text("🚚 **Scegli il metodo di spedizione:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def ask_shipping_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: Richiesta input indirizzo."""
    query = update.callback_query
    await query.answer()
    
    # Salva la scelta della spedizione
    if query.data.startswith("ship_"):
        context.user_data['selected_shipping'] = query.data.split("_")[1]
    
    context.user_data['step'] = 'address_input'
    
    await query.edit_message_text(
        "📫 **DATI DI SPEDIZIONE**\n\n"
        "Scrivi ora in chat il tuo indirizzo completo (Nome, Via, Città, CAP, Nazione).",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Indietro", callback_data="choose_shipping")]]),
        parse_mode="Markdown"
    )

async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE, from_text=False):
    """
    Step 3: RIEPILOGO TOTALE (Prodotti + Spedizione + Indirizzo)
    e selezione del metodo di pagamento.
    """
    await delete_warning_msg(context, update.effective_chat.id)

    # Calcolo del totale finale
    ship_code = context.user_data.get('selected_shipping')
    total = context.user_data.get('cart_total_products', 0) + SHIPPING_METHODS[ship_code]['price']
    context.user_data['final_total_eur'] = total
    
    address = context.user_data.get('shipping_address', 'Non inserito')
    recap_products = get_order_recap(context) 

    # Creazione del messaggio di riepilogo ben visibile
    text = (
        f"📝 **RIEPILOGO ORDINE**\n\n"
        f"🏠 **INDIRIZZO DI SPEDIZIONE:**\n"
        f"`{address}`\n\n"
        f"📦 **CONTENUTO:**\n"
        f"{recap_products}"
        f"💰 **TOTALE FINALE: {total}€**\n\n"
        "👇 **Seleziona metodo di pagamento:**"
    )
    
    keyboard = [
        [InlineKeyboardButton("🟠 BTC", callback_data="pay_BTC"), InlineKeyboardButton("🔵 LTC", callback_data="pay_LTC")],
        [InlineKeyboardButton("🟢 USDC", callback_data="pay_USDC")],
        [InlineKeyboardButton("✏️ Modifica Indirizzo", callback_data="ship_" + ship_code)]
    ]
    
    if from_text:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 4: Pagamento. Mostra l'indirizzo Crypto e il riepilogo ancora una volta.
    """
    query = update.callback_query
    await query.answer()
    
    await delete_warning_msg(context, update.effective_chat.id)

    crypto = query.data.replace("pay_", "")
    eur = context.user_data['final_total_eur']
    
    # Recuperiamo l'indirizzo e il recap per mostrarli ANCHE QUI
    address = context.user_data.get('shipping_address', 'Non inserito')
    recap_products = get_order_recap(context)

    await query.edit_message_text(f"🔄 Calcolo cambio {crypto}...")
    
    # Conversione Euro -> Crypto
    amount = get_crypto_price(crypto, eur)
    wallet = WALLETS.get(crypto, "Errore")
    
    # Salva i dati per la verifica del TXID successiva
    context.user_data['pending_order'] = {
        "crypto": crypto, 
        "amount": amount, 
        "wallet": wallet, 
        "eur": eur
    }
    context.user_data['step'] = 'txid_input'

    # Messaggio finale di pagamento
    text = (
        f"🏠 **Indirizzo Spedizione:**\n`{address}`\n\n"
        f"📦 **Ordine:**\n{recap_products}"
        f"💰 **TOTALE DA PAGARE: {eur}€**\n\n"
        f"💳 **PAGAMENTO {crypto} RICHIESTO**\n"
        f"Invia esattamente: `{amount} {crypto}`\n\n"
        f"⬇️ Premi **COPIA** qui sotto per copiare l'indirizzo wallet."
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 COPIA INDIRIZZO WALLET", callback_data=f"copy_{crypto}")],
        [InlineKeyboardButton("🔙 Indietro (Cambia Crypto)", callback_data="to_pay_methods")],
        [InlineKeyboardButton("❌ Annulla Ordine", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def copy_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestisce il bottone 'Copia'. Invia l'indirizzo in un messaggio separato
    per facilitare la copia su smartphone e invia l'istruzione per il TXID.
    """
    query = update.callback_query
    crypto = query.data.replace("copy_", "")
    wallet = WALLETS.get(crypto, "Errore")
    
    # 1. Invia SOLO l'indirizzo (Monospace per copia rapida)
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=f"`{wallet}`", 
        parse_mode="Markdown"
    )
    
    # 2. Invia messaggio di istruzioni (che cancelleremo se l'utente torna indietro)
    warn_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="⏳ **IN ATTESA DEL PAGAMENTO...**\n\nDopo aver inviato i fondi, copia il **TXID** (ID Transazione) e incollalo qui in chat.", 
        parse_mode="Markdown"
    )
    context.user_data['warning_msg_id'] = warn_msg.message_id
    
    await query.answer("Indirizzo copiato! Incolla il TXID quando hai fatto.")

# --- GESTORE INPUT TESTUALE (INDIRIZZO E TXID) ---

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Intercetta tutto ciò che l'utente scrive.
    Gestisce sia l'inserimento dell'indirizzo che l'invio del TXID.
    """
    user_text = update.message.text
    step = context.user_data.get('step')

    # CASO 1: Inserimento Indirizzo Spedizione
    if step == 'address_input':
        if len(user_text) < 5:
            await update.message.reply_text("⚠️ Indirizzo troppo corto. Per favore inserisci un indirizzo valido.")
            return
        
        # Salviamo l'indirizzo
        context.user_data['shipping_address'] = user_text
        context.user_data['step'] = None 
        
        # Mostriamo subito il riepilogo con i bottoni di pagamento
        await show_payment_methods(update, context, from_text=True)
        return

    # CASO 2: Inserimento TXID (Pagamento)
    if step == 'txid_input':
        txid = user_text
        order = context.user_data['pending_order']
        expected, wallet, crypto = order['amount'], order['wallet'], order['crypto']
        
        # Cancelliamo il messaggio "In attesa..."
        await delete_warning_msg(context, update.effective_chat.id)
        
        # Messaggio di stato
        check_msg = await update.message.reply_text("🛰 **Verifica Blockchain in corso...**\n_Attendere prego..._", parse_mode="Markdown")
        
        # --- VERIFICA REALE ---
        valid, msg_verify = verify_tx_on_blockchain(crypto, txid, expected, wallet)
        
        if not valid:
            # Fallimento
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, 
                message_id=check_msg.message_id, 
                text=f"{msg_verify}\n\nRiprova o controlla di aver copiato bene il TXID."
            )
            return 
        
        # Successo
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=check_msg.message_id, 
            text=f"{msg_verify}\n\n🎉 **ORDINE CONFERMATO!**\nLa spedizione avverrà entro 24h."
        )
        
        # NOTIFICA ALL'ADMIN
        try: 
            addr = context.user_data['shipping_address']
            recap = get_order_recap(context)
            await context.bot.send_message(
                ADMIN_CHAT_ID, 
                f"🚨 **NUOVO ORDINE PAGATO** 🚨\n\n{recap}\n🏠 **Indirizzo:**\n`{addr}`\n\n🔗 **TXID:** `{txid}`",
                parse_mode="Markdown"
            )
        except: 
            pass
        
        # Reset finale
        context.user_data['cart'] = {}
        context.user_data['step'] = None

# --- ROUTER (Gestione Bottoni) ---

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Smista i click sui bottoni alle funzioni corrette."""
    data = update.callback_query.data
    
    # Se torno al menu o cambio metodo, pulisco eventuali messaggi pendenti
    if data in ["main_menu", "to_pay_methods"]:
        await delete_warning_msg(context, update.effective_chat.id)

    # Navigazione Base
    if data == "main_menu": 
        await start(update, context)
    elif data == "listings": 
        await listings(update, context)
    elif data == "show_cart": 
        await show_cart(update, context)
    
    # Navigazione Checkout
    elif data == "choose_shipping": 
        await choose_shipping(update, context)
    elif data.startswith("ship_"): 
        await ask_shipping_address(update, context)
    elif data == "to_pay_methods": 
        await show_payment_methods(update, context, from_text=False)
    
    # Logica Quantità e Carrello
    elif data.startswith("sel_"): 
        await init_quantity_selector(update, context)
    elif data.startswith("qty_"): 
        await manage_quantity_buttons(update, context)
    elif data.startswith("add_"): 
        await add_to_cart_handler(update, context)
    
    # Logica Pagamento
    elif data.startswith("pay_"): 
        await process_payment(update, context)
    elif data.startswith("copy_"): 
        await copy_address_handler(update, context)
    
    elif data == "noop": 
        await update.callback_query.answer()

# ==========================================
# 🚀 AVVIO DEL BOT
# ==========================================

def main():
    # Avvia il server fake in background (necessario per hosting cloud gratuiti)
    threading.Thread(target=run_fake_server, daemon=True).start()
    
    # Costruzione dell'applicazione
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Aggiunta degli handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))
    
    print("Bot avviato con successo! ✔️")
    app.run_polling()

if __name__ == "__main__":
    main()