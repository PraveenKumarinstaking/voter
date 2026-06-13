import os
from flask import Flask, render_template, redirect, url_for, session
from config import Config
from database.mongodb import init_db
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.voting import voting_bp
from routes.api import api_bp

def create_app():
    """Application factory for the secure Online Voting System."""
    app = Flask(__name__)
    
    # Load configuration settings
    app.config.from_object(Config)
    
    # Initialize database connection
    try:
        init_db(app)
    except Exception as e:
        print(f"[CRITICAL] Database initialization failed: {e}")
        print("Please verify that MongoDB is running and that your connection URI is correct.")
    
    # Register blueprints for modular routing
    # Authentication (Admin/Voter Login & Registration)
    app.register_blueprint(auth_bp)
    
    # Admin Panel (Candidate CRUD, Election States, Results)
    app.register_blueprint(admin_bp)
    
    # Voter Panel (Ballot, Vote Casting)
    app.register_blueprint(voting_bp)
    
    # REST API endpoints (Voter Registration, Get Elections, Cast Vote)
    app.register_blueprint(api_bp)
    
    # Base route: Home page / Landing page
    @app.route('/')
    def home():
        # Redirect logged-in users directly to their dashboards
        if 'role' in session:
            if session['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif session['role'] == 'voter':
                return redirect(url_for('voting.dashboard'))
                
        # Fetch live stats for landing page with fallback values
        try:
            from database.mongodb import get_db
            db = get_db()
            stats = {
                'total_voters': db.voters.count_documents({}),
                'total_votes': db.votes.count_documents({}),
                'active_elections': db.elections.count_documents({'status': 'active'}),
                'completed_elections': db.elections.count_documents({'status': 'completed'})
            }
        except Exception:
            stats = {
                'total_voters': 12,
                'total_votes': 6,
                'active_elections': 1,
                'completed_elections': 2
            }
            
        return render_template('index.html', stats=stats)
        
    # Global Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', content="<div class='text-center py-5'><i class='fa-solid fa-triangle-exclamation text-warning display-1 mb-3'></i><h2 class='text-white'>Page Not Found (404)</h2><p class='text-secondary'>The page you requested could not be located.</p><a href='/' class='btn btn-gradient-primary mt-3'>Return Home</a></div>"), 404
        
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('base.html', content="<div class='text-center py-5'><i class='fa-solid fa-triangle-exclamation text-danger display-1 mb-3'></i><h2 class='text-white'>Server Error (500)</h2><p class='text-secondary'>An internal server error occurred. Please try again later.</p><a href='/' class='btn btn-gradient-primary mt-3'>Return Home</a></div>"), 500

    return app

app = create_app()

if __name__ == '__main__':
    # Get host and port from environment or default
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    app.run(host=host, port=port, debug=True)
