import secrets
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..config import DEFAULT_STARTING_CREDITS, ADMIN_IDS, REFERRAL_BONUS_CREDITS
from ..models import User, WalletTransaction
def _make_referral_code()->str: return secrets.token_hex(4)
def _ensure_referral_code(db:Session,user:User)->User:
    if user.referral_code: return user
    while True:
        code=_make_referral_code(); exists=db.query(User).filter(User.referral_code==code).first()
        if not exists:
            user.referral_code=code; db.commit(); db.refresh(user); return user
def get_or_create_user(db:Session,telegram_id:int,username:str|None,full_name:str|None):
    user=db.query(User).filter(User.telegram_id==telegram_id).first(); created=False
    if user:
        user.username=username; user.full_name=full_name; user.is_admin=telegram_id in ADMIN_IDS; db.commit(); db.refresh(user); return _ensure_referral_code(db,user), created
    user=User(telegram_id=telegram_id,username=username,full_name=full_name,credits=DEFAULT_STARTING_CREDITS,wallet_balance_cents=0,is_admin=telegram_id in ADMIN_IDS,referral_code=_make_referral_code())
    db.add(user)
    try: db.commit()
    except IntegrityError:
        db.rollback(); user=db.query(User).filter(User.telegram_id==telegram_id).first(); return _ensure_referral_code(db,user),False
    db.refresh(user); return user, True
def deduct_credit(db:Session,user:User,amount:int=1)->bool:
    if user.credits<amount: return False
    user.credits-=amount; db.commit(); db.refresh(user); return True
def add_credits(db:Session,telegram_id:int,amount:int):
    user=db.query(User).filter(User.telegram_id==telegram_id).first()
    if not user: return None
    user.credits+=amount; db.commit(); db.refresh(user); return user
def add_wallet_balance(db:Session,telegram_id:int,amount_cents:int,note:str="admin_topup"):
    user=db.query(User).filter(User.telegram_id==telegram_id).first()
    if not user: return None
    user.wallet_balance_cents+=amount_cents; db.add(WalletTransaction(telegram_id=telegram_id,amount_cents=amount_cents,kind="topup",note=note)); db.commit(); db.refresh(user); return user
def charge_wallet(db:Session,user:User,amount_cents:int,kind:str,note:str="")->bool:
    if amount_cents<=0: return True
    if user.wallet_balance_cents<amount_cents: return False
    user.wallet_balance_cents-=amount_cents; db.add(WalletTransaction(telegram_id=user.telegram_id,amount_cents=-amount_cents,kind=kind,note=note)); db.commit(); db.refresh(user); return True
def activate_unlimited(db:Session,user:User,until_dt):
    user.unlimited_until=until_dt; db.add(WalletTransaction(telegram_id=user.telegram_id,amount_cents=0,kind="unlimited_plan",note=f"Unlimited until {until_dt.isoformat()}")); db.commit(); db.refresh(user); return user
def has_unlimited(user:User)->bool: return bool(user.unlimited_until and user.unlimited_until > datetime.utcnow())
def apply_referral_bonus(db:Session,new_user:User,referral_code:str)->bool:
    if not referral_code or new_user.referred_by: return False
    referrer=db.query(User).filter(User.referral_code==referral_code).first()
    if not referrer or referrer.telegram_id==new_user.telegram_id: return False
    new_user.referred_by=referrer.telegram_id; referrer.credits+=REFERRAL_BONUS_CREDITS; db.commit(); db.refresh(referrer); return True
