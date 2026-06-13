-- Supabase PostgreSQL Schema for Online Voting System
-- Execute this script in the SQL Editor of your Supabase dashboard.

-- 1. Create Admins Table
CREATE TABLE IF NOT EXISTS admins (
    _id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create Voters Table
CREATE TABLE IF NOT EXISTS voters (
    _id TEXT PRIMARY KEY,
    voter_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_approved BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create Elections Table
CREATE TABLE IF NOT EXISTS elections (
    _id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'upcoming',
    is_results_published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create Candidates Table
CREATE TABLE IF NOT EXISTS candidates (
    _id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    party TEXT NOT NULL,
    bio TEXT,
    symbol_url TEXT,
    election_id TEXT REFERENCES elections(_id) ON DELETE CASCADE
);

-- 5. Create Votes Table (with Double-Voting Constraint)
CREATE TABLE IF NOT EXISTS votes (
    _id TEXT PRIMARY KEY,
    voter_id TEXT REFERENCES voters(_id) ON DELETE CASCADE,
    election_id TEXT REFERENCES elections(_id) ON DELETE CASCADE,
    candidate_id TEXT REFERENCES candidates(_id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (voter_id, election_id)
);

-- Enable Row Level Security (RLS) policies if you want, but by default postgrest requires it.
-- For simplicity of a local backend using admin bypass or service keys, we can keep tables public.
-- If RLS is enabled, you must add policies allowing public read/write if using anon key.
-- To allow public access to all tables for the anon role under this client:
ALTER TABLE admins DISABLE ROW LEVEL SECURITY;
ALTER TABLE voters DISABLE ROW LEVEL SECURITY;
ALTER TABLE elections DISABLE ROW LEVEL SECURITY;
ALTER TABLE candidates DISABLE ROW LEVEL SECURITY;
ALTER TABLE votes DISABLE ROW LEVEL SECURITY;

-- 6. Insert Seed Admin (Username: admin, Password: AdminPassword123)
INSERT INTO admins (_id, username, password)
VALUES (
    '000000000000000000000100',
    'admin',
    'scrypt:32768:8:1$DhA6U3vYYmguzNtS$9bb1ef5cf1b582c194b2f8d7ff7d0e7aa1a79eb52e7a90bc2340bb1870abaf8c6d4025454c36deb9b5fb0be14ccd5300cd954da835dd93cc76b4bf9a1ebe1cd1'
)
ON CONFLICT (username) DO NOTHING;

-- 7. Insert Seed Voters (Password: VoterPassword123)
INSERT INTO voters (_id, voter_id, name, email, password, is_approved)
VALUES 
(
    '000000000000000000000201',
    'VOTE-111111',
    'Sarah Connor',
    'sarah@example.com',
    'scrypt:32768:8:1$rx9lJug0MZBxPRX9$6608ee9f5cbbebcf4797db6656dd4ad57e01825a0f730c845af8baa4b4bda734c6a49b14cd54a001f44870f2b2a910299d06fbedff34406f2b4fb57159d33082',
    TRUE
),
(
    '000000000000000000000202',
    'VOTE-222222',
    'John Connor',
    'john@example.com',
    'scrypt:32768:8:1$rx9lJug0MZBxPRX9$6608ee9f5cbbebcf4797db6656dd4ad57e01825a0f730c845af8baa4b4bda734c6a49b14cd54a001f44870f2b2a910299d06fbedff34406f2b4fb57159d33082',
    TRUE
)
ON CONFLICT (email) DO NOTHING;

-- 8. Insert Seed Elections
INSERT INTO elections (_id, title, description, status, is_results_published)
VALUES 
(
    '000000000000000000000301',
    '2026 Student Council Election',
    'Vote for the upcoming Student Council President to lead academic initiatives and student representation.',
    'active',
    FALSE
),
(
    '000000000000000000000302',
    'Municipal Board Elections',
    'Select representatives for the Municipal Development Council.',
    'upcoming',
    FALSE
)
ON CONFLICT (_id) DO NOTHING;

-- 9. Insert Seed Candidates (for Student Council Election)
INSERT INTO candidates (_id, name, party, bio, election_id)
VALUES 
(
    '000000000000000000000401',
    'Alice Smith',
    'Innovation Alliance',
    'Alice is a senior majoring in Computer Science. She aims to improve digital campus tools and extend library hours.',
    '000000000000000000000301'
),
(
    '000000000000000000000402',
    'Bob Jones',
    'Student Voice Party',
    'Bob is a junior majoring in Political Science. He is focused on campus sustainability, reducing food waste, and transit aid.',
    '000000000000000000000301'
)
ON CONFLICT (_id) DO NOTHING;
