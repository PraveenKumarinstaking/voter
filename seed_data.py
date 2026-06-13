import os
from datetime import datetime
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Load env variables
load_dotenv()

def seed_sample_data():
    from flask import Flask
    from config import Config
    from database.mongodb import init_db
    
    print("==================================================")
    print("           ONLINE VOTING SYSTEM - SEEDER          ")
    print("==================================================")
    
    # Initialize a temporary Flask context to load correct DB client settings
    app = Flask(__name__)
    app.config.from_object(Config)
    
    try:
        db = init_db(app)
    except Exception as e:
        print(f"[FAIL] Could not initialize database client: {e}")
        return
        
    # 1. Seed Voters
    try:
        voters_count = db.voters.count_documents({})
        if voters_count == 0:
            sample_voters = [
                {
                    "name": "Sarah Connor",
                    "email": "sarah@example.com",
                    "voter_id": "VOTE-111111",
                    "password": generate_password_hash("VoterPassword123"),
                    "is_approved": True,
                    "created_at": datetime.now()
                },
                {
                    "name": "John Connor",
                    "email": "john@example.com",
                    "voter_id": "VOTE-222222",
                    "password": generate_password_hash("VoterPassword123"),
                    "is_approved": True,
                    "created_at": datetime.now()
                }
            ]
            db.voters.insert_many(sample_voters)
            print("[OK] Seeded 2 sample voters successfully:")
            print("  - Email: sarah@example.com, Password: VoterPassword123, ID: VOTE-111111")
            print("  - Email: john@example.com, Password: VoterPassword123, ID: VOTE-222222")
        else:
            print(f"[INFO] Voters collection already has {voters_count} items. Skipping.")
    except Exception as e:
        print(f"[FAIL] Error seeding voters: {e}")
        return

    # 2. Seed Elections & Candidates
    try:
        elections_count = db.elections.count_documents({})
        if elections_count == 0:
            election1 = {
                "title": "2026 Student Council Election",
                "description": "Vote for the upcoming Student Council President to lead academic initiatives and student representation.",
                "status": "active",
                "created_at": datetime.now()
            }
            election2 = {
                "title": "Municipal Board Elections",
                "description": "Select representatives for the Municipal Development Council.",
                "status": "upcoming",
                "created_at": datetime.now()
            }
            
            # Insert and get insertion ids
            el1_res = db.elections.insert_one(election1)
            el2_res = db.elections.insert_one(election2)
            election1_id = el1_res.inserted_id
            
            print("[OK] Seeded 2 sample elections: '2026 Student Council Election' (Active) and 'Municipal Board Elections' (Upcoming)")
            
            # Seed Candidates tied to election 1
            sample_candidates = [
                {
                    "name": "Alice Smith",
                    "party": "Innovation Alliance",
                    "bio": "Alice is a senior majoring in Computer Science. She aims to improve digital campus tools and extend library hours.",
                    "election_id": election1_id
                },
                {
                    "name": "Bob Jones",
                    "party": "Student Voice Party",
                    "bio": "Bob is a junior majoring in Political Science. He is focused on campus sustainability, reducing food waste, and transit aid.",
                    "election_id": election1_id
                }
            ]
            db.candidates.insert_many(sample_candidates)
            print("[OK] Seeded 2 candidates for the Active election ('Alice Smith' and 'Bob Jones').")
        else:
            print(f"[INFO] Elections collection already has {elections_count} items. Skipping.")
    except Exception as e:
        print(f"[FAIL] Error seeding elections/candidates: {e}")
        return
        
    print("\nDatabase seeding completed successfully.")

if __name__ == '__main__':
    seed_sample_data()
