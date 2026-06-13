import sys
import os

# Add parent directory to path so Flask app modules can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel expects a callable named 'app' or 'handler'
# This file is the serverless function entry point
