from datetime import datetime
from sqlalchemy import String, BigInteger, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    credits: Mapped[int] = mapped_column(BigInteger, default=0)
    wallet_balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    unlimited_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    referral_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    source_type: Mapped[str] = mapped_column(String(50), default="upload")
    uploaded_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    record_count: Mapped[int] = mapped_column(BigInteger, default=0)
    skipped_count: Mapped[int] = mapped_column(BigInteger, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    records: Mapped[list["Record"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class Record(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(50), default="generic", index=True)
    domain: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default="upload")
    assigned_to_telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assignment_batch_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dataset: Mapped["Dataset"] = relationship(back_populates="records")


Index("ix_records_domain_lower", Record.domain)
Index("ix_records_email_lower", Record.email)
Index("ix_records_username_lower", Record.username)
Index("ix_records_phone", Record.phone)
Index("ix_records_company_lower", Record.company)
Index("ix_records_country_lower", Record.country)
Index("ix_records_assigned_to", Record.assigned_to_telegram_id)
Index("ix_records_assignment_batch", Record.assignment_batch_id)


class SearchLog(Base):
    __tablename__ = "search_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    search_type: Mapped[str] = mapped_column(String(50), index=True)
    query: Mapped[str] = mapped_column(String(255), index=True)
    results_count: Mapped[int] = mapped_column(BigInteger, default=0)
    credits_used: Mapped[int] = mapped_column(BigInteger, default=0)
    wallet_cents_used: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CryptoInvoice(Base):
    __tablename__ = "crypto_invoices"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="cryptomus")
    coin: Mapped[str] = mapped_column(String(20), index=True)
    amount_usd_cents: Mapped[int] = mapped_column(BigInteger)
    invoice_uuid: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    payment_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_currency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    credited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
