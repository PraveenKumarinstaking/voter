import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    """Flask application configuration class."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-1234567890")
    
    # Default connection string checks env variable first, falls back to local MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/online_voting_system")
    
    # Supabase connection details
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    # Session lifetime (e.g. 30 minutes)
    PERMANENT_SESSION_LIFETIME = 1800
