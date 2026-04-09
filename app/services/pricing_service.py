from datetime import datetime, timedelta

UNLIMITED_PLAN_CENTS = 75000
UNLIMITED_PLAN_DAYS = 30


def cents_to_display(cents: int) -> str:
    return f"${cents / 100:.2f}"


def calculate_export_price_cents(row_count: int) -> int:
    if row_count <= 0:
        return 0
    if row_count < 10:
        return 500
    if row_count < 100:
        return 1500
    if row_count <= 2000:
        return 3000
    return 6500


def pricing_lines() -> str:
    return "\n".join(
        [
            "📦 <b>Plans & Export Pricing</b>",
            "",
            "1–9 lines → $5.00",
            "10–99 lines → $15.00",
            "100–2000 lines → $30.00",
            "2001+ lines → $65.00",
            "",
            f"Unlimited plan ({UNLIMITED_PLAN_DAYS} days) → {cents_to_display(UNLIMITED_PLAN_CENTS)}",
        ]
    )


def unlimited_expiry():
    return datetime.utcnow() + timedelta(days=UNLIMITED_PLAN_DAYS)
