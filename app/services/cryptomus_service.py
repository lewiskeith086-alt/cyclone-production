import base64, hashlib, json, os, uuid
from decimal import Decimal
from typing import Any
import requests
CRYPTOMUS_BASE_URL="https://api.cryptomus.com"
CRYPTOMUS_MERCHANT_UUID=os.getenv("CRYPTOMUS_MERCHANT_UUID","")
CRYPTOMUS_PAYMENT_API_KEY=os.getenv("CRYPTOMUS_PAYMENT_API_KEY","")
CRYPTOMUS_CALLBACK_URL=os.getenv("CRYPTOMUS_CALLBACK_URL","")
CRYPTOMUS_RETURN_URL=os.getenv("CRYPTOMUS_RETURN_URL","")
SUPPORTED_COINS=["BTC","USDT","USDC","XMR","TRX","TON","SOL","SHIB","POL","LTC","ETH","DOGE","DASH","DAI","BNB","BCH","AVAX"]
def _sign_payload(payload:dict[str,Any], api_key:str)->str:
    raw=base64.b64encode(json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode("utf-8")).decode("utf-8")
    return hashlib.md5(f"{raw}{api_key}".encode("utf-8")).hexdigest()
def _headers(payload:dict[str,Any])->dict[str,str]:
    if not CRYPTOMUS_MERCHANT_UUID or not CRYPTOMUS_PAYMENT_API_KEY: raise RuntimeError("Missing Cryptomus credentials")
    return {"merchant":CRYPTOMUS_MERCHANT_UUID,"sign":_sign_payload(payload,CRYPTOMUS_PAYMENT_API_KEY),"Content-Type":"application/json"}
def create_invoice(*,usd_amount:Decimal,order_id:str,coin:str,user_id:int,note:str="Wallet top-up")->dict[str,Any]:
    coin=coin.upper().strip()
    if coin not in SUPPORTED_COINS: raise ValueError(f"Unsupported coin: {coin}")
    payload={"amount":str(usd_amount),"currency":"USD","order_id":order_id,"to_currency":coin,"url_callback":CRYPTOMUS_CALLBACK_URL,"url_return":CRYPTOMUS_RETURN_URL,"is_payment_multiple":False,"lifetime":3600,"additional_data":json.dumps({"telegram_id":user_id,"note":note})}
    resp=requests.post(f"{CRYPTOMUS_BASE_URL}/v1/payment",json=payload,headers=_headers(payload),timeout=30); resp.raise_for_status(); return resp.json()
def payment_info(*,uuid_value:str|None=None,order_id:str|None=None)->dict[str,Any]:
    payload={}
    if uuid_value: payload["uuid"]=uuid_value
    if order_id: payload["order_id"]=order_id
    if not payload: raise ValueError("uuid_value or order_id is required")
    resp=requests.post(f"{CRYPTOMUS_BASE_URL}/v1/payment/info",json=payload,headers=_headers(payload),timeout=30); resp.raise_for_status(); return resp.json()
def verify_webhook_signature(body:dict[str,Any])->bool:
    sign=body.get("sign")
    if not sign or not CRYPTOMUS_PAYMENT_API_KEY: return False
    copied=dict(body); copied.pop("sign",None)
    return _sign_payload(copied,CRYPTOMUS_PAYMENT_API_KEY)==sign
def make_order_id(prefix:str="topup")->str: return f"{prefix}_{uuid.uuid4().hex[:24]}"
