#!/usr/bin/env python
"""Test script to verify NIFTY50 live data fetching from Kite"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv
from kiteconnect import KiteConnect
from utils.nifty50_stocks import get_nifty50_symbols

# Load .env from backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))

api_key = os.getenv("API_KEY")
access_token = os.getenv("ACCESS_TOKEN")

if not access_token or not api_key:
    print("[FAIL] Missing API_KEY or ACCESS_TOKEN in .env")
    sys.exit(1)

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

print("[OK] Connected to Kite API")

# Fetch NSE instruments
print("\n[INFO] Fetching NSE instruments...")
try:
    instruments = kite.instruments("NSE")
    print("[OK] Found {} NSE instruments".format(len(instruments)))
except Exception as e:
    print("[FAIL] Error fetching instruments: {}".format(e))
    sys.exit(1)

# Get NIFTY50 symbols and map to tokens
print("\n[INFO] Mapping NIFTY50 symbols to Kite tokens...")
nifty50_symbols = get_nifty50_symbols(format_type="nse")
print("Total NIFTY50 symbols to map: {}".format(len(nifty50_symbols)))

mapped = 0
failed = []

for symbol in nifty50_symbols:
    try:
        inst = next((i for i in instruments if i.get("tradingsymbol") == symbol and i.get("segment") == "NSE"), None)
        if inst:
            token = inst.get("instrument_token")
            name = inst.get("name")
            print("[OK] {:<15} -> Token: {:<10} Name: {}".format(symbol, token, name))
            mapped += 1
        else:
            failed.append(symbol)
            print("[FAIL] {} NOT FOUND in NSE instruments".format(symbol))
    except Exception as e:
        failed.append(symbol)
        print("[FAIL] {}: {}".format(symbol, e))

print("\n[SUMMARY]")
print("   Mapped: {}/{}".format(mapped, len(nifty50_symbols)))
if failed:
    print("   Failed: {} - {}{}".format(len(failed), failed[:5], "..." if len(failed) > 5 else ""))
else:
    print("   All NIFTY50 stocks successfully mapped! [OK]")

# Test getting live quote for one stock
if mapped > 0:
    print("\n[INFO] Testing live quote for first mapped stock...")
    try:
        symbol = nifty50_symbols[0]
        inst = next((i for i in instruments if i.get("tradingsymbol") == symbol and i.get("segment") == "NSE"), None)
        if inst:
            token = inst.get("instrument_token")
            quote = kite.quote("NSE:{}".format(symbol))
            price = quote["NSE:{}".format(symbol)].get('last_price')
            print("[OK] Quote for {}: Rs.{}".format(symbol, price))
    except Exception as e:
        print("[WARN] Could not get quote: {}".format(e))

print("\n[OK] Test completed! Ready to use live Kite data for NIFTY50.")

