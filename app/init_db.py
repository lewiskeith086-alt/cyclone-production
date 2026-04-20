from sqlalchemy import inspect, text

from .db import Base, IS_POSTGRES, IS_SQLITE, engine
from . import models  # noqa: F401


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _exec(conn, stmt: str):
    if IS_SQLITE:
        conn.exec_driver_sql(stmt)
    else:
        conn.execute(text(stmt))


def _ensure_user_columns():
    existing = _column_names("users")
    if not existing:
        return
    with engine.begin() as conn:
        if "referral_code" not in existing:
            _exec(conn, "ALTER TABLE users ADD COLUMN referral_code VARCHAR(64)")
        if "referred_by" not in existing:
            _exec(conn, "ALTER TABLE users ADD COLUMN referred_by BIGINT")
        if "wallet_balance_cents" not in existing:
            _exec(conn, "ALTER TABLE users ADD COLUMN wallet_balance_cents BIGINT DEFAULT 0")
        if "unlimited_until" not in existing:
            _exec(conn, "ALTER TABLE users ADD COLUMN unlimited_until TIMESTAMP NULL")


def _ensure_searchlog_columns():
    existing = _column_names("search_logs")
    if not existing:
        return
    with engine.begin() as conn:
        if "wallet_cents_used" not in existing:
            _exec(conn, "ALTER TABLE search_logs ADD COLUMN wallet_cents_used BIGINT DEFAULT 0")


def _ensure_record_columns():
    existing = _column_names("records")
    if not existing:
        return
    with engine.begin() as conn:
        if "country" not in existing:
            _exec(conn, "ALTER TABLE records ADD COLUMN country VARCHAR(100)")
        if "assigned_to_telegram_id" not in existing:
            _exec(conn, "ALTER TABLE records ADD COLUMN assigned_to_telegram_id BIGINT")
        if "assigned_at" not in existing:
            _exec(conn, "ALTER TABLE records ADD COLUMN assigned_at TIMESTAMP NULL")
        if "assignment_batch_id" not in existing:
            _exec(conn, "ALTER TABLE records ADD COLUMN assignment_batch_id VARCHAR(64)")
        try:
            _exec(conn, "ALTER TABLE records ALTER COLUMN url TYPE TEXT")
        except Exception:
            pass
        try:
            _exec(conn, "ALTER TABLE records ALTER COLUMN notes TYPE TEXT")
        except Exception:
            pass


def _create_perf_indexes():
    if not IS_POSTGRES:
        return
    stmts = [
        "CREATE INDEX IF NOT EXISTS idx_records_domain_lower_pg ON records (lower(domain))",
        "CREATE INDEX IF NOT EXISTS idx_records_email_lower_pg ON records (lower(email))",
        "CREATE INDEX IF NOT EXISTS idx_records_username_lower_pg ON records (lower(username))",
        "CREATE INDEX IF NOT EXISTS idx_records_company_lower_pg ON records (lower(company))",
        "CREATE INDEX IF NOT EXISTS idx_records_country_lower_pg ON records (lower(country))",
        "CREATE INDEX IF NOT EXISTS idx_records_phone_pg ON records (phone)",
        "CREATE INDEX IF NOT EXISTS idx_records_assigned_to_pg ON records (assigned_to_telegram_id)",
        "CREATE INDEX IF NOT EXISTS idx_records_assignment_batch_pg ON records (assignment_batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_search_logs_telegram_created_pg ON search_logs (telegram_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_wallet_tx_telegram_id_pg ON wallet_transactions (telegram_id)",
        "CREATE INDEX IF NOT EXISTS idx_crypto_invoices_telegram_id_pg ON crypto_invoices (telegram_id)",
        "CREATE INDEX IF NOT EXISTS idx_crypto_invoices_status_pg ON crypto_invoices (status)",
        "CREATE INDEX IF NOT EXISTS idx_payment_invoices_status_pg ON payment_invoices (status)",
        "CREATE INDEX IF NOT EXISTS idx_payment_invoices_telegram_pg ON payment_invoices (telegram_id)",
        "CREATE INDEX IF NOT EXISTS idx_payment_invoices_expires_pg ON payment_invoices (expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_payment_transactions_invoice_pg ON payment_transactions (invoice_id)",
        "CREATE INDEX IF NOT EXISTS idx_payment_transactions_txhash_pg ON payment_transactions (tx_hash)",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass


def _sync_postgres_sequences():
    if not IS_POSTGRES:
        return
    tables = [
        "users",
        "datasets",
        "records",
        "search_logs",
        "wallet_transactions",
        "crypto_invoices",
        "payment_invoices",
        "payment_transactions",
    ]
    with engine.begin() as conn:
        for table in tables:
            seq_name = conn.execute(
                text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
                {"table_name": table},
            ).scalar()
            if not seq_name:
                continue
            max_id = conn.execute(text(f'SELECT COALESCE(MAX(id), 0) FROM "{table}"')).scalar() or 0
            if max_id <= 0:
                conn.execute(
                    text("SELECT setval(:seq_name, :new_value, :is_called)"),
                    {"seq_name": seq_name, "new_value": 1, "is_called": False},
                )
            else:
                conn.execute(
                    text("SELECT setval(:seq_name, :new_value, :is_called)"),
                    {"seq_name": seq_name, "new_value": max_id, "is_called": True},
                )


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_user_columns()
    _ensure_searchlog_columns()
    _ensure_record_columns()
    _create_perf_indexes()
    _sync_postgres_sequences()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
