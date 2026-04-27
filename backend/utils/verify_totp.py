"""
TOTP Secret Verifier
====================
Run this locally to confirm your ZERODHA_TOTP_SECRET is correct BEFORE
pushing it to GitHub Secrets.

Usage:
    cd backend
    pip install pyotp python-dotenv
    python utils/verify_totp.py

OR pass the secret directly:
    python utils/verify_totp.py JBSWY3DPEHPK3PXP
"""

import sys
import time
import pyotp
from dotenv import load_dotenv
import os

load_dotenv()

def verify(secret: str):
    # Normalize exactly as the main script does
    padded = secret.upper().strip().replace(' ', '').replace('-', '')
    padded += '=' * (-len(padded) % 8)

    try:
        totp = pyotp.TOTP(padded)
    except Exception as e:
        print(f"ERROR: Invalid TOTP secret — {e}")
        print("Make sure ZERODHA_TOTP_SECRET is the base32 text key from Zerodha,")
        print("NOT a URL or QR code image.")
        return

    print("=" * 50)
    print("Compare the code below with your authenticator app.")
    print("They should match exactly at the same second.")
    print("=" * 50)

    for _ in range(6):  # show 6 refreshes so you can catch the changeover
        remaining = 30 - (int(time.time()) % 30)
        code = totp.now()
        print(f"  Current TOTP: {code}   (window expires in {remaining:2d}s)")
        time.sleep(5)

    print()
    print("If the codes above MATCH your app → secret is correct.")
    print("If they DO NOT match → update ZERODHA_TOTP_SECRET in GitHub Secrets.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        secret = sys.argv[1]
    else:
        secret = os.getenv("ZERODHA_TOTP_SECRET", "")

    if not secret:
        secret = input("Paste your ZERODHA_TOTP_SECRET (base32 key): ").strip()

    verify(secret)
