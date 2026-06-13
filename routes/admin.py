from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from bson.objectid import ObjectId
from datetime import datetime
from database.mongodb import get_db, safe_object_id

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to ensure only logged-in administrators can access routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Access denied. Administrator login required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Main dashboard displaying key statistics and managing election modules."""
    db = get_db()

    # Calculate counts safely
    try:
        stats = {
            'total_voters':     db.voters.count_documents({}),
            'total_candidates': db.candidates.count_documents({}),
            'total_elections':  db.elections.count_documents({}),
            'total_votes':      db.votes.count_documents({}),
        }
    except Exception:
        stats = {'total_voters': 0, 'total_candidates': 0, 'total_elections': 0, 'total_votes': 0}

    # Fetch data
    try:
        elections  = list(db.elections.find().sort('created_at', -1))
    except Exception:
        elections = []
    try:
        candidates = list(db.candidates.find())
    except Exception:
        candidates = []
    try:
        voters     = list(db.voters.find().sort('created_at', -1))
    except Exception:
        voters = []

    # ── Normalise created_at to a plain string in Python (safe for any DB backend) ──
    def _fmt_date(val, fmt='%Y-%m-%d %H:%M'):
        """Return a formatted date string regardless of whether val is datetime or str."""
        if val is None:
            return 'N/A'
        if isinstance(val, datetime):
            return val.strftime(fmt)
        s = str(val)
        return s[:16] if len(s) >= 16 else s  # ISO string slice "2026-06-13T11:14"

    # Enrich elections
    election_map = {str(e['_id']): e['title'] for e in elections}
    for e in elections:
        e['id_str']     = str(e['_id'])
        e['created_at_str'] = _fmt_date(e.get('created_at'))

    # Enrich candidates
    for c in candidates:
        c['id_str']       = str(c['_id'])
        c['election_name'] = election_map.get(str(c.get('election_id', '')), 'Unknown Election')

    # Enrich voters
    for v in voters:
        v['id_str']         = str(v['_id'])
        v['created_at_str'] = _fmt_date(v.get('created_at'), '%Y-%m-%d')

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        elections=elections,
        candidates=candidates,
        voters=voters,
    )


@admin_bp.route('/election/create', methods=['POST'])
@admin_required
def create_election():
    """Create a new election."""
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    
    if not title:
        flash('Election Title is required!', 'danger')
        return redirect(url_for('admin.dashboard'))
        
    db = get_db()
    db.elections.insert_one({
        'title': title,
        'description': description,
        'status': 'upcoming',  # 'upcoming', 'active', 'completed'
        'created_at': datetime.now()
    })
    flash('New Election created successfully!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/election/<election_id>/status/<status>')
@admin_required
def change_election_status(election_id, status):
    """Change election status (Start or End election)."""
    if status not in ['upcoming', 'active', 'completed']:
        flash('Invalid status action.', 'danger')
        return redirect(url_for('admin.dashboard'))
        
    db = get_db()
    
    # Update the election status
    db.elections.update_one(
        {'_id': safe_object_id(election_id)},
        {'$set': {'status': status}}
    )
    
    flash(f"Election status changed to '{status.capitalize()}'!", 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/candidate/add', methods=['POST'])
@admin_required
def add_candidate():
    """Add a new candidate tied to an election."""
    name = request.form.get('name', '').strip()
    party = request.form.get('party', '').strip()
    bio = request.form.get('bio', '').strip()
    election_id = request.form.get('election_id')
    
    if not (name and party and election_id):
        flash('Candidate Name, Party, and Election selection are required!', 'danger')
        return redirect(url_for('admin.dashboard'))
        
    db = get_db()
    db.candidates.insert_one({
        'name': name,
        'party': party,
        'bio': bio,
        'election_id': safe_object_id(election_id)
    })
    flash('Candidate added successfully!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/candidate/edit/<candidate_id>', methods=['POST'])
@admin_required
def edit_candidate(candidate_id):
    """Edit existing candidate details."""
    name = request.form.get('name', '').strip()
    party = request.form.get('party', '').strip()
    bio = request.form.get('bio', '').strip()
    
    if not (name and party):
        flash('Candidate Name and Party are required!', 'danger')
        return redirect(url_for('admin.dashboard'))
        
    db = get_db()
    db.candidates.update_one(
        {'_id': safe_object_id(candidate_id)},
        {'$set': {
            'name': name,
            'party': party,
            'bio': bio
        }}
    )
    flash('Candidate details updated successfully!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/candidate/delete/<candidate_id>')
@admin_required
def delete_candidate(candidate_id):
    """Delete a candidate from database."""
    db = get_db()
    db.candidates.delete_one({'_id': safe_object_id(candidate_id)})
    flash('Candidate removed successfully.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/election/<election_id>/results')
@admin_required
def view_results(election_id):
    """View vote aggregation and charts for an election."""
    db = get_db()
    
    election = db.elections.find_one({'_id': safe_object_id(election_id)})
    if not election:
        flash('Election not found!', 'danger')
        return redirect(url_for('admin.dashboard'))
        
    # Get all candidates for this election
    candidates = list(db.candidates.find({'election_id': safe_object_id(election_id)}))
    
    # Calculate votes cast for each candidate
    total_votes_cast = db.votes.count_documents({'election_id': safe_object_id(election_id)})
    
    results = []
    for c in candidates:
        c_votes = db.votes.count_documents({'candidate_id': c['_id']})
        percentage = round((c_votes / total_votes_cast) * 100, 2) if total_votes_cast > 0 else 0
        results.append({
            'candidate_name': c['name'],
            'party': c['party'],
            'votes': c_votes,
            'percentage': percentage
        })
        
    # Sort results by descending votes
    results = sorted(results, key=lambda x: x['votes'], reverse=True)
    
    # Check if request is AJAX (json response) for JS graphs or dynamic reloading
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'election_title': election['title'],
            'results': results,
            'total_votes': total_votes_cast
        })
    return render_template('results.html', election=election, results=results, total_votes=total_votes_cast)

@admin_bp.route('/election/<election_id>/publish/<int:action>')
@admin_required
def toggle_results_publication(election_id, action):
    """Publish or hide the results of an election for voters."""
    db = get_db()
    is_published = (action == 1)
    
    db.elections.update_one(
        {'_id': safe_object_id(election_id)},
        {'$set': {'is_results_published': is_published}}
    )
    
    msg = "Election results published successfully! Voters can now view results." if is_published else "Election results retracted. Results are hidden from voters."
    flash(msg, 'success')
    return redirect(url_for('admin.dashboard'))
