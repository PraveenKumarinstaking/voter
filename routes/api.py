from flask import Blueprint, request, jsonify
from datetime import datetime
from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash
from database.mongodb import get_db, safe_object_id

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/register', methods=['POST'])
def api_register_voter():
    """
    POST API to register a new voter.
    Expects JSON body: { "name": "...", "email": "...", "voter_id": "...", "password": "..." }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing JSON request body.'}), 400
        
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    voter_id = data.get('voter_id', '').strip()
    password = data.get('password', '')
    
    if not (name and email and voter_id and password):
        return jsonify({'error': 'Missing required fields (name, email, voter_id, password).'}), 400
        
    db = get_db()
    
    # Check if voter already registered
    if db.voters.find_one({'$or': [{'email': email}, {'voter_id': voter_id}]}):
        return jsonify({'error': 'Voter profile with this email or ID is already registered.'}), 409
        
    # Create voter document
    hashed_pw = generate_password_hash(password)
    new_voter = {
        'name': name,
        'email': email,
        'voter_id': voter_id,
        'password': hashed_pw,
        'is_approved': True,
        'created_at': datetime.now()
    }
    
    try:
        result = db.voters.insert_one(new_voter)
        return jsonify({
            'success': True,
            'message': 'Voter profile successfully registered and saved to database.',
            'voter_id': str(result.inserted_id)
        }), 201
    except Exception as e:
        return jsonify({'error': f'Database write failed: {str(e)}'}), 500

@api_bp.route('/elections', methods=['GET'])
def api_get_elections():
    """
    GET API to retrieve all elections and their candidates.
    Returns JSON list of elections.
    """
    db = get_db()
    elections = list(db.elections.find())
    candidates = list(db.candidates.find())
    
    # Group candidates by election_id
    candidates_by_election = {}
    for c in candidates:
        el_id = str(c['election_id'])
        if el_id not in candidates_by_election:
            candidates_by_election[el_id] = []
        candidates_by_election[el_id].append({
            'candidate_id': str(c['_id']),
            'name': c['name'],
            'party': c['party'],
            'bio': c['bio']
        })
        
    response = []
    for e in elections:
        el_id_str = str(e['_id'])
        response.append({
            'election_id': el_id_str,
            'title': e['title'],
            'description': e['description'],
            'status': e['status'],
            'created_at': str(e['created_at']),
            'candidates': candidates_by_election.get(el_id_str, [])
        })
        
    return jsonify({'elections': response}), 200

@api_bp.route('/vote', methods=['POST'])
def api_cast_vote():
    """
    POST API to submit/store a vote in the database.
    Expects JSON body: { "voter_id_str": "...", "election_id": "...", "candidate_id": "..." }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing JSON request body.'}), 400
        
    voter_id_str = data.get('voter_id_str')
    election_id_str = data.get('election_id')
    candidate_id_str = data.get('candidate_id')
    
    if not (voter_id_str and election_id_str and candidate_id_str):
        return jsonify({'error': 'Missing required fields (voter_id_str, election_id, candidate_id).'}), 400
        
    voter_id = safe_object_id(voter_id_str)
    election_id = safe_object_id(election_id_str)
    candidate_id = safe_object_id(candidate_id_str)
        
    db = get_db()
    
    # 1. Verify election exists and is active
    election = db.elections.find_one({'_id': election_id})
    if not election:
        return jsonify({'error': 'Election event not found.'}), 404
    if election['status'] != 'active':
        return jsonify({'error': f'Election is not open for voting. Current status: {election["status"]}.'}), 403
        
    # 2. Verify candidate exists and belongs to the election
    candidate = db.candidates.find_one({'_id': candidate_id, 'election_id': election_id})
    if not candidate:
        return jsonify({'error': 'Candidate not found in this election.'}), 404
        
    # 3. Securely cast vote (relying on database compound unique index constraint)
    try:
        vote_record = {
            'voter_id': voter_id,
            'election_id': election_id,
            'candidate_id': candidate_id,
            'timestamp': datetime.now()
        }
        db.votes.insert_one(vote_record)
        return jsonify({
            'success': True,
            'message': 'Vote cast successfully and stored in the database.',
            'receipt': {
                'election': election['title'],
                'candidate': candidate['name'],
                'party': candidate['party'],
                'timestamp': vote_record['timestamp'].isoformat() if isinstance(vote_record['timestamp'], datetime) else str(vote_record['timestamp'])
            }
        }), 201
    except DuplicateKeyError:
        return jsonify({'error': 'Invalid vote operation: You have already cast a ballot in this election.'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to store vote: {str(e)}'}), 500
