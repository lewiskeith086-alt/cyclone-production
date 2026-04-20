import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import PaymentInvoice, PaymentTransaction, User, WalletTransaction
from .price_service_payment import get_crypto_price_usd

BTC_RECEIVE_ADDRESS = os.getenv("BTC_RECEIVE_ADDRESS", "").strip()
USDT_TRC20_RECEIVE_ADDRESS = os.getenv("USDT_TRC20_RECEIVE_ADDRESS", "").strip()
INVOICE_EXPIRY_MINUTES = int(os.getenv("INVOICE_EXPIRY_MINUTES", "30"))
PRICE_SLIPPAGE_BPS = int(os.getenv("PRICE_SLIPPAGE_BPS", "50"))

def generate_invoice_id(asset: str) -> str:
    return f"{asset.lower()}_{uuid.uuid4().hex[:16]}"

def get_receive_address(asset: str) -> tuple[str, str]:
    asset = asset.upper().strip()
    if asset == "BTC":
        return BTC_RECEIVE_ADDRESS, "BTC"
    if asset == "USDT":
        return USDT_TRC20_RECEIVE_ADDRESS, "TRC20"
    raise ValueError("Unsupported asset")

def quantize_amount(asset: str, amount: Decimal) -> Decimal:
    if asset == "BTC":
        return amount.quantize(Decimal("0.00000001"))
    if asset == "USDT":
        return amount.quantize(Decimal("0.000001"))
    raise ValueError("Unsupported asset")

def create_payment_invoice(db: Session, telegram_id: int, asset: str, usd_cents: int) -> PaymentInvoice:
    asset = asset.upper().strip()
    price_usd = get_crypto_price_usd(asset)
    usd = Decimal(usd_cents) / Decimal("100")
    base_amount = usd / price_usd
    slippage = base_amount * Decimal(PRICE_SLIPPAGE_BPS) / Decimal("10000")
    unique_bump = Decimal(str((uuid.uuid4().int % 97) + 1)) / (Decimal("100000000") if asset == "BTC" else Decimal("1000000"))
    amount_crypto = quantize_amount(asset, base_amount + slippage + unique_bump)
    address, network = get_receive_address(asset)

    invoice = PaymentInvoice(
        invoice_id=generate_invoice_id(asset),
        telegram_id=telegram_id,
        asset=asset,
        network=network,
        amount_usd_cents=usd_cents,
        amount_crypto=str(amount_crypto),
        wallet_address=address,
        status="pending",
        confirmations=0,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=INVOICE_EXPIRY_MINUTES),
        paid_at=None,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice

def expire_old_invoices(db: Session) -> int:
    now = datetime.utcnow()
    pending = db.query(PaymentInvoice).filter(
        PaymentInvoice.status == "pending",
        PaymentInvoice.expires_at < now,
    ).all()
    for inv in pending:
        inv.status = "expired"
    db.commit()
    return len(pending)

def has_transaction(db: Session, tx_hash: str) -> bool:
    return db.query(PaymentTransaction).filter(PaymentTransaction.tx_hash == tx_hash).first() is not None

def credit_invoice(db: Session, invoice: PaymentInvoice, tx_hash: str, confirmations: int, amount_crypto: str) -> bool:
    if invoice.status == "paid" or has_transaction(db, tx_hash):
        return False
    user = db.query(User).filter(User.telegram_id == invoice.telegram_id).first()
    if not user:
        return False

    invoice.status = "paid"
    invoice.tx_hash = tx_hash
    invoice.confirmations = confirmations
    invoice.paid_at = datetime.utcnow()
    user.wallet_balance_cents += invoice.amount_usd_cents

    db.add(PaymentTransaction(
        telegram_id=invoice.telegram_id,
        invoice_id=invoice.invoice_id,
        asset=invoice.asset,
        network=invoice.network,
        wallet_address=invoice.wallet_address,
        tx_hash=tx_hash,
        amount_crypto=str(amount_crypto),
        confirmations=confirmations,
        credited_amount_usd_cents=invoice.amount_usd_cents,
    ))
    db.add(WalletTransaction(
        telegram_id=invoice.telegram_id,
        amount_cents=invoice.amount_usd_cents,
        kind="crypto_invoice_topup",
        note=f"{invoice.asset} invoice {invoice.invoice_id}",
    ))
    db.commit()
    return True
