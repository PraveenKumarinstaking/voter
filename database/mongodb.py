import os
import json
from datetime import datetime
# pyrefly: ignore [missing-import]
from bson.objectid import ObjectId
# pyrefly: ignore [missing-import]
from pymongo import MongoClient
# pyrefly: ignore [missing-import]
from werkzeug.security import generate_password_hash

# Global database client and database references
client = None
db = None

class MockCursor:
    """Mock database cursor class supporting sorting and list conversions."""
    def __init__(self, data):
        self.data = data
        
    def sort(self, key, direction=-1):
        try:
            # Sort with datetime handling or string fallback
            self.data = sorted(
                self.data, 
                key=lambda x: x.get(key, datetime.min.isoformat() if key == 'created_at' else ""), 
                reverse=(direction == -1)
            )
        except Exception:
            self.data = sorted(self.data, key=lambda x: str(x.get(key, "")), reverse=(direction == -1))
        return self
        
    def __iter__(self):
        return iter(self.data)
        
    def __getitem__(self, index):
        return self.data[index]
        
    def __len__(self):
        return len(self.data)

class MockCollection:
    """Mock PyMongo collection class replicating query methods with a local JSON file."""
    def __init__(self, name, file_path):
        self.name = name
        self.file_path = file_path
        
    def _load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    full_data = json.load(f)
                    return full_data.get(self.name, [])
            except Exception:
                return []
        return []
        
    def _save_data(self, data):
        full_data = {}
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    full_data = json.load(f)
            except Exception:
                pass
        
        # Serialize ObjectId and datetime to string format for JSON
        def serialize(obj):
            if isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize(x) for x in obj]
            elif isinstance(obj, (datetime, ObjectId)):
                return str(obj)
            return obj
            
        full_data[self.name] = serialize(data)
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=4)
        except Exception as e:
            print(f"[MOCK DB ERROR] Saving data: {e}")

    def find_one(self, filter_dict):
        docs = self._load_data()
        for doc in docs:
            match = True
            for k, v in filter_dict.items():
                if k == '$or':
                    or_match = False
                    for subfilter in v:
                        sub_match = True
                        for sk, sv in subfilter.items():
                            if str(doc.get(sk)) != str(sv):
                                sub_match = False
                        if sub_match:
                            or_match = True
                            break
                    if not or_match:
                        match = False
                    continue
                if str(doc.get(k)) != str(v):
                    match = False
            if match:
                return dict(doc)
        return None

    def find(self, filter_dict=None):
        docs = self._load_data()
        if not filter_dict:
            return MockCursor([dict(d) for d in docs])
        results = []
        for doc in docs:
            match = True
            for k, v in filter_dict.items():
                if str(doc.get(k)) != str(v):
                    match = False
            if match:
                results.append(dict(doc))
        return MockCursor(results)

    def insert_one(self, doc):
        docs = self._load_data()
        if '_id' not in doc:
            doc['_id'] = str(ObjectId())
            
        # Duplicate checks simulating database indexes
        if self.name == 'admins' and any(d.get('username') == doc.get('username') for d in docs):
            # pyrefly: ignore [missing-import]
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError(f"Duplicate username: {doc.get('username')}")
        if self.name == 'voters':
            if any(d.get('email') == doc.get('email') for d in docs):
                # pyrefly: ignore [missing-import]
                from pymongo.errors import DuplicateKeyError
                raise DuplicateKeyError("Duplicate email.")
            if any(d.get('voter_id') == doc.get('voter_id') for d in docs):
                # pyrefly: ignore [missing-import]
                from pymongo.errors import DuplicateKeyError
                raise DuplicateKeyError("Duplicate voter ID.")
        if self.name == 'votes':
            if any(str(d.get('voter_id')) == str(doc.get('voter_id')) and str(d.get('election_id')) == str(doc.get('election_id')) for d in docs):
                # pyrefly: ignore [missing-import]
                from pymongo.errors import DuplicateKeyError
                raise DuplicateKeyError("Duplicate vote cast detected.")
                
        # Format structures for JSON file writing
        for k, v in list(doc.items()):
            if isinstance(v, datetime):
                doc[k] = v.isoformat()
            elif isinstance(v, ObjectId):
                doc[k] = str(v)
                
        docs.append(doc)
        self._save_data(docs)
        return type('InsertOneResult', (object,), {'inserted_id': doc['_id']})()

    def insert_many(self, docs_list):
        docs = self._load_data()
        for doc in docs_list:
            if '_id' not in doc:
                doc['_id'] = str(ObjectId())
            for k, v in list(doc.items()):
                if isinstance(v, datetime):
                    doc[k] = v.isoformat()
                elif isinstance(v, ObjectId):
                    doc[k] = str(v)
            docs.append(doc)
        self._save_data(docs)

    def update_one(self, filter_dict, update_dict):
        docs = self._load_data()
        doc = self.find_one(filter_dict)
        if doc:
            index = next(i for i, d in enumerate(docs) if str(d.get('_id')) == str(doc.get('_id')))
            if '$set' in update_dict:
                for k, v in update_dict['$set'].items():
                    if isinstance(v, (datetime, ObjectId)):
                        v = str(v)
                    docs[index][k] = v
            self._save_data(docs)
            
    def delete_one(self, filter_dict):
        docs = self._load_data()
        doc = self.find_one(filter_dict)
        if doc:
            docs = [d for d in docs if str(d.get('_id')) != str(doc.get('_id'))]
            self._save_data(docs)
            
    def count_documents(self, filter_dict):
        return len(self.find(filter_dict))

class MockDatabase:
    """Mock PyMongo Database class mappings."""
    def __init__(self, file_path):
        self.file_path = file_path
        self.admins = MockCollection('admins', file_path)
        self.voters = MockCollection('voters', file_path)
        self.elections = MockCollection('elections', file_path)
        self.candidates = MockCollection('candidates', file_path)
        self.votes = MockCollection('votes', file_path)

import requests

class SupabaseCursor:
    """Cursor wrapper for Supabase query results mimicking PyMongo."""
    def __init__(self, data):
        self.data = data
        
    def sort(self, key, direction=-1):
        try:
            self.data = sorted(
                self.data, 
                key=lambda x: x.get(key, ""), 
                reverse=(direction == -1)
            )
        except Exception:
            self.data = sorted(self.data, key=lambda x: str(x.get(key, "")), reverse=(direction == -1))
        return self
        
    def __iter__(self):
        return iter(self.data)
        
    def __getitem__(self, index):
        return self.data[index]
        
    def __len__(self):
        return len(self.data)

class SupabaseCollection:
    """Supabase PostgREST table wrapper mimicking PyMongo Collection."""
    def __init__(self, name, url, key):
        self.name = name
        self.url = url
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
    def _serialize(self, obj):
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize(x) for x in obj]
        elif isinstance(obj, (datetime, ObjectId)):
            return str(obj)
        return obj

    def _deserialize_doc(self, doc):
        if not doc:
            return doc
        if isinstance(doc, list):
            return [self._deserialize_doc(x) for x in doc]
        if isinstance(doc, dict):
            new_doc = {}
            for k, v in doc.items():
                if k in ['created_at', 'start_date', 'end_date', 'timestamp'] and isinstance(v, str):
                    try:
                        val_str = v.replace('Z', '+00:00')
                        new_doc[k] = datetime.fromisoformat(val_str)
                    except Exception:
                        new_doc[k] = v
                else:
                    new_doc[k] = self._deserialize_doc(v)
            return new_doc
        return doc

    def _build_params(self, filter_dict):
        params = {}
        if not filter_dict:
            return params
        for k, v in filter_dict.items():
            val = str(v) if isinstance(v, (ObjectId, datetime)) else v
            if k == '$or':
                or_parts = []
                for sub in v:
                    for sk, sv in sub.items():
                        sub_val = str(sv) if isinstance(sv, (ObjectId, datetime)) else sv
                        or_parts.append(f"{sk}.eq.{sub_val}")
                params["or"] = f"({','.join(or_parts)})"
            else:
                params[k] = f"eq.{val}"
        return params

    def find_one(self, filter_dict):
        params = self._build_params(filter_dict)
        params["limit"] = 1
        res = requests.get(f"{self.url}/rest/v1/{self.name}", headers=self.headers, params=params)
        if res.status_code >= 400:
            print(f"[SUPABASE ERROR] {res.status_code}: {res.text}")
            if res.status_code == 404:
                raise RuntimeError(f"Table '{self.name}' not found on Supabase. Please execute setup_supabase.sql script in the Supabase SQL editor.")
            return None
        data = res.json()
        return self._deserialize_doc(data[0]) if data else None

    def find(self, filter_dict=None):
        params = self._build_params(filter_dict)
        res = requests.get(f"{self.url}/rest/v1/{self.name}", headers=self.headers, params=params)
        if res.status_code >= 400:
            print(f"[SUPABASE ERROR] {res.status_code}: {res.text}")
            if res.status_code == 404:
                raise RuntimeError(f"Table '{self.name}' not found on Supabase. Please execute setup_supabase.sql script in the Supabase SQL editor.")
            return SupabaseCursor([])
        data = res.json()
        return SupabaseCursor(self._deserialize_doc(data))

    def insert_one(self, doc):
        doc = self._serialize(doc)
        if '_id' not in doc:
            doc['_id'] = str(ObjectId())
            
        res = requests.post(f"{self.url}/rest/v1/{self.name}", headers=self.headers, json=doc)
        
        if res.status_code == 409 or (res.status_code >= 400 and "23505" in res.text):
            raise DuplicateKeyError("Duplicate key violation on Supabase.")
        elif res.status_code >= 400:
            print(f"[SUPABASE ERROR] {res.status_code}: {res.text}")
            if res.status_code == 404:
                raise RuntimeError(f"Table '{self.name}' not found on Supabase. Please execute setup_supabase.sql script in the Supabase SQL editor.")
            raise RuntimeError(f"Supabase insert failed: {res.text}")
            
        return type('InsertOneResult', (object,), {'inserted_id': doc['_id']})()

    def insert_many(self, docs_list):
        serialized_docs = []
        for doc in docs_list:
            doc = self._serialize(doc)
            if '_id' not in doc:
                doc['_id'] = str(ObjectId())
            serialized_docs.append(doc)
            
        res = requests.post(f"{self.url}/rest/v1/{self.name}", headers=self.headers, json=serialized_docs)
        if res.status_code >= 400:
            print(f"[SUPABASE ERROR] {res.status_code}: {res.text}")
            if res.status_code == 404:
                raise RuntimeError(f"Table '{self.name}' not found on Supabase. Please execute setup_supabase.sql script in the Supabase SQL editor.")
            raise RuntimeError(f"Supabase insert_many failed: {res.text}")

    def update_one(self, filter_dict, update_dict):
        params = self._build_params(filter_dict)
        if '$set' in update_dict:
            payload = self._serialize(update_dict['$set'])
            res = requests.patch(f"{self.url}/rest/v1/{self.name}", headers=self.headers, params=params, json=payload)
            if res.status_code >= 400:
                print(f"[SUPABASE ERROR] {res.status_code}: {res.text}")
                if res.status_code == 404:
                    raise RuntimeError(f"Table '{self.name}' not found on Supabase. Please execute setup_supabase.sql script in the Supabase SQL editor.")

    def delete_one(self, filter_dict):
        params = self._build_params(filter_dict)
        res = requests.delete(f"{self.url}/rest/v1/{self.name}", headers=self.headers, params=params)
        if res.status_code >= 400:
            print(f"[SUPABASE ERROR] {res.status_code}: {res.text}")
            if res.status_code == 404:
                raise RuntimeError(f"Table '{self.name}' not found on Supabase. Please execute setup_supabase.sql script in the Supabase SQL editor.")

    def count_documents(self, filter_dict):
        return len(self.find(filter_dict))

class SupabaseDatabase:
    """Supabase PostgREST Database interface mimicking PyMongo Client Database."""
    def __init__(self, url, key):
        self.url = url
        self.key = key
        self.admins = SupabaseCollection('admins', url, key)
        self.voters = SupabaseCollection('voters', url, key)
        self.elections = SupabaseCollection('elections', url, key)
        self.candidates = SupabaseCollection('candidates', url, key)
        self.votes = SupabaseCollection('votes', url, key)

def init_db(app):
    """
    Initializes database connection. Prioritizes Supabase if configured.
    Falls back to MongoDB, and then to local MockDatabase.
    """
    global client, db
    
    supabase_url = app.config.get("SUPABASE_URL")
    supabase_key = app.config.get("SUPABASE_KEY")
    
    if supabase_url and supabase_key:
        print("[DATABASE] Supabase configurations detected. Attempting Supabase connection...")
        temp_db = SupabaseDatabase(supabase_url, supabase_key)
        try:
            # Test query to verify tables are created and connected
            temp_db.admins.find_one({})
            print("[DATABASE] Connected to Supabase successfully.")
            
            # Seed default admin in Supabase if not present
            if temp_db.admins.count_documents({}) == 0:
                admin_data = {
                    "_id": str(ObjectId()),
                    "username": "admin",
                    "password": generate_password_hash("AdminPassword123")
                }
                temp_db.admins.insert_one(admin_data)
                print("[DATABASE] Seeded default administrator account successfully in Supabase.")
            db = temp_db
            return db
        except Exception as e:
            print("\n" + "="*70)
            print("[DATABASE WARNING] Could not verify Supabase connection.")
            print(f"Details: {e}")
            print("Please ensure your setup_supabase.sql has been run in the Supabase SQL editor.")
            print("Falling back to MongoDB...")
            print("="*70 + "\n")
        
    mongo_uri = app.config.get("MONGO_URI", "mongodb://localhost:27017/online_voting_system")
    
    try:
        # Try actual MongoDB connection with short timeout
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
        client.admin.command('ping')
        
        # Connection succeeded
        parts = mongo_uri.split('/')
        db_name = None
        if len(parts) > 3:
            db_name = parts[-1].split('?')[0]
        if not db_name:
            db_name = "online_voting_system"
            
        db = client[db_name]
        
        # Build indexes
        db.admins.create_index("username", unique=True)
        db.voters.create_index("email", unique=True)
        db.voters.create_index("voter_id", unique=True)
        db.votes.create_index([("voter_id", 1), ("election_id", 1)], unique=True)
        db.candidates.create_index("election_id")
        
        # Seed admin
        if db.admins.count_documents({}) == 0:
            admin_data = {
                "username": "admin",
                "password": generate_password_hash("AdminPassword123")
            }
            db.admins.insert_one(admin_data)
            print("[DATABASE] Seeded default administrator account successfully in MongoDB.")
            
        print(f"[DATABASE] Connected to live MongoDB Database '{db_name}'.")
        
    except Exception as e:
        print("\n" + "="*70)
        print("[DATABASE WARNING] Could not connect to live MongoDB service.")
        print(f"Details: {e}")
        print("Falling back to local file-based MockDatabase (online-voting-system/mock_db.json).")
        print("This ensures the application runs out-of-the-box without setup!")
        print("="*70 + "\n")
        
        # Enable local Mock database fallback
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mock_file = os.path.join(base_dir, 'mock_db.json')
        db = MockDatabase(mock_file)
        
        # Seed admin in Mock database
        if db.admins.count_documents({}) == 0:
            admin_data = {
                "username": "admin",
                "password": generate_password_hash("AdminPassword123")
            }
            db.admins.insert_one(admin_data)
            print("[DATABASE] Seeded default administrator account successfully in MockDatabase.")
            
    return db

def get_db():
    """Returns the current active database instance (MongoDB or MockDatabase)."""
    global db
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db(app) first.")
    return db

def safe_object_id(val):
    """
    Converts a value to bson.objectid.ObjectId if it is a valid 24-character hex string.
    Otherwise returns the value as-is (e.g. as a string ID used in Supabase or MockDB).
    Prevents bson.errors.InvalidId crash.
    """
    if val is None:
        return None
    if isinstance(val, ObjectId):
        return val
    val_str = str(val)
    if ObjectId.is_valid(val_str):
        return ObjectId(val_str)
    return val_str

