import os
import json
import tempfile
import shutil
from datetime import datetime
from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash
import requests

# ─────────────────────────────────────────────────────────────
# Detect Vercel / serverless environment.
# On Vercel: filesystem is read-only except /tmp.
# ─────────────────────────────────────────────────────────────
IS_VERCEL = bool(
    os.environ.get('VERCEL') or
    os.environ.get('VERCEL_ENV') or
    os.environ.get('VERCEL_REGION')
)

# ─── Global DB handle ────────────────────────────────────────
_client = None
db = None


# ═════════════════════════════════════════════════════════════
#  Custom Errors
# ═════════════════════════════════════════════════════════════
class SupabaseTableNotFoundError(RuntimeError):
    """Raised when a Supabase table does not exist (setup_supabase.sql not run)."""
    pass


# ═════════════════════════════════════════════════════════════
#  MOCK DATABASE  (JSON file / /tmp fallback)
# ═════════════════════════════════════════════════════════════
class MockCursor:
    """Minimal PyMongo-compatible cursor backed by a list."""
    def __init__(self, data):
        self.data = list(data)

    def sort(self, key, direction=-1):
        try:
            self.data = sorted(
                self.data,
                key=lambda x: x.get(key, datetime.min.isoformat() if key == 'created_at' else ''),
                reverse=(direction == -1)
            )
        except Exception:
            self.data = sorted(self.data, key=lambda x: str(x.get(key, '')), reverse=(direction == -1))
        return self

    def __iter__(self):   return iter(self.data)
    def __getitem__(self, i): return self.data[i]
    def __len__(self):    return len(self.data)


class MockCollection:
    """PyMongo-compatible collection backed by a JSON file.
    On Vercel the live copy is kept in /tmp so writes succeed."""

    def __init__(self, name, file_path):
        self.name = name
        self.file_path = file_path  # original (possibly read-only) path

    # ── path helpers ──────────────────────────────────────────
    def _writable_path(self):
        """Return a path we can write to."""
        if IS_VERCEL:
            tmp = os.path.join(tempfile.gettempdir(), 'mock_db.json')
            if not os.path.exists(tmp) and os.path.exists(self.file_path):
                try:
                    shutil.copy2(self.file_path, tmp)
                except Exception:
                    pass
            return tmp
        return self.file_path

    # ── I/O helpers ───────────────────────────────────────────
    def _load(self):
        paths = []
        if IS_VERCEL:
            paths.append(self._writable_path())
        paths.append(self.file_path)
        for path in paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f).get(self.name, [])
                except Exception:
                    continue
        return []

    def _save(self, docs):
        write_path = self._writable_path()
        full = {}
        # Load whatever is already there
        if os.path.exists(write_path):
            try:
                with open(write_path, 'r', encoding='utf-8') as f:
                    full = json.load(f)
            except Exception:
                pass
        elif os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    full = json.load(f)
            except Exception:
                pass

        def _serial(obj):
            if isinstance(obj, dict):  return {k: _serial(v) for k, v in obj.items()}
            if isinstance(obj, list):  return [_serial(x) for x in obj]
            if isinstance(obj, (datetime, ObjectId)): return str(obj)
            return obj

        full[self.name] = _serial(docs)
        try:
            with open(write_path, 'w', encoding='utf-8') as f:
                json.dump(full, f, indent=2)
        except Exception as e:
            print(f'[MOCK DB] Write error ({write_path}): {e}')

    # ── CRUD ─────────────────────────────────────────────────
    def find_one(self, filter_dict):
        for doc in self._load():
            if self._matches(doc, filter_dict):
                return dict(doc)
        return None

    def find(self, filter_dict=None):
        docs = self._load()
        if not filter_dict:
            return MockCursor([dict(d) for d in docs])
        return MockCursor([dict(d) for d in docs if self._matches(d, filter_dict)])

    def insert_one(self, doc):
        docs = self._load()
        if '_id' not in doc:
            doc['_id'] = str(ObjectId())
        # Unique-key simulation
        if self.name == 'admins' and any(d.get('username') == doc.get('username') for d in docs):
            raise DuplicateKeyError(f"Duplicate username: {doc.get('username')}")
        if self.name == 'voters':
            if any(d.get('email') == doc.get('email') for d in docs):
                raise DuplicateKeyError('Duplicate email.')
            if any(d.get('voter_id') == doc.get('voter_id') for d in docs):
                raise DuplicateKeyError('Duplicate voter ID.')
        if self.name == 'votes':
            if any(str(d.get('voter_id')) == str(doc.get('voter_id')) and
                   str(d.get('election_id')) == str(doc.get('election_id')) for d in docs):
                raise DuplicateKeyError('Duplicate vote.')
        # Serialize
        for k, v in list(doc.items()):
            if isinstance(v, (datetime, ObjectId)):
                doc[k] = str(v)
        docs.append(doc)
        self._save(docs)
        class _Res:
            inserted_id = doc['_id']
        return _Res()

    def insert_many(self, docs_list):
        docs = self._load()
        for doc in docs_list:
            if '_id' not in doc:
                doc['_id'] = str(ObjectId())
            for k, v in list(doc.items()):
                if isinstance(v, (datetime, ObjectId)):
                    doc[k] = str(v)
            docs.append(doc)
        self._save(docs)

    def update_one(self, filter_dict, update_dict):
        docs = self._load()
        target = self.find_one(filter_dict)
        if not target:
            return
        idx = next(i for i, d in enumerate(docs) if str(d.get('_id')) == str(target.get('_id')))
        if '$set' in update_dict:
            for k, v in update_dict['$set'].items():
                docs[idx][k] = str(v) if isinstance(v, (datetime, ObjectId)) else v
        self._save(docs)

    def delete_one(self, filter_dict):
        docs = self._load()
        target = self.find_one(filter_dict)
        if target:
            docs = [d for d in docs if str(d.get('_id')) != str(target.get('_id'))]
            self._save(docs)

    def count_documents(self, filter_dict):
        return len(self.find(filter_dict))

    # ── filter helper ─────────────────────────────────────────
    @staticmethod
    def _matches(doc, filter_dict):
        if not filter_dict:
            return True
        for k, v in filter_dict.items():
            if k == '$or':
                if not any(
                    all(str(doc.get(sk)) == str(sv) for sk, sv in sub.items())
                    for sub in v
                ):
                    return False
            elif str(doc.get(k)) != str(v):
                return False
        return True


class MockDatabase:
    """Minimal PyMongo-compatible database backed by a JSON file."""
    def __init__(self, file_path):
        self.admins    = MockCollection('admins',     file_path)
        self.voters    = MockCollection('voters',     file_path)
        self.elections = MockCollection('elections',  file_path)
        self.candidates= MockCollection('candidates', file_path)
        self.votes     = MockCollection('votes',      file_path)


# ═════════════════════════════════════════════════════════════
#  SUPABASE DATABASE
# ═════════════════════════════════════════════════════════════
class SupabaseCursor:
    def __init__(self, data):
        self.data = list(data)
    def sort(self, key, direction=-1):
        try:
            self.data = sorted(self.data, key=lambda x: x.get(key, ''), reverse=(direction == -1))
        except Exception:
            self.data = sorted(self.data, key=lambda x: str(x.get(key, '')), reverse=(direction == -1))
        return self
    def __iter__(self):    return iter(self.data)
    def __getitem__(self, i): return self.data[i]
    def __len__(self):     return len(self.data)


class SupabaseCollection:
    """PyMongo-compatible collection backed by Supabase PostgREST."""

    def __init__(self, name, url, key):
        self.name = name
        self.url  = url.rstrip('/')
        self.headers = {
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation',
        }

    # ── serialisation ─────────────────────────────────────────
    def _serial(self, obj):
        if isinstance(obj, dict): return {k: self._serial(v) for k, v in obj.items()}
        if isinstance(obj, list): return [self._serial(x) for x in obj]
        if isinstance(obj, (datetime, ObjectId)): return str(obj)
        return obj

    def _deserial(self, doc):
        if not doc: return doc
        if isinstance(doc, list): return [self._deserial(x) for x in doc]
        if isinstance(doc, dict):
            out = {}
            for k, v in doc.items():
                if k in ('created_at', 'start_date', 'end_date', 'timestamp') and isinstance(v, str):
                    try:
                        out[k] = datetime.fromisoformat(v.replace('Z', '+00:00'))
                    except Exception:
                        out[k] = v
                else:
                    out[k] = self._deserial(v)
            return out
        return doc

    # ── query params ─────────────────────────────────────────
    def _params(self, filter_dict):
        p = {}
        if not filter_dict:
            return p
        for k, v in filter_dict.items():
            if k == '$or':
                parts = [f"{sk}.eq.{sv}" for sub in v for sk, sv in sub.items()]
                p['or'] = f"({','.join(parts)})"
            else:
                val = str(v) if isinstance(v, (ObjectId, datetime)) else v
                p[k] = f'eq.{val}'
        return p

    # ── error check ───────────────────────────────────────────
    def _check(self, res, op=''):
        if res.status_code >= 400:
            print(f'[SUPABASE/{self.name}] {op} {res.status_code}: {res.text[:300]}')
            if res.status_code in (400, 404) and ('PGRST' in res.text or 'not found' in res.text.lower()):
                raise SupabaseTableNotFoundError(
                    f"Table '{self.name}' not found. Run setup_supabase.sql in Supabase SQL Editor."
                )
            return False
        return True

    # ── CRUD ─────────────────────────────────────────────────
    def find_one(self, filter_dict):
        p = self._params(filter_dict)
        p['limit'] = 1
        try:
            res = requests.get(f'{self.url}/rest/v1/{self.name}', headers=self.headers, params=p, timeout=10)
        except Exception as e:
            print(f'[SUPABASE/{self.name}] find_one network error: {e}')
            return None
        if not self._check(res, 'find_one'): return None
        data = res.json()
        return self._deserial(data[0]) if data else None

    def find(self, filter_dict=None):
        p = self._params(filter_dict)
        try:
            res = requests.get(f'{self.url}/rest/v1/{self.name}', headers=self.headers, params=p, timeout=10)
        except Exception as e:
            print(f'[SUPABASE/{self.name}] find network error: {e}')
            return SupabaseCursor([])
        if not self._check(res, 'find'): return SupabaseCursor([])
        return SupabaseCursor(self._deserial(res.json()))

    def insert_one(self, doc):
        doc = self._serial(doc)
        if '_id' not in doc:
            doc['_id'] = str(ObjectId())
        try:
            res = requests.post(f'{self.url}/rest/v1/{self.name}', headers=self.headers, json=doc, timeout=10)
        except Exception as e:
            raise RuntimeError(f'Supabase network error: {e}')
        if res.status_code == 409 or (res.status_code >= 400 and '23505' in res.text):
            raise DuplicateKeyError('Duplicate key.')
        if not self._check(res, 'insert_one'):
            raise RuntimeError(f'Supabase insert failed: {res.text}')
        class _Res:
            inserted_id = doc['_id']
        return _Res()

    def insert_many(self, docs_list):
        serialized = []
        for d in docs_list:
            d = self._serial(d)
            if '_id' not in d:
                d['_id'] = str(ObjectId())
            serialized.append(d)
        try:
            res = requests.post(f'{self.url}/rest/v1/{self.name}', headers=self.headers, json=serialized, timeout=15)
        except Exception as e:
            raise RuntimeError(f'Supabase network error: {e}')
        self._check(res, 'insert_many')

    def update_one(self, filter_dict, update_dict):
        if '$set' not in update_dict:
            return
        payload = self._serial(update_dict['$set'])
        try:
            res = requests.patch(
                f'{self.url}/rest/v1/{self.name}',
                headers=self.headers, params=self._params(filter_dict),
                json=payload, timeout=10
            )
        except Exception as e:
            print(f'[SUPABASE/{self.name}] update_one network error: {e}')
            return
        self._check(res, 'update_one')

    def delete_one(self, filter_dict):
        try:
            res = requests.delete(
                f'{self.url}/rest/v1/{self.name}',
                headers=self.headers, params=self._params(filter_dict), timeout=10
            )
        except Exception as e:
            print(f'[SUPABASE/{self.name}] delete_one network error: {e}')
            return
        self._check(res, 'delete_one')

    def count_documents(self, filter_dict):
        return len(self.find(filter_dict))


class SupabaseDatabase:
    def __init__(self, url, key):
        self.admins     = SupabaseCollection('admins',      url, key)
        self.voters     = SupabaseCollection('voters',      url, key)
        self.elections  = SupabaseCollection('elections',   url, key)
        self.candidates = SupabaseCollection('candidates',  url, key)
        self.votes      = SupabaseCollection('votes',       url, key)


# ═════════════════════════════════════════════════════════════
#  INIT_DB  — priority: Supabase → MongoDB → MockDB
# ═════════════════════════════════════════════════════════════
def _seed_admin(database):
    """Insert a default admin if the admins collection is empty."""
    try:
        if database.admins.count_documents({}) == 0:
            database.admins.insert_one({
                '_id': str(ObjectId()),
                'username': 'admin',
                'password': generate_password_hash('AdminPassword123'),
            })
            print('[DATABASE] Default admin seeded.')
    except Exception as e:
        print(f'[DATABASE] Admin seed error: {e}')


def init_db(app):
    """
    Initialise the database.
    Priority: Supabase  →  MongoDB Atlas  →  MockDatabase (JSON / /tmp)
    """
    global db

    # ── 1. Try Supabase ──────────────────────────────────────
    sb_url = app.config.get('SUPABASE_URL')
    sb_key = app.config.get('SUPABASE_KEY')
    if sb_url and sb_key:
        print('[DATABASE] Supabase config detected — testing connection…')
        try:
            sdb = SupabaseDatabase(sb_url, sb_key)
            sdb.admins.find_one({})   # will raise SupabaseTableNotFoundError if table missing
            print('[DATABASE] ✓ Supabase connected.')
            _seed_admin(sdb)
            db = sdb
            return db
        except SupabaseTableNotFoundError as e:
            print(f'[DATABASE] Supabase tables missing — {e}')
            print('[DATABASE] ACTION: run setup_supabase.sql in the Supabase SQL Editor.')
            print('[DATABASE] Falling back to MongoDB / MockDB…')
        except Exception as e:
            print(f'[DATABASE] Supabase error: {e} — falling back…')

    # ── 2. Try MongoDB ───────────────────────────────────────
    mongo_uri = app.config.get('MONGO_URI', '')
    if mongo_uri and 'localhost' not in mongo_uri:
        try:
            print(f'[DATABASE] Trying MongoDB: {mongo_uri[:40]}…')
            mclient = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
            )
            mclient.admin.command('ping')
            db_name = (mongo_uri.split('/')[-1].split('?')[0] or 'online_voting_system')
            mdb = mclient[db_name]
            # Indexes
            mdb.admins.create_index('username', unique=True)
            mdb.voters.create_index('email', unique=True)
            mdb.voters.create_index('voter_id', unique=True)
            mdb.votes.create_index([('voter_id', 1), ('election_id', 1)], unique=True)
            _seed_admin(mdb)
            print(f'[DATABASE] ✓ MongoDB connected ({db_name}).')
            db = mdb
            return db
        except Exception as e:
            print(f'[DATABASE] MongoDB error: {e} — falling back to MockDB…')

    # ── 3. MockDatabase (always works) ───────────────────────
    print('[DATABASE] Using MockDatabase (JSON / /tmp).')
    base_dir  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mock_file = os.path.join(base_dir, 'mock_db.json')
    mocked    = MockDatabase(mock_file)
    _seed_admin(mocked)
    db = mocked
    return db


# ═════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════
def get_db():
    global db
    if db is None:
        raise RuntimeError('Database not initialised. Call init_db(app) first.')
    return db


def safe_object_id(val):
    """
    Convert val to ObjectId if it is a valid 24-hex string,
    otherwise return it as a plain string (Supabase / MockDB IDs).
    Prevents bson.errors.InvalidId.
    """
    if val is None:
        return None
    if isinstance(val, ObjectId):
        return val
    s = str(val)
    if ObjectId.is_valid(s):
        return ObjectId(s)
    return s
