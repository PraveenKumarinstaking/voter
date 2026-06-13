from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from bson.objectid import ObjectId
from datetime import datetime
from pymongo.errors import DuplicateKeyError
from database.mongodb import get_db, safe_object_id

voting_bp = Blueprint('voting', __name__)

def voter_required(f):
    """Decorator to ensure only logged-in voters can access voter portal routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'voter':
            flash('Access denied. Voter login required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@voting_bp.route('/dashboard')
@voter_required
def dashboard():
    """Lists elections and tracks voter eligibility/status."""
    db = get_db()
    voter_id = safe_object_id(session['user_id'])
    
    # Get all elections
    all_elections = list(db.elections.find().sort('created_at', -1))
    
    # For each election, check if voter has already voted
    for election in all_elections:
        election['id_str'] = str(election['_id'])
        has_voted = db.votes.find_one({
            'voter_id': voter_id,
            'election_id': election['_id']
        })
        election['has_voted'] = (has_voted is not None)

    return render_template('voting.html', elections=all_elections)

@voting_bp.route('/election/<election_id>/ballot')
@voter_required
def ballot(election_id):
    """Displays the list of candidates for an active election to cast a vote."""
    db = get_db()
    voter_id = safe_object_id(session['user_id'])
    
    election = db.elections.find_one({'_id': safe_object_id(election_id)})
    if not election:
        flash('Election not found.', 'danger')
        return redirect(url_for('voting.dashboard'))
        
    if election['status'] != 'active':
        flash('This election is not currently active for voting.', 'warning')
        return redirect(url_for('voting.dashboard'))
        
    # Check if voter has already voted in this election
    already_voted = db.votes.find_one({
        'voter_id': voter_id,
        'election_id': safe_object_id(election_id)
    })
    
    if already_voted:
        flash('You have already cast your vote in this election!', 'info')
        return redirect(url_for('voting.dashboard'))
        
    # Get candidates for this election
    candidates = list(db.candidates.find({'election_id': safe_object_id(election_id)}))
    
    for c in candidates:
        c['id_str'] = str(c['_id'])
        
    return render_template('voting_ballot.html', election=election, candidates=candidates)

@voting_bp.route('/election/<election_id>/cast', methods=['POST'])
@voter_required
def cast_vote(election_id):
    """Processes the submission of a vote, enforcing security and uniqueness constraints."""
    db = get_db()
    voter_id = safe_object_id(session['user_id'])
    candidate_id = request.form.get('candidate_id')
    
    if not candidate_id:
        flash('Please select a candidate to vote.', 'danger')
        return redirect(url_for('voting.ballot', election_id=election_id))
        
    # 1. Verify election status
    election = db.elections.find_one({'_id': safe_object_id(election_id)})
    if not election or election['status'] != 'active':
        flash('Voting failed: The election is not currently active.', 'danger')
        return redirect(url_for('voting.dashboard'))
        
    # 2. Verify candidate belongs to the election
    candidate = db.candidates.find_one({
        '_id': safe_object_id(candidate_id),
        'election_id': safe_object_id(election_id)
    })
    if not candidate:
        flash('Voting failed: Invalid candidate selection.', 'danger')
        return redirect(url_for('voting.ballot', election_id=election_id))
        
    # 3. Securely cast vote (utilizing compound unique index for absolute enforcement)
    try:
        vote_record = {
            'voter_id': voter_id,
            'election_id': safe_object_id(election_id),
            'candidate_id': safe_object_id(candidate_id),
            'timestamp': datetime.now()
        }
        db.votes.insert_one(vote_record)
        
        flash(f"Your vote for {candidate['name']} has been cast successfully!", 'success')
        return render_template('vote_confirmation.html', election=election, candidate=candidate)
        
    except DuplicateKeyError:
        flash('Voting failed: You have already voted in this election!', 'danger')
        return redirect(url_for('voting.dashboard'))
    except Exception as e:
        flash('An error occurred while casting your vote. Please try again.', 'danger')
        print(f"[VOTE ERROR] Exception during vote insert: {e}")
        return redirect(url_for('voting.dashboard'))

@voting_bp.route('/election/<election_id>/results')
@voter_required
def view_election_results(election_id):
    """Allow voters to view results of a completed election if published by admin."""
    db = get_db()
    
    election = db.elections.find_one({'_id': safe_object_id(election_id)})
    if not election:
        flash('Election not found.', 'danger')
        return redirect(url_for('voting.dashboard'))
        
    # Security checks: must be completed and results must be published
    if election.get('status') != 'completed':
        flash('Election is still ongoing or upcoming. Results are not available.', 'warning')
        return redirect(url_for('voting.dashboard'))
        
    if not election.get('is_results_published'):
        flash('Results for this election have not been published yet.', 'warning')
        return redirect(url_for('voting.dashboard'))
        
    # Get candidates and calculate votes
    candidates = list(db.candidates.find({'election_id': safe_object_id(election_id)}))
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
        
    results = sorted(results, key=lambda x: x['votes'], reverse=True)
    
    return render_template('results.html', election=election, results=results, total_votes=total_votes_cast)
