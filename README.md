# VoteFlow - Secure Online Voting System

A complete, production-ready, and modern **Online Voting System** designed with a premium Bootstrap 5 dark glassmorphic user interface and a Python Flask + MongoDB backend.

---

## Technical Stack
* **Frontend:** HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, FontAwesome Icons
* **Backend:** Python Flask
* **Database:** MongoDB (using PyMongo client driver)
* **Security:** Cryptographic password hashing (`werkzeug.security`) and compound database-level unique indexes to enforce single-vote constraints.

---

## Features

### 1. Authentication Module
* **Unified Login Portal:** Toggle seamlessly between Voter and Administrator authentication.
* **Voter Registration:** Checks for unique Voter ID numbers and email configurations to prevent double registrations.
* **Secure Session Cookies:** Manages voter and admin credentials securely in Flask session states.

### 2. Administrative Control Center
* **Live Statistics Dashboard:** View real-time totals of registered voters, candidates, elections, and ballots.
* **Elections Management:** Configure electoral assemblies and toggle states (`upcoming` -> `active` -> `completed`).
* **Candidate Management:** Full CRUD capabilities to attach candidates to specific active/upcoming elections.
* **Tally Aggregation:** Instant vote tallying with percentage calculations and progress visualizations.

### 3. Voter Voting Desk
* **Eligible Ballots:** Checks active elections and lists only the ones the voter hasn't participated in yet.
* **Duplication Defense:** Implements strict database unique constraint blocks (`voter_id` + `election_id`) preventing double voting.
* **Interactive Ballots:** Highly aesthetic cards with dynamic candidate highlight selections.
* **Receipt Generation:** Secure cryptographic-style confirmation receipt for each cast vote.

---

## Installation & Setup Guide

### 1. Prerequisites
Ensure you have the following installed on your system:
* **Python 3.13+** (Installed during automated setup)
* **MongoDB** (A local MongoDB Community server running on port `27017` OR a MongoDB Atlas cluster URI)

### 2. Virtual Environment Setup
Open a terminal in the `online-voting-system/` directory and execute:
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 3. Database Configuration
Open the `.env` file in the project folder and configure your MongoDB connection:
* **Local MongoDB:** Defaults to `mongodb://localhost:27017/online_voting_system` (No changes needed if running locally).
* **MongoDB Atlas:** Replace `MONGO_URI` with your connection string. If using the database password from `mongodb.txt` (`twutD0b2vcL9J6Md`), it might look like:
  ```env
  MONGO_URI=mongodb+srv://admin:twutD0b2vcL9J6Md@cluster0.mongodb.net/online_voting_system?retryWrites=true&w=majority
  ```

---

## How to Run & Verify

### 1. Run Verification Checks
Test your imports, hashing, and database connectivity:
```powershell
python test_app.py
```

### 2. Seed Sample Data
Populate the database with sample voters, active elections, and candidates:
```powershell
python seed_data.py
```

### 3. Start the Flask Server
Launch the development web server:
```powershell
python app.py
```
Open your web browser and navigate to `http://127.0.0.1:5000`.

---

## Seed Accounts & Testing Credentials

If you populated the database using `seed_data.py`, you can use these accounts to test the application flows:

### Administrator Credentials
* **Username:** `admin`
* **Password:** `AdminPassword123`

### Sample Voter Credentials
1. **Sarah Connor** (Eligible to vote in "2026 Student Council Election")
   * **Email/ID:** `sarah@example.com` or `VOTE-111111`
   * **Password:** `VoterPassword123`
2. **John Connor** (Eligible to vote in "2026 Student Council Election")
   * **Email/ID:** `john@example.com` or `VOTE-222222`
   * **Password:** `VoterPassword123`

---

## Project Structure
```text
online-voting-system/
│
├── app.py                 # Main entry point & Flask initialization
├── config.py              # Application configuration and settings loader
├── seed_data.py           # Database seeder utility
├── test_app.py            # Automated environment & connection verifier
├── requirements.txt       # Project dependencies listing
├── .env                   # Local environment variable configuration
│
├── database/
│   └── mongodb.py         # DB connection client, schemas & default seed
│
├── routes/
│   ├── auth.py            # Voter sign-up, sign-in & sign-out handlers
│   ├── admin.py           # Admin dashboards, candidate CRUD & tallying
│   └── voting.py          # Ballot panels & secure voting transactions
│
├── static/
│   └── css/
│       └── style.css      # Custom dark-theme glassmorphism CSS
│
└── templates/
    ├── base.html          # Global header, navbar & footer layout
    ├── index.html         # Landing page & feature showcase
    ├── login.html         # Unified Voter/Admin authentication form
    ├── register.html      # Voter signup form with matching checks
    ├── admin_dashboard.html# Administrator panel controls
    ├── voting.html        # Voter portal main page listing elections
    ├── voting_ballot.html # Voter interactive ballot selection
    └── vote_confirmation.html# Successful vote submission details
```
