from kiteconnect import KiteConnect

api_key = "yi4arzszbdqujyt0"
api_secret = "sqbpnp0s1li9cwal29j2nsntuh0c52kw"

kite = KiteConnect(api_key=api_key)

# Step 1: Print login URL
print("Login URL:", kite.login_url())

# Step 2: After login, paste your request_token below
request_token = input("Paste your request_token from redirect URL: ")

# Step 3: Exchange for access token
if request_token:
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    print("Access Token:", access_token)
else:
    print("No request_token provided.")
