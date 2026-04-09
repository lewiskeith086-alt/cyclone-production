from datetime import datetime, timedelta
from ..config import UNLIMITED_PLAN_CENTS, UNLIMITED_PLAN_DAYS
TIERS=[(20,1500),(40,2500),(70,4500),(100,6500),(150,9500),(300,15000)]
def cents_to_display(cents:int)->str: return f"${cents/100:.2f}"
def calculate_export_price_cents(row_count:int)->int:
    if row_count<=0: return 0
    for max_rows,cents in TIERS:
        if row_count<=max_rows: return cents
    extra_blocks=((row_count-300)+99)//100
    return 15000+(extra_blocks*5000)
def pricing_lines()->str:
    return "\n".join(["📦 <b>Plans & Export Pricing</b>","","1–20 rows → $15.00","21–40 rows → $25.00","41–70 rows → $45.00","71–100 rows → $65.00","101–150 rows → $95.00","151–300 rows → $150.00","301+ rows → custom stepped pricing","",f"Unlimited plan ({UNLIMITED_PLAN_DAYS} days) → {cents_to_display(UNLIMITED_PLAN_CENTS)}"])
def unlimited_expiry(): return datetime.utcnow()+timedelta(days=UNLIMITED_PLAN_DAYS)
