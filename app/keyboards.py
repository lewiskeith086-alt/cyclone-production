from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
def user_main_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔎 Search")],[KeyboardButton(text="👤 Account"), KeyboardButton(text="💳 Balance")],[KeyboardButton(text="💰 Top Up"), KeyboardButton(text="📦 Plans")],[KeyboardButton(text="🎁 Referral"), KeyboardButton(text="ℹ️ Information")]], resize_keyboard=True)
def admin_main_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔎 Search")],[KeyboardButton(text="👤 Account"), KeyboardButton(text="💳 Balance")],[KeyboardButton(text="💰 Top Up"), KeyboardButton(text="📦 Plans")],[KeyboardButton(text="📤 Upload"), KeyboardButton(text="🎁 Referral"), KeyboardButton(text="📢 Broadcast")],[KeyboardButton(text="📊 Admin Stats"), KeyboardButton(text="➕ Give Credits"), KeyboardButton(text="💵 Add Balance")],[KeyboardButton(text="ℹ️ Information")]], resize_keyboard=True)
def search_filter_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Domain", callback_data="filter:domain")],[InlineKeyboardButton(text="Country", callback_data="filter:country")],[InlineKeyboardButton(text="Keyword", callback_data="filter:keyword")]])
def search_export_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📄 Export TXT", callback_data="export:txt")],[InlineKeyboardButton(text="📊 Export CSV", callback_data="export:csv")],[InlineKeyboardButton(text="‹ Back", callback_data="search:back")]])
def back_only_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Back", callback_data="search:back_to_filters")]])
def broadcast_confirm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Send Broadcast", callback_data="broadcast:send")],[InlineKeyboardButton(text="❌ Cancel", callback_data="broadcast:cancel")]])
def give_credits_confirm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Apply Credits", callback_data="credits:apply")],[InlineKeyboardButton(text="❌ Cancel", callback_data="credits:cancel")]])
def add_balance_confirm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Add Balance", callback_data="balanceadd:apply")],[InlineKeyboardButton(text="❌ Cancel", callback_data="balanceadd:cancel")]])
def plans_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="♾️ Buy Unlimited", callback_data="plan:unlimited")]])
def crypto_topup_menu():
    rows=[]; coins=["XMR","USDT","USDC","TRX","TON","SOL","SHIB","POL","LTC","ETH","DOGE","DASH","DAI","BTC","BNB","BCH","AVAX"]; row=[]
    for coin in coins:
        row.append(InlineKeyboardButton(text=coin, callback_data=f"topupcoin:{coin}"))
        if len(row)==3: rows.append(row); row=[]
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(text="‹ Back", callback_data="topup:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
