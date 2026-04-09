import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cyclone_ulp_searcher.db")
DEFAULT_STARTING_CREDITS = int(os.getenv("DEFAULT_STARTING_CREDITS", "2"))
RESULTS_PREVIEW_LIMIT = int(os.getenv("RESULTS_PREVIEW_LIMIT", "25"))
EXPORT_FETCH_LIMIT = int(os.getenv("EXPORT_FETCH_LIMIT", "1000"))
BOT_NAME = os.getenv("BOT_NAME", "CYCLONE ULP SEARCHER")
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "@TimHedrick")
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")
REFERRAL_BONUS_CREDITS = int(os.getenv("REFERRAL_BONUS_CREDITS", "2"))
UNLIMITED_PLAN_CENTS = int(os.getenv("UNLIMITED_PLAN_CENTS", "75000"))
UNLIMITED_PLAN_DAYS = int(os.getenv("UNLIMITED_PLAN_DAYS", "30"))
CRYPTOMUS_MERCHANT_UUID = os.getenv("CRYPTOMUS_MERCHANT_UUID", "")
CRYPTOMUS_PAYMENT_API_KEY = os.getenv("CRYPTOMUS_PAYMENT_API_KEY", "")
CRYPTOMUS_CALLBACK_URL = os.getenv("CRYPTOMUS_CALLBACK_URL", "")
CRYPTOMUS_RETURN_URL = os.getenv("CRYPTOMUS_RETURN_URL", "")
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()}
