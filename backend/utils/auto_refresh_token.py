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

DEBUG_DIR = "/tmp"

# ── Config from env ──────────────────────────────────────────────────────────
USER_ID       = os.environ["ZERODHA_USER_ID"]
PASSWORD      = os.environ["ZERODHA_PASSWORD"]
TOTP_SECRET   = os.environ["ZERODHA_TOTP_SECRET"]
API_KEY       = os.environ["API_KEY"]
API_SECRET    = os.environ["API_SECRET"]
RENDER_API_KEY     = os.environ["RENDER_API_KEY"]
RENDER_SERVICE_ID  = os.environ["RENDER_SERVICE_ID"]

REDIRECT_URL = "https://127.0.0.1"  # Must match what you set in Kite Connect app settings


# ── Debug helpers ────────────────────────────────────────────────────────────

def _save_debug(page, label: str):
    """Save a screenshot and the full page HTML for a given step."""
    try:
        page.screenshot(path=f"{DEBUG_DIR}/zerodha_{label}.png")
        html = page.content()
        with open(f"{DEBUG_DIR}/zerodha_{label}.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[debug] Saved screenshot + HTML: {DEBUG_DIR}/zerodha_{label}.*")

        # Log all visible inputs so we can confirm selectors
        inputs = page.query_selector_all("input")
        for idx, inp in enumerate(inputs):
            try:
                itype  = inp.get_attribute("type") or "text"
                iid    = inp.get_attribute("id") or ""
                iname  = inp.get_attribute("name") or ""
                iplace = inp.get_attribute("placeholder") or ""
                iauto  = inp.get_attribute("autocomplete") or ""
                print(f"  input[{idx}] type={itype!r} id={iid!r} name={iname!r} placeholder={iplace!r} autocomplete={iauto!r}")
            except Exception:
                pass
    except Exception as e:
        print(f"[debug] Could not save debug files: {e}")


def _fill_totp(page, totp_code: str):
    """
    Fill the TOTP code on the Zerodha 2FA screen.
    Handles both:
      - 6 individual digit boxes  (type=number, older UI)
      - Single External TOTP field (type=text/password, newer UI)
    """
    number_inputs = page.query_selector_all('input[type="number"]')
    print(f"Found {len(number_inputs)} number input(s)")

    if len(number_inputs) >= 6:
        # Older UI: 6 separate digit boxes
        for i, digit in enumerate(totp_code):
            number_inputs[i].click()
            number_inputs[i].fill(digit)
            time.sleep(0.1)
        print("Filled 6 individual TOTP digit boxes")
        return

    if len(number_inputs) == 1:
        number_inputs[0].triple_click()
        number_inputs[0].fill(totp_code)
        print("Filled single number TOTP input")
        return

    # Newer Zerodha UI: single text input for External TOTP
    single = (
        page.query_selector('input[autocomplete="one-time-code"]') or
        page.query_selector('input[id*="totp" i]') or
        page.query_selector('input[name*="totp" i]') or
        page.query_selector('input[placeholder*="TOTP" i]') or
        page.query_selector('input[placeholder*="OTP" i]') or
        page.query_selector('input[type="text"]') or
        page.query_selector('input[type="password"]') or
        page.query_selector('input')  # absolute last resort: first input on page
    )

    if single:
        single.triple_click()   # clear any existing value first
        single.fill(totp_code)
        print(f"Filled TOTP via selector: {single.get_attribute('type')!r} id={single.get_attribute('id')!r}")
    else:
        page.keyboard.type(totp_code)
        print("Typed TOTP via keyboard (no input found)")


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
        _save_debug(page, "01_login_page")

        # Fill user ID and password
        page.fill('input[type="text"]', USER_ID)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button[type="submit"]')
        print("Submitted login form")

        # Wait for TOTP screen — Zerodha uses either individual digit boxes or
        # a single "External TOTP" text/number input depending on account settings.
        page.wait_for_selector(
            'input[type="number"], input[type="text"], input[placeholder*="TOTP"], input[placeholder*="OTP"], input[autocomplete="one-time-code"]',
            timeout=15000
        )
        print(f"TOTP page reached: {page.url}")
        _save_debug(page, "02_totp_page")  # saves screenshot + HTML for inspection

        # Build and validate the TOTP secret
        padded_secret = TOTP_SECRET.upper().strip().replace(' ', '').replace('-', '')
        padded_secret += '=' * (-len(padded_secret) % 8)
        totp_obj = pyotp.TOTP(padded_secret)

        # Generate TOTP as close to submission as possible.
        # If we are in the last 3 seconds of the 30s window, wait for the next
        # window so we never submit a code that expires mid-flight.
        remaining = 30 - (int(time.time()) % 30)
        if remaining <= 3:
            print(f"TOTP window expires in {remaining}s — waiting for next window...")
            time.sleep(remaining + 1)

        totp_code = totp_obj.now()
        print(f"Generated TOTP (first 2 digits): {totp_code[:2]}****  (window remaining: {30 - (int(time.time()) % 30)}s)")

        _fill_totp(page, totp_code)
        _save_debug(page, "03_after_totp_fill")

        # Zerodha auto-submits when all 6 digit boxes are filled.
        # Only click submit manually if not already redirected.
        time.sleep(1.0)
        if "request_token=" not in page.url:
            try:
                submit_btn = (
                    page.query_selector('button[type="submit"]') or
                    page.query_selector('button:has-text("Continue")') or
                    page.query_selector('button:has-text("Login")')
                )
                if submit_btn:
                    submit_btn.click()
                    print("Clicked submit button")
            except Exception as e:
                print(f"Submit click note (may have auto-submitted): {e}")

        # Wait up to 30s for request_token to appear (via on_request handler or URL)
        for i in range(60):
            if request_token:
                break
            time.sleep(0.5)
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
            _save_debug(page, "04_final_state")
            print(f"Final page URL: {page.url}")
            print(f"Final page title: {page.title()}")

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
