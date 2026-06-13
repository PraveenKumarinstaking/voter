import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_supabase_connection():
    print("==================================================")
    print("         SUPABASE INTEGRATION TESTER             ")
    print("==================================================")
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("[FAIL] Missing SUPABASE_URL or SUPABASE_KEY in .env configuration.")
        return
        
    print(f"Project URL: {url}")
    print("Testing connection to Supabase API...")
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    try:
        # Check PostgREST health / open endpoint
        res = requests.get(f"{url}/rest/v1/", headers=headers)
        if res.status_code == 200:
            print("[OK] Connected to Supabase PostgREST API successfully.")
            # Check tables
            tables = ["admins", "voters", "elections", "candidates", "votes"]
            missing_tables = []
            
            for table in tables:
                table_res = requests.get(f"{url}/rest/v1/{table}?limit=1", headers=headers)
                if table_res.status_code == 404:
                    missing_tables.append(table)
                    
            if missing_tables:
                print(f"[WARN] Connected, but the following tables are missing: {', '.join(missing_tables)}")
                print("  --> Please execute the setup_supabase.sql script inside the SQL Editor of your Supabase dashboard.")
            else:
                print("[OK] All database tables are present and verified on Supabase.")
        else:
            print(f"[FAIL] Supabase API returned status code {res.status_code}: {res.text}")
    except Exception as e:
        print(f"[FAIL] Could not connect to Supabase. Error: {e}")

if __name__ == '__main__':
    test_supabase_connection()
