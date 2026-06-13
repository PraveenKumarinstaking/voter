from flask import Blueprint, request, redirect, url_for, session, flash, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from database.mongodb import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Voter registration route."""
    if 'role' in session:
        return redirect(url_for('admin.dashboard' if session['role'] == 'admin' else 'voting.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        voter_id = request.form.get('voter_id', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Basic validation
        if not (name and email and voter_id and password and confirm_password):
            flash('All fields are required!', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('register.html')

        db = get_db()
        # Check if email already exists
        if db.voters.find_one({'email': email}):
            flash('Email is already registered!', 'danger')
            return render_template('register.html')

        # Check if voter ID already exists
        if db.voters.find_one({'voter_id': voter_id}):
            flash('Voter ID is already registered!', 'danger')
            return render_template('register.html')

        # Save voter
        hashed_pw = generate_password_hash(password)
        try:
            db.voters.insert_one({
                'name': name,
                'email': email,
                'voter_id': voter_id,
                'password': hashed_pw,
                'is_approved': True  # Auto-approved for simplicity, can be updated by admin
            })
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash('An error occurred during registration. Please try again.', 'danger')
            print(f"[AUTH ERROR] Register failed: {e}")

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Unified login route with tab logic for Voter / Admin."""
    if 'role' in session:
        return redirect(url_for('admin.dashboard' if session['role'] == 'admin' else 'voting.dashboard'))

    if request.method == 'POST':
        login_type = request.form.get('login_type')  # 'voter' or 'admin'
        username_or_email = request.form.get('username_or_email', '').strip()
        password = request.form.get('password', '')

        if not (username_or_email and password):
            flash('Please enter all credentials.', 'danger')
            return render_template('login.html')

        db = get_db()

        if login_type == 'admin':
            # Query admins collection
            admin = db.admins.find_one({'username': username_or_email})
            if admin and check_password_hash(admin['password'], password):
                session.clear()
                session['user_id'] = str(admin['_id'])
                session['username'] = admin['username']
                session['role'] = 'admin'
                flash('Welcome Admin! You have logged in successfully.', 'success')
                return redirect(url_for('admin.dashboard'))
            else:
                flash('Invalid Administrator username or password.', 'danger')

        else: # 'voter'
            # Query voters collection by email or voter ID
            voter = db.voters.find_one({
                '$or': [
                    {'email': username_or_email},
                    {'voter_id': username_or_email}
                ]
            })
            if voter and check_password_hash(voter['password'], password):
                if not voter.get('is_approved', True):
                    flash('Your voter account has been suspended or is not approved yet.', 'warning')
                    return render_template('login.html')
                
                session.clear()
                session['user_id'] = str(voter['_id'])
                session['voter_id'] = voter['voter_id']
                session['name'] = voter['name']
                session['role'] = 'voter'
                flash('Logged in successfully!', 'success')
                return redirect(url_for('voting.dashboard'))
            else:
                flash('Invalid Voter email/ID or password.', 'danger')

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Logs the user out by clearing the session."""
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))
