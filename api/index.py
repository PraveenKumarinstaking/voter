import sys
import os

# CRITICAL: Ensure the project root is on Python's module search path
# so that 'from app import app', 'from database.mongodb import ...', etc. all resolve
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set PYTHONPATH fallback explicitly
os.environ.setdefault("PYTHONPATH", project_root)

# Import the Flask application object
# Vercel's Python runtime looks for a callable named 'app' in this file
from app import app  # noqa: F401
