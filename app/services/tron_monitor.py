from decimal import Decimal
import os
import requests

TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY", "").strip()
USDT_TRC20_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"

def _headers():
    return {"TRON-PRO-API-KEY": TRONGRID_API_KEY} if TRONGRID_API_KEY else {}

def get_trc20_transfers(address: str) -> list[dict]:
    resp = requests.get(
        f"https://api.trongrid.io/v1/accounts/{address}/transactions/trc20",
        params={"limit": 200, "only_to": "true", "contract_address": USDT_TRC20_CONTRACT},
        headers=_headers(),
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])

def find_matching_usdt_payment(address: str, expected_amount: Decimal) -> dict | None:
    for tx in get_trc20_transfers(address):
        to_addr = (tx.get("to") or "").strip()
        token_info = tx.get("token_info") or {}
        decimals = int(token_info.get("decimals", 6))
        amount = Decimal(str(tx.get("value", "0"))) / (Decimal(10) ** decimals)
        confirmed = bool(tx.get("confirmed", True))
        if to_addr == address and amount >= expected_amount and confirmed:
            return {"tx_hash": tx.get("transaction_id"), "amount_crypto": str(amount), "confirmations": 1}
    return None
