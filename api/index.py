import sys
import os

# Ensure the project root (parent of /api) is on the Python path
# so imports like 'from app import app' and 'from database.mongodb import ...' work
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Import the Flask app — Vercel will call this as a WSGI handler
from app import app
