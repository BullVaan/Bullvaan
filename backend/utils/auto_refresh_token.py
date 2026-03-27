"""
Automated Zerodha Access Token Refresh
=======================================
Uses Playwright to log in to Zerodha, get a new access_token,
then updates Render's environment variable and triggers a redeploy.

Required environment variables (set as GitHub Actions secrets):
  ZERODHA_USER_ID        - Your Zerodha client ID (e.g. AB1234)
  ZERODHA_PASSWORD       - Your Zerodha password
  ZERODHA_TOTP_SECRET    - Base32 TOTP secret from Zerodha 2FA setup
  API_KEY                - Zerodha Kite Connect API key
  API_SECRET             - Zerodha Kite Connect API secret
  RENDER_API_KEY         - Render API key (from Render dashboard → Account → API Keys)
  RENDER_SERVICE_ID      - Render service ID (from service URL: dashboard.render.com/web/srv-XXXX)
"""

import os
import time
import pyotp
import requests
from kiteconnect import KiteConnect
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Config from env ──────────────────────────────────────────────────────────
USER_ID       = os.environ["ZERODHA_USER_ID"]
PASSWORD      = os.environ["ZERODHA_PASSWORD"]
TOTP_SECRET   = os.environ["ZERODHA_TOTP_SECRET"]
API_KEY       = os.environ["API_KEY"]
API_SECRET    = os.environ["API_SECRET"]
RENDER_API_KEY     = os.environ["RENDER_API_KEY"]
RENDER_SERVICE_ID  = os.environ["RENDER_SERVICE_ID"]

REDIRECT_URL = "https://127.0.0.1"  # Must match what you set in Kite Connect app settings


def get_request_token() -> str:
    """
    Automates Zerodha browser login and returns the request_token.
    Steps:
      1. Open Kite Connect login URL
      2. Fill user_id + password
      3. Fill TOTP
      4. Capture the redirect URL containing request_token
    """
    kite = KiteConnect(api_key=API_KEY)
    login_url = kite.login_url()
    print(f"Navigating to: {login_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        request_token = None

        # Listen to ALL outgoing requests — catches the redirect to 127.0.0.1:8000
        # regardless of port or path, without needing to match a glob pattern
        def on_request(request):
            nonlocal request_token
            url = request.url
            print(f"[REQUEST] {url[:120]}")
            if "request_token=" in url:
                token = url.split("request_token=")[1].split("&")[0]
                request_token = token
                print(f"Captured request_token: {token[:8]}...")

        page.on("request", on_request)

        # Navigate to Zerodha login
        page.goto(login_url, wait_until="networkidle", timeout=30000)
        print(f"Page after goto: {page.url}")

        # Fill user ID and password
        page.fill('input[type="text"]', USER_ID)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button[type="submit"]')
        print("Submitted login form")

        # Wait for TOTP screen
        page.wait_for_selector(
            'input[type="number"], input[placeholder*="TOTP"], input[placeholder*="OTP"]',
            timeout=15000
        )
        print(f"TOTP page reached: {page.url}")
        time.sleep(1)

        # Generate TOTP (pad secret to valid base32 length)
        padded_secret = TOTP_SECRET.upper().strip().replace(' ', '').replace('-', '')
        padded_secret += '=' * (-len(padded_secret) % 8)

        # Generate fresh TOTP right before typing to avoid 30s window expiry
        totp = pyotp.TOTP(padded_secret)
        totp_code = totp.now()
        print(f"Generated TOTP: {totp_code}")

        # Find TOTP input and type digit-by-digit (Zerodha uses individual dot fields)
        totp_input = (page.query_selector('input[type="number"]') or
                      page.query_selector('input[placeholder*="TOTP"]') or
                      page.query_selector('input[placeholder*="OTP"]'))
        if not totp_input:
            raise RuntimeError("Could not find TOTP input field")

        totp_input.click()
        for digit in totp_code:
            totp_input.type(digit, delay=100)
        print("Typed TOTP digits")
        page.screenshot(path="/tmp/zerodha_debug.png")
        print("Screenshot saved to /tmp/zerodha_debug.png")
        if totp_input.evaluate("el => el.value.length") < 6:
            raise RuntimeError("TOTP input incomplete")

        # Click the Continue / Submit button
        time.sleep(0.5)
        try:
            submit_btn = (page.query_selector('button[type="submit"]') or
                          page.query_selector('button:has-text("Continue")') or
                          page.query_selector('button:has-text("Login")'))
            if submit_btn:
                submit_btn.click()
                print("Clicked submit button")
        except Exception as e:
            print(f"Submit click failed (may auto-submit): {e}")

        # Wait up to 30s for request_token to appear in any request URL
        for i in range(60):
            if request_token:
                break
            time.sleep(0.5)
            # Also check current page URL
            try:
                current = page.url
                if "request_token=" in current:
                    request_token = current.split("request_token=")[1].split("&")[0]
                    print(f"Captured request_token from page URL: {request_token[:8]}...")
                    break
                if i % 10 == 0:
                    print(f"Still waiting... current URL: {current[:120]}")
            except Exception:
                pass

        # Save screenshot for debugging if token not found
        if not request_token:
            try:
                page.screenshot(path="/tmp/zerodha_debug.png")
                print("Screenshot saved to /tmp/zerodha_debug.png")
                print(f"Final page URL: {page.url}")
                print(f"Final page title: {page.title()}")
            except Exception as e:
                print(f"Screenshot failed: {e}")

        browser.close()

    if not request_token:
        raise RuntimeError("Failed to capture request_token after login. Check credentials/TOTP secret.")

    return request_token


def generate_access_token(request_token: str) -> str:
    """Exchange request_token for access_token via Kite SDK."""
    kite = KiteConnect(api_key=API_KEY)
    session = kite.generate_session(request_token, api_secret=API_SECRET)
    access_token = session["access_token"]
    print(f"New access_token generated: {access_token[:8]}...")
    return access_token


def get_current_render_env_vars() -> list:
    """Fetch all current env vars from Render service."""
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/env-vars"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()  # list of {"key": ..., "value": ...}


def update_render_access_token(new_token: str):
    """
    Update ACCESS_TOKEN env var on Render.
    Render's PUT /env-vars replaces the complete list, so we fetch first then update.
    """
    current = get_current_render_env_vars()

    # Replace ACCESS_TOKEN, keep everything else unchanged
    updated = []
    found = False
    for var in current:
        if var.get("key") == "ACCESS_TOKEN":
            updated.append({"key": "ACCESS_TOKEN", "value": new_token})
            found = True
        else:
            updated.append({"key": var["key"], "value": var["value"]})

    if not found:
        updated.append({"key": "ACCESS_TOKEN", "value": new_token})

    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/env-vars"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    resp = requests.put(url, headers=headers, json=updated, timeout=15)
    resp.raise_for_status()
    print("Render ACCESS_TOKEN updated successfully.")


def trigger_render_deploy():
    """Trigger a new deployment on Render to pick up the updated env var."""
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers, json={"clearCache": "do_not_clear"}, timeout=15)
    resp.raise_for_status()
    deploy_id = resp.json().get("id", "unknown")
    print(f"Render deploy triggered: {deploy_id}")


def main():
    print("=== Zerodha Auto Token Refresh ===")
    print("Step 1: Getting request_token via browser automation...")
    request_token = get_request_token()

    print("Step 2: Generating access_token...")
    access_token = generate_access_token(request_token)

    print("Step 3: Updating ACCESS_TOKEN on Render...")
    update_render_access_token(access_token)

    print("Step 4: Triggering Render redeploy...")
    trigger_render_deploy()

    print("\nDone! New access_token is live on Render.")


if __name__ == "__main__":
    main()
