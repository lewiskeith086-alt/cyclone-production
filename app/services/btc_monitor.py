from decimal import Decimal
import os
import requests

BTC_CONFIRMATIONS_REQUIRED = int(os.getenv("BTC_CONFIRMATIONS_REQUIRED", "1"))

def get_btc_address_txs(address: str) -> list[dict]:
    resp = requests.get(f"https://blockstream.info/api/address/{address}/txs", timeout=20)
    resp.raise_for_status()
    return resp.json()

def tx_confirmations(tx: dict) -> int:
    status = tx.get("status") or {}
    if not status.get("confirmed"):
        return 0
    block_height = status.get("block_height")
    tip_resp = requests.get("https://blockstream.info/api/blocks/tip/height", timeout=20)
    tip_resp.raise_for_status()
    tip = int(tip_resp.text.strip())
    return max(0, tip - int(block_height) + 1)

def sum_received_to_address(tx: dict, address: str) -> Decimal:
    sats = 0
    for vout in tx.get("vout", []):
        if vout.get("scriptpubkey_address") == address:
            sats += int(vout.get("value", 0))
    return Decimal(sats) / Decimal("100000000")

def find_matching_btc_payment(address: str, expected_amount: Decimal) -> dict | None:
    for tx in get_btc_address_txs(address):
        received = sum_received_to_address(tx, address)
        if received >= expected_amount:
            confs = tx_confirmations(tx)
            if confs >= BTC_CONFIRMATIONS_REQUIRED:
                return {"tx_hash": tx.get("txid"), "amount_crypto": str(received), "confirmations": confs}
    return None
