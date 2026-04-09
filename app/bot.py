import asyncio
import logging
import os
import tempfile
from decimal import Decimal, InvalidOperation

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy import func

from .config import BOT_NAME, BOT_TOKEN, ADMIN_CONTACT, UNLIMITED_PLAN_CENTS
from .db import get_session
from .init_db import init_db
from .keyboards import (
    add_balance_confirm_menu,
    admin_main_menu,
    back_only_menu,
    broadcast_confirm_menu,
    crypto_topup_menu,
    give_credits_confirm_menu,
    plans_menu,
    search_export_menu,
    search_filter_menu,
    user_main_menu,
)
from .models import CryptoInvoice, Dataset, SearchLog, User, WalletTransaction
from .services.cryptomus_service import create_invoice, make_order_id
from .services.pricing_service import (
    calculate_export_price_cents,
    cents_to_display,
    pricing_lines,
    unlimited_expiry,
)
from .services.search_service import (
    build_safe_csv,
    build_safe_txt_report,
    fetch_export_records,
    log_search,
    search_records,
)
from .services.user_service import (
    activate_unlimited,
    add_credits,
    add_wallet_balance,
    apply_referral_bonus,
    charge_wallet,
    deduct_credit,
    get_or_create_user,
    has_unlimited,
)
from .states import (
    AddBalanceStates,
    BroadcastStates,
    CryptoTopUpStates,
    GiveCreditsStates,
    SearchStates,
)

logging.basicConfig(level=logging.INFO)

router = Router()

TOPUP_TEXT = (
    "💰 <b>Top Up</b>\n\n"
    "Choose a crypto coin or contact admin.\n\n"
    f"Admin: {ADMIN_CONTACT}\n\n"
    f"{pricing_lines()}"
)


def get_menu_for_user(user: User):
    return admin_main_menu() if user.is_admin else user_main_menu()


def extract_referral_payload(text: str | None):
    parts = (text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    return payload[4:] if payload.startswith("ref_") else None


def safe_query_name(text: str) -> str:
    return (
        (text or "search")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace(".", "_")
        .lower()
    )


async def require_admin(message_or_callback, state: FSMContext | None = None) -> bool:
    db = get_session()
    try:
        fu = message_or_callback.from_user
        user, _ = get_or_create_user(db, fu.id, fu.username, fu.full_name)
        if not user.is_admin:
            if state:
                await state.clear()
            target = (
                message_or_callback.message
                if hasattr(message_or_callback, "message") and message_or_callback.message
                else message_or_callback
            )
            await target.answer("❌ Admin-only action.")
            return False
        return True
    finally:
        db.close()


async def cancel_search_state_if_active(state: FSMContext):
    current = await state.get_state()
    if current == SearchStates.waiting_for_query.state:
        await state.clear()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    db = get_session()
    try:
        user, created = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        payload_code = extract_referral_payload(message.text or "")
        referral_msg = ""
        if created and payload_code and apply_referral_bonus(db, user, payload_code):
            referral_msg = "\n🎁 Referral applied successfully."

        await message.answer(
            f"🔎 <b>{BOT_NAME}</b>\n\n"
            f"Welcome, {message.from_user.full_name or 'User'}.\n"
            f"Free credits: <b>{user.credits}</b>\n"
            f"Wallet: <b>{cents_to_display(user.wallet_balance_cents)}</b>\n"
            f"Admin contact: {ADMIN_CONTACT}{referral_msg}",
            reply_markup=get_menu_for_user(user),
            parse_mode="HTML",
        )
    finally:
        db.close()


@router.message(F.text == "🔎 Search")
async def search_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔎 <b>Search</b>\n\nTap the buttons below to choose your search filter.",
        reply_markup=search_filter_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("filter:"))
async def filter_select_handler(callback: CallbackQuery, state: FSMContext):
    search_type = callback.data.split(":", 1)[1]
    await state.update_data(search_type=search_type)
    await state.set_state(SearchStates.waiting_for_query)
    await callback.message.answer(
        f"🔎 <b>Search</b>\n\nType your {search_type} search query.",
        reply_markup=back_only_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "search:back_to_filters")
async def back_to_filters_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "🔎 <b>Search</b>\n\nTap the buttons below to choose your search filter.",
        reply_markup=search_filter_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(
    SearchStates.waiting_for_query,
    F.text.in_(["📦 Plans", "💰 Top Up", "ℹ️ Information", "👤 Account", "💳 Balance", "🎁 Referral", "🔎 Search"]),
)
async def escape_search_state_to_menu(message: Message, state: FSMContext):
    await state.clear()

    if message.text == "📦 Plans":
        await message.answer(pricing_lines(), reply_markup=plans_menu(), parse_mode="HTML")
    elif message.text == "💰 Top Up":
        await state.set_state(CryptoTopUpStates.waiting_for_coin)
        await message.answer(
            "💸 <b>Top Up</b>\n\nChoose a cryptocurrency to deposit.",
            reply_markup=crypto_topup_menu(),
            parse_mode="HTML",
        )
    elif message.text == "ℹ️ Information":
        await message.answer(
            f"ℹ️ <b>{BOT_NAME}</b>\n\n"
            "This platform supports safe search previews and masked TXT/CSV exports for authorized datasets only.\n"
            f"Admin contact: {ADMIN_CONTACT}",
            parse_mode="HTML",
        )
    elif message.text == "👤 Account":
        await account_handler(message, state)
    elif message.text == "💳 Balance":
        await balance_handler(message, state)
    elif message.text == "🎁 Referral":
        await referral_handler(message, state)
    elif message.text == "🔎 Search":
        await search_menu_handler(message, state)


@router.message(SearchStates.waiting_for_query)
async def capture_query_handler(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query:
        await message.answer("Please type a valid search query.")
        return

    await state.update_data(query=query)
    db = get_session()

    try:
        user, _ = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )

        credits_used = 0
        if user.credits > 0:
            deduct_credit(db, user, 1)
            credits_used = 1

        data = await state.get_data()
        result = search_records(db, data.get("search_type", "keyword"), query)
        export_price_cents = calculate_export_price_cents(result["total"])

        await state.update_data(
            result_count=result["total"],
            export_price_cents=export_price_cents,
            query=query,
        )

        log_search(
            db,
            user.telegram_id,
            data.get("search_type", "keyword"),
            query,
            result["total"],
            credits_used,
            0,
        )

        await message.answer(
            "✅ <b>Search complete!</b>\n\n"
            f"🍀 Results found: <b>{result['total']}</b>\n"
            f"⏳ Time: <b>{result['elapsed']:.3f}s</b>\n"
            f"💵 Export price: <b>{cents_to_display(export_price_cents)}</b>\n"
            f"💳 Wallet: <b>{cents_to_display(user.wallet_balance_cents)}</b>\n"
            f"♾️ Unlimited active: <b>{'Yes' if has_unlimited(user) else 'No'}</b>\n\n"
            "Choose an export format.",
            reply_markup=search_export_menu(),
            parse_mode="HTML",
        )

        await state.clear()

    except Exception:
        logging.exception(
            "Search failed for telegram_id=%s query=%s",
            message.from_user.id,
            query,
        )
        await message.answer(
            "❌ Search failed right now. Please try again in a moment.",
            parse_mode="HTML",
        )
        await state.clear()

    finally:
        db.close()


@router.callback_query(F.data == "search:back")
async def search_back_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Search cancelled.")
    await callback.answer()


async def _run_export(callback: CallbackQuery, state: FSMContext, file_kind: str):
    data = await state.get_data()
    search_type = data.get("search_type", "keyword")
    query = (data.get("query") or "").strip()

    if not query:
        await callback.message.answer("Missing search data. Please search again.")
        await state.clear()
        await callback.answer()
        return

    db = get_session()
    temp_path = None

    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.full_name,
        )
        records = fetch_export_records(db, search_type, query)
        total = len(records)
        export_price_cents = calculate_export_price_cents(total)
        wallet_used = 0

        if not has_unlimited(user):
            if user.wallet_balance_cents < export_price_cents:
                await callback.message.answer(
                    "❌ <b>Insufficient wallet balance.</b>\n\n"
                    f"Needed: <b>{cents_to_display(export_price_cents)}</b>\n"
                    f"Current wallet: <b>{cents_to_display(user.wallet_balance_cents)}</b>\n\n"
                    f"{TOPUP_TEXT}",
                    parse_mode="HTML",
                )
                await callback.answer()
                return

            charge_wallet(
                db,
                user,
                export_price_cents,
                "export_charge",
                f"{file_kind.upper()} export for {query}",
            )
            wallet_used = export_price_cents

        if file_kind == "txt":
            content = build_safe_txt_report(query, search_type, total, records)
            suffix = ".txt"
            filename = f"{safe_query_name(query)}_safe_results.txt"
        else:
            content = build_safe_csv(records)
            suffix = ".csv"
            filename = f"{safe_query_name(query)}_safe_results.csv"

        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            suffix=suffix,
            encoding="utf-8",
            newline="",
        ) as tmp:
            tmp.write(content)
            temp_path = tmp.name

        log_search(db, user.telegram_id, search_type, query, total, 0, wallet_used)
        await state.clear()

        await callback.message.answer_document(
            FSInputFile(temp_path, filename=filename),
            caption=(
                f"Query: {query}\n"
                f"Rows exported: {total}\n"
                f"Charge: {cents_to_display(wallet_used)}\n"
                f"Wallet left: {cents_to_display(user.wallet_balance_cents)}"
            ),
        )

    except Exception:
        logging.exception(
            "Export failed for telegram_id=%s query=%s",
            callback.from_user.id,
            query,
        )
        await callback.message.answer("❌ Export failed. Please try again shortly.")
    finally:
        db.close()
        await callback.answer()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.callback_query(F.data == "export:txt")
async def export_txt_handler(callback: CallbackQuery, state: FSMContext):
    await _run_export(callback, state, "txt")


@router.callback_query(F.data == "export:csv")
async def export_csv_handler(callback: CallbackQuery, state: FSMContext):
    await _run_export(callback, state, "csv")


@router.message(F.text == "📦 Plans")
async def plans_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    await message.answer(pricing_lines(), reply_markup=plans_menu(), parse_mode="HTML")


@router.callback_query(F.data == "plan:unlimited")
async def buy_unlimited_handler(callback: CallbackQuery, state: FSMContext):
    await cancel_search_state_if_active(state)
    db = get_session()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.full_name,
        )
        if user.wallet_balance_cents < UNLIMITED_PLAN_CENTS:
            await callback.message.answer(
                "❌ <b>Not enough balance for unlimited plan.</b>\n\n"
                f"Needed: <b>{cents_to_display(UNLIMITED_PLAN_CENTS)}</b>\n"
                f"Current wallet: <b>{cents_to_display(user.wallet_balance_cents)}</b>\n\n"
                f"{TOPUP_TEXT}",
                parse_mode="HTML",
            )
            await callback.answer()
            return

        charge_wallet(
            db,
            user,
            UNLIMITED_PLAN_CENTS,
            "unlimited_plan",
            "Unlimited plan purchase",
        )
        activate_unlimited(db, user, unlimited_expiry())

        await callback.message.answer(
            f"✅ <b>Unlimited plan activated.</b>\n\n"
            f"Active until: <b>{user.unlimited_until}</b>",
            parse_mode="HTML",
        )
    except Exception:
        logging.exception("Unlimited plan purchase failed for telegram_id=%s", callback.from_user.id)
        await callback.message.answer("❌ Could not activate unlimited plan right now.")
    finally:
        db.close()
        await callback.answer()


@router.message(F.text == "💰 Top Up")
async def topup_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    await state.set_state(CryptoTopUpStates.waiting_for_coin)
    await message.answer(
        "💸 <b>Top Up</b>\n\nChoose a cryptocurrency to deposit.",
        reply_markup=crypto_topup_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "topup:back")
async def topup_back_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Top-up cancelled.")
    await callback.answer()


@router.callback_query(F.data.startswith("topupcoin:"))
async def topup_coin_handler(callback: CallbackQuery, state: FSMContext):
    coin = callback.data.split(":", 1)[1].upper()
    await state.update_data(coin=coin)
    await state.set_state(CryptoTopUpStates.waiting_for_amount)
    await callback.message.answer(
        "💸 <b>Top Up</b>\n\nEnter amount in USD. Limits: 15–6810300.74",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(CryptoTopUpStates.waiting_for_amount)
async def topup_amount_handler(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace("$", "")
    try:
        usd = Decimal(raw)
    except InvalidOperation:
        await message.answer("Please enter a valid USD amount, for example 20")
        return

    if usd < Decimal("15") or usd > Decimal("6810300.74"):
        await message.answer("Amount out of allowed range.")
        return

    data = await state.get_data()
    coin = data.get("coin", "BTC")
    db = get_session()

    try:
        user, _ = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )

        order_id = make_order_id("topup")
        result = create_invoice(
            usd_amount=usd,
            order_id=order_id,
            coin=coin,
            user_id=user.telegram_id,
            note="Wallet top-up",
        )
        result_data = result.get("result") or result

        invoice = CryptoInvoice(
            telegram_id=user.telegram_id,
            order_id=order_id,
            provider="cryptomus",
            coin=coin,
            amount_usd_cents=int(usd * 100),
            invoice_uuid=result_data.get("uuid"),
            payment_address=result_data.get("address"),
            payment_amount=str(result_data.get("amount")),
            payment_currency=result_data.get("currency") or coin,
            network=result_data.get("network"),
            qr_code=result_data.get("qr_code"),
            payment_url=result_data.get("url"),
            status=(result_data.get("status") or "pending").lower(),
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        caption = (
            "💰 <b>Pending Payment</b>\n"
            f"🏦 Address: <code>{invoice.payment_address or '-'}</code>\n\n"
            f"├ Currency: <b>{invoice.payment_currency or coin}</b>\n"
            f"├ Network: <b>{invoice.network or coin}</b>\n"
            f"├ Amount: <b>${usd}</b>\n"
            f"├ To send: <b>{invoice.payment_amount or '-'}</b>\n\n"
            "⏱ Time left: <b>~1 hour</b>\n\n"
            "❗ Double-check the amount and address."
        )

        if invoice.qr_code:
            try:
                await message.answer_photo(invoice.qr_code, caption=caption, parse_mode="HTML")
            except Exception:
                await message.answer(caption, parse_mode="HTML")
        else:
            await message.answer(caption, parse_mode="HTML")

    except Exception:
        logging.exception("Top-up creation failed for telegram_id=%s", message.from_user.id)
        await message.answer("❌ Top-up creation failed right now. Please try again later.")
    finally:
        db.close()
        await state.clear()


@router.message(F.text == "🎁 Referral")
async def referral_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    db = get_session()
    try:
        user, _ = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        me = await message.bot.get_me()
        await message.answer(
            f"🎁 <b>Your Referral Link</b>\n\n"
            f"<code>https://t.me/{me.username}?start=ref_{user.referral_code}</code>\n\n"
            "Bonus: 2 free credits for each successful referral.",
            parse_mode="HTML",
        )
    finally:
        db.close()


@router.message(F.text == "📊 Admin Stats")
async def admin_stats_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    if not await require_admin(message, state):
        return
    db = get_session()
    try:
        total_users = db.query(func.count(User.id)).scalar() or 0
        total_wallet = db.query(func.coalesce(func.sum(User.wallet_balance_cents), 0)).scalar() or 0
        active_unlimited = db.query(func.count(User.id)).filter(User.unlimited_until.is_not(None)).scalar() or 0
        total_datasets = db.query(func.count(Dataset.id)).scalar() or 0
        total_searches = db.query(func.count(SearchLog.id)).scalar() or 0
        total_transactions = db.query(func.count(WalletTransaction.id)).scalar() or 0

        await message.answer(
            "📊 <b>Admin Stats</b>\n\n"
            f"Users: <b>{total_users}</b>\n"
            f"Wallet total: <b>{cents_to_display(total_wallet)}</b>\n"
            f"Unlimited users: <b>{active_unlimited}</b>\n"
            f"Datasets: <b>{total_datasets}</b>\n"
            f"Searches logged: <b>{total_searches}</b>\n"
            f"Wallet txns: <b>{total_transactions}</b>",
            parse_mode="HTML",
        )
    finally:
        db.close()


@router.message(F.text == "📢 Broadcast")
async def broadcast_entry_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    if not await require_admin(message, state):
        return
    await state.set_state(BroadcastStates.waiting_for_message)
    await message.answer(
        "📢 <b>Broadcast</b>\n\nSend the message you want to broadcast to all users.",
        parse_mode="HTML",
    )


@router.message(BroadcastStates.waiting_for_message)
async def broadcast_capture_handler(message: Message, state: FSMContext):
    if not await require_admin(message, state):
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Please send a valid broadcast message.")
        return

    await state.update_data(broadcast_text=text)
    await message.answer(
        f"📢 <b>Broadcast Preview</b>\n\n{text}\n\nSend this to all users?",
        reply_markup=broadcast_confirm_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Broadcast cancelled.")
    await callback.answer()


@router.callback_query(F.data == "broadcast:send")
async def broadcast_send_handler(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        await callback.answer()
        return

    data = await state.get_data()
    text = (data.get("broadcast_text") or "").strip()
    if not text:
        await state.clear()
        await callback.message.answer("No broadcast message found.")
        await callback.answer()
        return

    db = get_session()
    try:
        users = db.query(User).all()
        sent = 0
        failed = 0

        for target in users:
            try:
                await callback.bot.send_message(
                    chat_id=target.telegram_id,
                    text=f"📢 Broadcast\n\n{text}",
                )
                sent += 1
            except Exception:
                failed += 1

        await callback.message.answer(
            f"✅ <b>Broadcast complete</b>\n\nSent: <b>{sent}</b>\nFailed: <b>{failed}</b>",
            parse_mode="HTML",
        )
    finally:
        db.close()
        await state.clear()
        await callback.answer()


@router.message(F.text == "➕ Give Credits")
async def give_credits_entry_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    if not await require_admin(message, state):
        return
    await state.set_state(GiveCreditsStates.waiting_for_target)
    await message.answer("➕ <b>Give Credits</b>\n\nSend target Telegram ID.", parse_mode="HTML")


@router.message(GiveCreditsStates.waiting_for_target)
async def give_credits_target_handler(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Please send a valid numeric Telegram ID.")
        return

    await state.update_data(target_telegram_id=int(text))
    await state.set_state(GiveCreditsStates.waiting_for_amount)
    await message.answer("Now send the credit amount to add.")


@router.message(GiveCreditsStates.waiting_for_amount)
async def give_credits_amount_handler(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("Please send a valid positive whole number.")
        return

    await state.update_data(amount=int(text))
    data = await state.get_data()

    await message.answer(
        f"➕ <b>Give Credits Preview</b>\n\n"
        f"Target Telegram ID: <code>{data['target_telegram_id']}</code>\n"
        f"Amount: <b>{data['amount']}</b>",
        reply_markup=give_credits_confirm_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "credits:cancel")
async def credits_cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Credit action cancelled.")
    await callback.answer()


@router.callback_query(F.data == "credits:apply")
async def credits_apply_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db = get_session()
    try:
        user = add_credits(db, int(data["target_telegram_id"]), int(data["amount"]))
        if not user:
            await callback.message.answer("User not found.")
        else:
            await callback.message.answer(f"✅ Credits added. New credits: {user.credits}")
    finally:
        db.close()
        await state.clear()
        await callback.answer()


@router.message(F.text == "💵 Add Balance")
async def add_balance_entry_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    if not await require_admin(message, state):
        return
    await state.set_state(AddBalanceStates.waiting_for_target)
    await message.answer("💵 <b>Add Balance</b>\n\nSend target Telegram ID.", parse_mode="HTML")


@router.message(AddBalanceStates.waiting_for_target)
async def add_balance_target_handler(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Please send a valid numeric Telegram ID.")
        return

    await state.update_data(target_telegram_id=int(text))
    await state.set_state(AddBalanceStates.waiting_for_amount)
    await message.answer("Now send the amount in dollars, e.g. 15 or 25.50")


@router.message(AddBalanceStates.waiting_for_amount)
async def add_balance_amount_handler(message: Message, state: FSMContext):
    text = (message.text or "").strip().replace("$", "")
    try:
        amount_cents = int(round(float(text) * 100))
    except ValueError:
        await message.answer("Please send a valid dollar amount.")
        return

    if amount_cents <= 0:
        await message.answer("Amount must be greater than zero.")
        return

    await state.update_data(amount_cents=amount_cents)
    data = await state.get_data()

    await message.answer(
        f"💵 <b>Add Balance Preview</b>\n\n"
        f"Target Telegram ID: <code>{data['target_telegram_id']}</code>\n"
        f"Amount: <b>{cents_to_display(amount_cents)}</b>",
        reply_markup=add_balance_confirm_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "balanceadd:cancel")
async def add_balance_cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Balance action cancelled.")
    await callback.answer()


@router.callback_query(F.data == "balanceadd:apply")
async def add_balance_apply_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db = get_session()
    try:
        user = add_wallet_balance(
            db,
            int(data["target_telegram_id"]),
            int(data["amount_cents"]),
            "admin_manual_topup",
        )
        if not user:
            await callback.message.answer("User not found.")
        else:
            await callback.message.answer(
                "✅ <b>Balance added</b>\n\n"
                f"Target: <code>{user.telegram_id}</code>\n"
                f"Added: <b>{cents_to_display(int(data['amount_cents']))}</b>\n"
                f"New wallet: <b>{cents_to_display(user.wallet_balance_cents)}</b>",
                parse_mode="HTML",
            )
            try:
                await callback.bot.send_message(
                    user.telegram_id,
                    f"✅ Balance added: {cents_to_display(int(data['amount_cents']))}\n"
                    f"New wallet: {cents_to_display(user.wallet_balance_cents)}",
                )
            except Exception:
                pass
    finally:
        db.close()
        await state.clear()
        await callback.answer()


@router.message(F.text == "📤 Upload")
async def upload_prompt_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    if not await require_admin(message, state):
        return
    await message.answer("Open the web uploader at your API URL + /ui")


@router.message(F.text == "👤 Account")
async def account_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    db = get_session()
    try:
        user, _ = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        text = (
            "👤 <b>Account</b>\n\n"
            f"Name: {user.full_name or '-'}\n"
            f"Username: @{user.username if user.username else '-'}\n"
            f"Telegram ID: <code>{user.telegram_id}</code>\n"
            f"Free credits: <b>{user.credits}</b>\n"
            f"Wallet: <b>{cents_to_display(user.wallet_balance_cents)}</b>\n"
            f"Unlimited active: <b>{'Yes' if has_unlimited(user) else 'No'}</b>"
        )
        if user.is_admin:
            text += "\nAdmin: Yes"
        await message.answer(text, parse_mode="HTML")
    finally:
        db.close()


@router.message(F.text == "💳 Balance")
async def balance_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    db = get_session()
    try:
        user, _ = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        await message.answer(
            "💳 <b>Balance</b>\n\n"
            f"Free credits: <b>{user.credits}</b>\n"
            f"Wallet: <b>{cents_to_display(user.wallet_balance_cents)}</b>\n"
            f"Unlimited active: <b>{'Yes' if has_unlimited(user) else 'No'}</b>\n\n"
            f"{pricing_lines()}",
            parse_mode="HTML",
        )
    finally:
        db.close()


@router.message(F.text == "ℹ️ Information")
async def info_handler(message: Message, state: FSMContext):
    await cancel_search_state_if_active(state)
    await message.answer(
        f"ℹ️ <b>{BOT_NAME}</b>\n\n"
        "This platform supports safe search previews and masked TXT/CSV exports for authorized datasets only.\n"
        f"Admin contact: {ADMIN_CONTACT}",
        parse_mode="HTML",
    )


async def main():
    init_db()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
