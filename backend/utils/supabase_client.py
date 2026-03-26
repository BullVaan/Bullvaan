from supabase import create_client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

url = os.getenv("SUPABASE_URL")
# Use service role key (bypasses RLS) for backend server operations.
# Falls back to anon key if service key not set.
key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)
