from decimal import Decimal
import os
import requests

COINGECKO_TIMEOUT_SECONDS = int(os.getenv("COINGECKO_TIMEOUT_SECONDS", "20"))

def get_crypto_price_usd(asset: str) -> Decimal:
    asset = asset.upper().strip()
    mapping = {"BTC": "bitcoin", "USDT": "tether"}
    coin_id = mapping.get(asset)
    if not coin_id:
        raise ValueError(f"Unsupported asset: {asset}")
    resp = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": coin_id, "vs_currencies": "usd"},
        timeout=COINGECKO_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    return Decimal(str(data[coin_id]["usd"]))
