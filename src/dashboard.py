import os
import sys
import logging
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scoring import ScoringEngine
from src.marginal import MarginalRiskEngine
from src.extract import extract_pipeline
from src.canonicalize import EntityCanonicalizer

app = Flask(__name__, static_folder='static')

# Minimal CORS for extension development
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'db', 'portfolio.db'))

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    engine = ScoringEngine()
    try:
        data = engine.get_portfolio_data(DB_PATH)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/marginal-risk', methods=['POST'])
def calculate_marginal_risk():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    candidate = request.json
    if not candidate or 'service_name' not in candidate or 'clauses' not in candidate:
        return jsonify({"error": "Invalid candidate JSON structure"}), 400
        
    engine = MarginalRiskEngine(DB_PATH)
    try:
        result = engine.calculate_marginal_risk(candidate)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-policy', methods=['POST', 'OPTIONS'])
def analyze_policy():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    data = request.json
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' in request body"}), 400
        
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Policy text is empty"}), 400
        
    url = data.get("url", "")
    title = data.get("title", "")
    
    # Always prioritize domain name so everything doesn't get grouped as "Privacy Policy"
    service_name = ""
    if url:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc:
            parts = parsed.netloc.split('.')
            if parts[0] == 'www':
                parts = parts[1:]
                
            if len(parts) >= 2:
                if parts[-2] in ['co', 'com', 'org', 'net', 'edu', 'gov'] and len(parts) >= 3:
                    domain = parts[-3]
                else:
                    domain = parts[-2]
                service_name = domain.capitalize()
            elif len(parts) == 1:
                service_name = parts[0].capitalize()
            
    if not service_name and title:
        service_name = title.split('-')[0].strip()
        
    if not service_name:
        service_name = "Unknown Web Service"

    try:
        # C1 Extraction
        extracted = extract_pipeline(text, service_name)
        
        # C2 Canonicalization (in-memory)
        canonicalizer = EntityCanonicalizer()
        all_canonical_entities = set()
        for clause in extracted.get("clauses", []):
            canon_list = [c_e for e in clause.get("entities", []) if (c_e := canonicalizer.canonicalize(e)) is not None]
            clause["canonical_entities"] = canon_list
            all_canonical_entities.update(canon_list)
            
        # C4 Scoring
        scoring_engine = ScoringEngine()
        risk = scoring_engine.calculate_service_score_from_clauses(extracted.get("clauses", []))
        
        mode = extracted.get("mode", "UNKNOWN")
        
        # Assemble Response
        response_data = {
            "service_name": extracted.get("service_name"),
            "mode": mode,
            "clauses": extracted.get("clauses", []),
            "canonical_entities": sorted(list(all_canonical_entities)),
            "risk": risk,
            "policy_url": url
        }
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        return jsonify({"error": f"Extraction failed: {str(e)}"}), 500

@app.route('/api/save-service', methods=['POST', 'OPTIONS'])
def save_service():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.json
    if not data or 'service_name' not in data or 'clauses' not in data:
        return jsonify({"error": "Invalid analysis result data"}), 400

    try:
        from src.canonicalize import DatabaseLoader
        canonicalizer = EntityCanonicalizer()
        loader = DatabaseLoader(DB_PATH)
        loader.load_extraction(data, canonicalizer)
        return jsonify({"status": "success", "message": "Service added to portfolio"}), 201
    except Exception as e:
        logging.error(f"Save failed: {e}")
        return jsonify({"error": f"Failed to save service: {str(e)}"}), 500

@app.route('/api/overlap-graph', methods=['GET'])
def get_overlap_graph():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    engine = ScoringEngine()
    try:
        data = engine.get_portfolio_data(DB_PATH)
        
        nodes = []
        edges = []
        
        # Add service nodes
        for service in data.get("services", []):
            nodes.append({"id": service["service_name"], "group": "service"})
            
        # Add entity nodes and edges
        added_entities = set()
        for service in data.get("services", []):
            s_name = service["service_name"]
            for ent in service.get("entities", []):
                if ent not in added_entities:
                    nodes.append({"id": ent, "group": "entity"})
                    added_entities.add(ent)
                # Deduplicate edges conceptually
                edge_id = f"{s_name}->{ent}"
                edges.append({"source": s_name, "target": ent, "id": edge_id})
        
        # Deduplicate edges list
        unique_edges = {e["id"]: e for e in edges}.values()
        
        return jsonify({
            "nodes": nodes,
            "edges": list(unique_edges)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/quick-compare', methods=['POST'])
def quick_compare():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    req_data = request.json
    if not req_data or 'candidate' not in req_data or 'target' not in req_data:
        return jsonify({"error": "Must provide candidate and target"}), 400
        
    candidate = req_data['candidate']
    target_name = req_data['target']
    
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM services WHERE name = ?", (target_name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": f"Service not found: {target_name}"}), 404
        
    target_id = row[0]
    cursor.execute("""
        SELECT DISTINCT ce.name 
        FROM canonical_entities ce
        JOIN clause_entity_mapping cem ON ce.id = cem.entity_id
        JOIN clauses c ON cem.clause_id = c.id
        WHERE c.service_id = ?
    """, (target_id,))
    target_entities = set(r[0] for r in cursor.fetchall())
    conn.close()
    
    candidate_entities = set()
    from src.canonicalize import EntityCanonicalizer
    canonicalizer = EntityCanonicalizer()
    for clause in candidate.get("clauses", []):
        for e in clause.get("entities", []):
            ce = canonicalizer.canonicalize(e)
            if ce and not ce.startswith("Unknown"):
                candidate_entities.add(ce)
                
    overlap = candidate_entities.intersection(target_entities)
    new_ents = candidate_entities.difference(target_entities)
    
    return jsonify({
        "overlap": list(overlap),
        "new": list(new_ents)
    })

@app.route('/api/compare-services', methods=['POST'])
def compare_services():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    req_data = request.json
    if not req_data or 'candidate_a' not in req_data or 'candidate_b' not in req_data:
        return jsonify({"error": "Must provide candidate_a and candidate_b"}), 400

    def get_candidate(candidate_data):
        if isinstance(candidate_data, dict):
            return candidate_data
            
        # Fetch from DB if string
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM services WHERE name = ?", (candidate_data,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Service not found: {candidate_data}")
            
        service_id = row[0]
        cursor.execute("SELECT id, text, severity_score, specificity_score, risk_category FROM clauses WHERE service_id = ?", (service_id,))
        clauses = []
        for c_id, text, sev, spec, cat in cursor.fetchall():
            cursor.execute("""
                SELECT ce.name 
                FROM canonical_entities ce
                JOIN clause_entity_mapping cem ON ce.id = cem.entity_id
                WHERE cem.clause_id = ?
            """, (c_id,))
            ents = [r[0] for r in cursor.fetchall()]
            clauses.append({
                "text": text,
                "severity_score": sev,
                "specificity_score": spec,
                "risk_category": cat,
                "entities": ents
            })
        conn.close()
        return {
            "service_name": candidate_data,
            "clauses": clauses
        }
        
    try:
        cand_a = get_candidate(req_data["candidate_a"])
        cand_b = get_candidate(req_data["candidate_b"])
        
        engine = MarginalRiskEngine(DB_PATH)
        res_a = engine.calculate_marginal_risk(cand_a)
        res_b = engine.calculate_marginal_risk(cand_b)
        return jsonify({
            "candidate_a": res_a,
            "candidate_b": res_b
        })
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/proxy-fetch', methods=['POST', 'OPTIONS'])
def proxy_fetch():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        url = request.json.get("url")
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        
        html = res.text
        
        # If the website blocks our Python bot (e.g. Cloudflare 403 or 200 Challenge), throw an error
        if res.status_code != 200 or "Just a moment..." in html or "cloudflare" in html.lower() or "datadome" in html.lower():
            return jsonify({"error": f"Website blocked the background fetch."}), 403
            
        return jsonify({"html": html}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting ClauseGuard Dashboard...")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(host='127.0.0.1', port=5000, debug=True)
