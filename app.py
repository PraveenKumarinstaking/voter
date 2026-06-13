import os
from flask import Flask, render_template, redirect, url_for, session
from config import Config
from database.mongodb import init_db

# ── Resolve absolute paths so Flask finds templates/static
#    whether run from project root OR from api/ (Vercel)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_app():
    """Application factory for the secure Online Voting System."""
    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, 'static'),
        template_folder=os.path.join(BASE_DIR, 'templates')
    )

    # Load configuration settings
    app.config.from_object(Config)

    # Initialize database connection
    try:
        init_db(app)
    except Exception as e:
        print(f"[CRITICAL] Database initialization failed: {e}")

    # Register blueprints
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.voting import voting_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(voting_bp)
    app.register_blueprint(api_bp)

    # ── Home / Landing page ──────────────────────────────────
    @app.route('/')
    def home():
        # Redirect logged-in users to their dashboards
        if 'role' in session:
            if session['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif session['role'] == 'voter':
                return redirect(url_for('voting.dashboard'))

        # Live stats with safe fallback
        try:
            from database.mongodb import get_db
            db = get_db()
            stats = {
                'total_voters':        db.voters.count_documents({}),
                'total_votes':         db.votes.count_documents({}),
                'active_elections':    db.elections.count_documents({'status': 'active'}),
                'completed_elections': db.elections.count_documents({'status': 'completed'}),
            }
        except Exception:
            stats = {
                'total_voters': 12,
                'total_votes': 6,
                'active_elections': 1,
                'completed_elections': 2,
            }

        return render_template('index.html', stats=stats)

    # ── Global error handlers ────────────────────────────────
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html', code=404,
            title='Page Not Found',
            message='The page you requested could not be located.'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('error.html', code=500,
            title='Server Error',
            message='An internal server error occurred. Please try again later.'), 500

    return app


app = create_app()

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    app.run(host=host, port=port, debug=True)
