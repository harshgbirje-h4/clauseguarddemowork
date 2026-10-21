import requests
import time
import subprocess
import os
import sys

# Start the Flask app
flask_process = subprocess.Popen([sys.executable, "src/dashboard.py"])
time.sleep(3)

try:
    # Clear db for clean test
    db_path = os.path.abspath('data/db/portfolio.db')
    sys.path.insert(0, os.path.abspath('src'))
    from db import init_db, reset_db
    init_db(db_path)
    reset_db(db_path)
    
    # 1. Save Service A
    sa_payload = {
        "service_name": "Service A",
        "mode": "MOCK",
        "clauses": [
            {
                "text": "Location clause",
                "entities": ["Location Data"],
                "severity_score": 1,
                "specificity_score": 1,
                "risk_category": "Cat",
                "canonical_entities": ["Location"]
            },
            {
                "text": "IP clause",
                "entities": ["IP"],
                "severity_score": 1,
                "specificity_score": 1,
                "risk_category": "Cat",
                "canonical_entities": ["IP Address"]
            }
        ],
        "canonical_entities": ["Location", "IP Address"]
    }
    requests.post('http://127.0.0.1:5000/api/save-service', json=sa_payload)

    # 2. Save Service B
    sb_payload = {
        "service_name": "Service B",
        "mode": "MOCK",
        "clauses": [
            {
                "text": "IP clause",
                "entities": ["IP"],
                "severity_score": 1,
                "specificity_score": 1,
                "risk_category": "Cat",
                "canonical_entities": ["IP Address"]
            },
            {
                "text": "Email clause",
                "entities": ["Email"],
                "severity_score": 1,
                "specificity_score": 1,
                "risk_category": "Cat",
                "canonical_entities": ["Email"]
            }
        ],
        "canonical_entities": ["IP Address", "Email"]
    }
    requests.post('http://127.0.0.1:5000/api/save-service', json=sb_payload)

    # Check portfolio
    r = requests.get('http://127.0.0.1:5000/api/portfolio')
    port = r.json()
    assert len(port["services"]) == 2

    # Now compare candidate A = "Service B" vs candidate B = "Service A"
    # Service B is already in portfolio.
    # The Marginal Risk Delta for Service B against a baseline excluding Service B:
    # Baseline without Service B has Service A:
    #   Entities = {Location, IP Address}
    # If we add Service B:
    #   Entities of Service B = {IP Address, Email}
    #   Overlapping entities = {IP Address}
    #   Newly introduced entities = {Email}
    
    compare_payload = {
        "candidate_a": "Service B",
        "candidate_b": "Service A"
    }
    r = requests.post('http://127.0.0.1:5000/api/compare-services', json=compare_payload)
    assert r.status_code == 200
    res = r.json()
    
    ca = res["candidate_a"]
    assert ca["candidate_name"] == "Service B"
    assert "IP Address" in ca["overlapping_entities"]
    
    # Since Service B is excluded from the baseline during calculation,
    # "Email" should be recognized as newly introduced, not overlapping.
    assert "Email" in ca["newly_introduced_entities"]
    assert "Email" not in ca["overlapping_entities"]
    
    print("End-to-end Phase 2B test passed!")

finally:
    # Always restore database to clean state after test
    try:
        from db import reset_db
        reset_db(db_path)
    except Exception:
        pass
    flask_process.terminate()
    flask_process.wait()
