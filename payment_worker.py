import asyncio
import logging
import os
from decimal import Decimal

from aiogram import Bot

from app.db import get_session
from app.init_db import init_db
from app.models import PaymentInvoice
from app.services.btc_monitor import find_matching_btc_payment
from app.services.payment_service import credit_invoice, expire_old_invoices
from app.services.tron_monitor import find_matching_usdt_payment

logging.basicConfig(level=logging.INFO)

PAYMENT_POLL_INTERVAL_SECONDS = int(os.getenv("PAYMENT_POLL_INTERVAL_SECONDS", "30"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()


async def notify_user_payment_received(bot: Bot, invoice: PaymentInvoice):
    try:
        await bot.send_message(
            chat_id=invoice.telegram_id,
            text=(
                "✅ <b>Payment received. Balance updated.</b>\n\n"
                f"Invoice ID: <code>{invoice.invoice_id}</code>\n"
                f"Asset: <b>{invoice.asset}</b>\n"
                f"Network: <b>{invoice.network}</b>\n"
                f"Amount: <b>${invoice.amount_usd_cents / 100:.2f}</b>\n"
                f"Status: <b>{invoice.status.upper()}</b>\n"
                f"Confirmations: <b>{invoice.confirmations}</b>"
            ),
            parse_mode="HTML",
        )
    except Exception:
        logging.exception("Failed to notify telegram_id=%s", invoice.telegram_id)


async def process_pending_invoices(bot: Bot):
    db = get_session()
    try:
        expired_count = expire_old_invoices(db)
        if expired_count:
            logging.info("Expired %s old invoices", expired_count)

        pending = db.query(PaymentInvoice).filter(PaymentInvoice.status == "pending").all()
        for invoice in pending:
            expected = Decimal(str(invoice.amount_crypto))
            match = None

            if invoice.asset == "BTC":
                match = find_matching_btc_payment(invoice.wallet_address, expected)
            elif invoice.asset == "USDT" and invoice.network == "TRC20":
                match = find_matching_usdt_payment(invoice.wallet_address, expected)

            if not match:
                continue

            ok = credit_invoice(
                db,
                invoice,
                tx_hash=match["tx_hash"],
                confirmations=int(match["confirmations"]),
                amount_crypto=str(match["amount_crypto"]),
            )
            if ok:
                db.refresh(invoice)
                logging.info("Credited invoice %s for telegram_id=%s", invoice.invoice_id, invoice.telegram_id)
                await notify_user_payment_received(bot, invoice)
    except Exception:
        logging.exception("Payment worker loop failed")
    finally:
        db.close()


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing for payment worker notifications")

    bot = Bot(BOT_TOKEN)
    try:
        while True:
            await process_pending_invoices(bot)
            await asyncio.sleep(PAYMENT_POLL_INTERVAL_SECONDS)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
