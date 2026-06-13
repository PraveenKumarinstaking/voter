import urllib.request
import urllib.parse
import re
import sys

BASE_URL = "http://127.0.0.1:5000"

def run_request(opener, url, data=None):
    if data:
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(url, data=encoded_data)
    else:
        req = urllib.request.Request(url)
    
    try:
        with opener.open(req) as response:
            html = response.read().decode('utf-8')
            return response.getcode(), html
    except urllib.error.HTTPError as e:
        html = e.read().decode('utf-8')
        return e.code, html

def test_flow():
    print("==================================================")
    print("    RUNNING RESULTS PUBLISHING INTEGRATION TESTS   ")
    print("==================================================")
    
    # Create cookie jar and opener for admin and voter
    admin_cookie_processor = urllib.request.HTTPCookieProcessor()
    admin_opener = urllib.request.build_opener(admin_cookie_processor)
    
    voter_cookie_processor = urllib.request.HTTPCookieProcessor()
    voter_opener = urllib.request.build_opener(voter_cookie_processor)
    
    # 1. Log in as Admin
    login_data = {
        "username_or_email": "admin",
        "password": "AdminPassword123",
        "login_type": "admin"
    }
    code, html = run_request(admin_opener, f"{BASE_URL}/login", login_data)
    assert code == 200
    assert "Admin Dashboard" in html or "Control Center" in html
    print("[OK] Logged in as Admin successfully.")
    
    # Find active election and extract the ID
    election_match = re.search(r'href="/admin/election/([a-f0-9]{24})/status/completed"', html)
    already_completed = False
    
    if election_match:
        election_id = election_match.group(1)
        print(f"[INFO] Found active election ID: {election_id}")
        # Click End Polls
        end_code, end_html = run_request(admin_opener, f"{BASE_URL}/admin/election/{election_id}/status/completed")
        assert "status changed to" in end_html.lower() or "completed" in end_html.lower()
        print("[OK] Ended polls successfully.")
    else:
        # Check if already completed and has publish link
        publish_match = re.search(r'href="/admin/election/([a-f0-9]{24})/publish/[01]"', html)
        if publish_match:
            election_id = publish_match.group(1)
            print(f"[INFO] Election is already completed. Found election ID: {election_id}")
            already_completed = True
        else:
            # Try finding results link
            results_match = re.search(r'href="/admin/election/([a-f0-9]{24})/results"', html)
            if results_match:
                election_id = results_match.group(1)
                print(f"[INFO] Election is completed. Found election ID: {election_id}")
                already_completed = True
            else:
                print("[FAIL] Could not find election in the admin dashboard.")
                sys.exit(1)
                
    # Reset state: Ensure results are retracted/hidden initially for the test
    hide_url = f"{BASE_URL}/admin/election/{election_id}/publish/0"
    run_request(admin_opener, hide_url)
    print("[INFO] Reset results publication status to Hidden/Retracted.")
                
    # 2. Log in as Voter
    voter_login_data = {
        "username_or_email": "sarah@example.com",
        "password": "VoterPassword123",
        "login_type": "voter"
    }
    code, html = run_request(voter_opener, f"{BASE_URL}/login", voter_login_data)
    assert code == 200
    assert "Voter Voting Desk" in html or "Voter Portal" in html
    print("[OK] Logged in as Voter successfully.")
    
    # Try to access results directly (should fail since not published yet)
    results_url = f"{BASE_URL}/election/{election_id}/results"
    
    code, html = run_request(voter_opener, results_url)
    assert "Results for this election have not been published yet." in html
    print("[OK] Voter blocked from viewing unpublished results directly via URL.")
    
    # Check that voter dashboard has "Results Pending" disabled button for this election
    code, html = run_request(voter_opener, f"{BASE_URL}/dashboard")
    assert f'href="/election/{election_id}/results"' not in html
    print("[OK] Voter dashboard shows results are pending (no view link) for this election.")
    
    # 3. Publish results as Admin
    publish_url = f"{BASE_URL}/admin/election/{election_id}/publish/1"
    code, html = run_request(admin_opener, publish_url)
    assert "published successfully" in html
    print("[OK] Admin published election results successfully.")
    
    # 4. Check results as Voter again
    code, html = run_request(voter_opener, f"{BASE_URL}/dashboard")
    assert f'href="/election/{election_id}/results"' in html
    print("[OK] Voter dashboard now shows 'View Results' link for this election.")
    
    # Fetch results page as Voter
    code, html = run_request(voter_opener, results_url)
    assert code == 200
    assert "Results -" in html
    assert "Tally breakdown" in html
    print("[OK] Voter successfully viewed results page and saw correct breakdown.")
    
    # 5. Hide results again as Admin
    hide_url = f"{BASE_URL}/admin/election/{election_id}/publish/0"
    code, html = run_request(admin_opener, hide_url)
    assert "retracted" in html or "hidden" in html
    print("[OK] Admin retracted (hid) election results successfully.")
    
    # 6. Verify voter is blocked again
    code, html = run_request(voter_opener, results_url)
    assert "Results for this election have not been published yet." in html
    print("[OK] Voter is blocked from viewing results after retraction.")
    
    print("==================================================")
    print("      ALL RESULTS PUBLISHING TESTS PASSED         ")
    print("==================================================")

if __name__ == "__main__":
    test_flow()
