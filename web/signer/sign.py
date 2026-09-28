"""blockchain signer worker
Anchors daily Merkle roots to a low-cost EVM chain (Polygon/BNB) and
reports the tx hash back to the PHP API.

WHY THIS IS SPLIT:
  * The PHP server NEVER holds a private key. Shared hosting + keys = bad.
  * This worker runs ONCE A DAY on your PC, phone (Termux), or a tiny VPS.

SETUP
  1. pip install -r requirements.txt        (web3, requests)
  2. Create a wallet, fund with a tiny amount of MATIC/BNB (~PHP 30 lasts)
  3. Set the environment variables below (or a .env near this file)

RUN
  python sign.py            # anchor any pending days, then exit
  python sign.py --loop     # poll every 10 minutes forever (for cron/VPS)
  python sign.py --dry-run  # print planned tx without sending

ENV VARS
  API_BASE        e.g. https://yourdomain.com/web/api  (no trailing slash)
  ANCHOR_SECRET   same value as web/api/config.php ANCHOR_SECRET
  RPC_URL         Polygon: https://polygon-rpc.com   BNB: https://bsc-dataseed.binance.org
  CHAIN_NAME      polygon | bsc
  PRIVATE_KEY     the wallet private key (0x...)
  MAX_GWEI        optional max gas price cap (default 200)
"""

import hashlib
import os
import sys
import time
from pathlib import Path

import requests
from web3 import Web3

API_BASE = os.environ.get("API_BASE", "").rstrip("/")
SECRET = os.environ.get("ANCHOR_SECRET", "")
RPC_URL = os.environ.get("RPC_URL", "https://polygon-rpc.com")
CHAIN = os.environ.get("CHAIN_NAME", "polygon")
PRIV = os.environ.get("PRIVATE_KEY", "")
MAX_GWEI = float(os.environ.get("MAX_GWEI", "200"))


def headers():
    return {"X-Anchor-Secret": SECRET, "Content-Type": "application/json"}


def fetch_pending():
    r = requests.get(f"{API_BASE}?r=anchors/pending", headers=headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("anchors", [])


def confirm(date, tx_hash):
    r = requests.post(
        f"{API_BASE}?r=anchors/confirm",
        headers=headers(),
        json={"date": date, "tx_hash": tx_hash, "chain": CHAIN, "status": "anchored"},
        timeout=30,
    )
    r.raise_for_status()


def anchor(w3, account, root_hex):
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    gas_price = w3.eth.gas_price
    if gas_price > MAX_GWEI * 10**9:
        raise RuntimeError(f"gas price {gas_price} exceeds MAX_GWEI={MAX_GWEI}")

    tx = {
        "nonce": nonce,
        "to": account.address,  # self-transfer carries the proof in `data`
        "value": 0,
        "data": f"0x{root_hex}",
        "gas": 21000,
        "gasPrice": gas_price,
        "chainId": w3.eth.chain_id,
    }
    signed = account.sign_transaction(tx)
    return w3.eth.send_raw_transaction(signed.raw_transaction).hex()


def main():
    if not PRIV:
        sys.exit("PRIVATE_KEY not set (see docstring). Aborting.")

    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        sys.exit(f"Cannot reach RPC: {RPC_URL}")

    account = w3.eth.account.from_key(PRIV)
    print(f"signer: {account.address} on {CHAIN} ({w3.eth.chain_id})")

    pending = fetch_pending()
    if not pending:
        print("no pending anchors")
        return

    for p in pending:
        root = p["merkle_root"]
        if len(root) != 64:
            print(f"skip {p['anchor_date']}: bad root")
            continue
        print(f"anchoring {p['anchor_date']} root={root} total={p['grand_total']}")

        if "--dry-run" in sys.argv or "--dry-run" in os.environ.get("ANCHOR_DRY", ""):
            print(f"  [dry-run] would send 0x{root}")
            continue

        txh = anchor(w3, account, root)
        print(f"  tx={txh}")
        receipt = w3.eth.wait_for_transaction_receipt(txh, timeout=300)
        if receipt.status != 1:
            print(f"  FAILED status={receipt.status}")
            continue
        confirm(p["anchor_date"], txh)
        print(f"  confirmed on-chain: {txh}")


if __name__ == "__main__":
    try:
        if "--loop" in sys.argv:
            while True:
                main()
                time.sleep(600)
        else:
            main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)