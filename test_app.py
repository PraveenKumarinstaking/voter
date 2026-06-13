import os
import sys

def run_tests():
    print("==================================================")
    print("         ONLINE VOTING SYSTEM - VERIFIER          ")
    print("==================================================")
    
    # Test 1: Check imports
    print("[1/3] Testing dependency imports...")
    try:
        from flask import Flask
        from pymongo import MongoClient
        from werkzeug.security import generate_password_hash, check_password_hash
        import dotenv
        print("  [OK] flask, pymongo, werkzeug, python-dotenv imported successfully.")
    except ImportError as e:
        print(f"  [FAIL] Import failed: {e}")
        sys.exit(1)
        
    # Test 2: Check password hashing compatibility
    print("[2/3] Checking password hashing algorithms...")
    raw_pass = "TestSecurePassword123"
    hashed_pass = generate_password_hash(raw_pass)
    if check_password_hash(hashed_pass, raw_pass):
        print("  [OK] Password hashing and verification functions are fully operational.")
    else:
        print("  [FAIL] Password verification mismatch!")
        sys.exit(1)
        
    # Test 3: Check MongoDB Connection
    print("[3/3] Checking MongoDB connection status...")
    # Load .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/online_voting_system")
    print(f"  Attempting client connection to: {mongo_uri}")
    
    try:
        from pymongo import MongoClient
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        # Try pinging the client to trigger a connection request
        client.admin.command('ping')
        
        parts = mongo_uri.split('/')
        db_name = None
        if len(parts) > 3:
            db_name = parts[-1].split('?')[0]
        if not db_name:
            db_name = "online_voting_system"
            
        db = client[db_name]
        print(f"  [OK] Connected to database: '{db_name}' successfully.")
        
    except Exception as e:
        print("  [WARN] Warning: Could not connect to MongoDB.")
        print(f"    Error details: {e}")
        print("    Please ensure your MongoDB local service is running or your environment connection string is correct.")
        print("    (You can still run the webserver, but database calls will fail until MongoDB is active.)")

    print("\nVerification checks completed.")

if __name__ == '__main__':
    run_tests()
