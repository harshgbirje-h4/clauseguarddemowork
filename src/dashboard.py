import os
import sys
import logging
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

# Ensure project root and src dir are in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.scoring import ScoringEngine
from src.marginal import MarginalRiskEngine
from src.extract import extract_pipeline
from src.canonicalize import EntityCanonicalizer
from src.risk import policy_risk_score, risk_category, coverage_report

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
        # Additive score kept for compatibility; the de-duplicated view is added alongside it.
        data.update(engine.get_exposure_by_data_type(DB_PATH))
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
    # Set by the extension when the page text was cut before it was sent.
    truncated = bool(data.get("truncated", False))

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
        unmapped = {}        # raw phrase -> suggested category (or None)
        entity_sources = {}  # canonical entity -> clause texts it came from (for review)
        for clause in extracted.get("clauses", []):
            canon_list = []
            clause_text = (clause.get("text") or "")[:200]
            for raw in clause.get("entities", []):
                detail = canonicalizer.resolve_detail(raw)
                if detail["canonical"] is None:
                    continue
                canon_list.append(detail["canonical"])
                if detail["is_known"]:
                    sources = entity_sources.setdefault(detail["canonical"], [])
                    if clause_text and clause_text not in sources:
                        sources.append(clause_text)
                else:
                    unmapped[raw.strip()] = detail["suggestion"]
            clause["canonical_entities"] = canon_list
            all_canonical_entities.update(canon_list)

        clauses = extracted.get("clauses", [])
        mode = extracted.get("mode", "UNKNOWN")
        is_demo = mode.startswith("MOCK")

        # C4 Scoring: bounded 0-100 score, plus category and coverage.
        # The old unbounded sum is kept as raw_risk for backward compatibility.
        score = policy_risk_score(clauses)
        coverage = coverage_report(
            analysed_chars=len(text),
            truncated=truncated,
            clauses_found=len(clauses),
            is_demo=is_demo,
        )
        category = risk_category(score, coverage)
        raw_risk = ScoringEngine().calculate_service_score_from_clauses(clauses)

        # Check if service is already saved in portfolio
        is_saved = False
        previous_scan = None
        if os.path.exists(DB_PATH):
            try:
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT id, name, category FROM services WHERE name = ? COLLATE NOCASE", (extracted.get("service_name"),))
                s_row = cur.fetchone()
                if s_row:
                    is_saved = True
                    s_id, s_name, s_cat = s_row
                    cur.execute("SELECT severity_score, specificity_score FROM clauses WHERE service_id = ?", (s_id,))
                    c_rows = cur.fetchall()
                    c_list = [{'severity_score': r[0], 'specificity_score': r[1]} for r in c_rows]
                    s_score = policy_risk_score(c_list)
                    legacy_score = ScoringEngine().calculate_service_score_from_clauses(c_list)
                    cur.execute("""
                        SELECT DISTINCT ce.name
                        FROM canonical_entities ce
                        JOIN clause_entity_mapping cem ON ce.id = cem.entity_id
                        JOIN clauses c ON cem.clause_id = c.id
                        WHERE c.service_id = ?
                    """, (s_id,))
                    p_entities = [r[0] for r in cur.fetchall()]
                    previous_scan = {
                        "service_name": s_name,
                        "service_score": s_score,
                        "legacy_score": legacy_score,
                        "entities": p_entities,
                        "clause_count": len(c_rows)
                    }
                conn.close()
            except Exception as dbe:
                logging.warning(f"Could not check existing service in portfolio: {dbe}")

        # Extract third-party sharing and user privacy controls (Phase 2 & 3)
        sharing_keywords = [
            "share", "disclose", "distribute", "sell", "transfer", "third part", "affiliate", "partner",
            "advertis", "marketing partner", "vendor", "service provider"
        ]
        control_keywords = [
            "opt-out", "opt out", "unsubscribe", "delete", "deletion", "rectif", "access your data",
            "privacy setting", "your choice", "cookie setting", "do not track", "rights", "request"
        ]

        sharing_findings = []
        control_findings = []
        for c in clauses:
            c_text = c.get("text") or ""
            c_text_lower = c_text.lower()
            c_sev = float(c.get("severity_score") or 0)
            c_spec = float(c.get("specificity_score") or 0)
            c_risk = round(100.0 * (c_sev / 5.0) * (c_spec / 5.0), 1)

            if any(kw in c_text_lower for kw in sharing_keywords):
                if any(w in c_text_lower for w in ["sell", "sale", "commercial value", "monetiz"]):
                    kind = "Selling / Commercial Transfer"
                    summary = "States or reserves the right to sell or commercially transfer personal data."
                elif any(w in c_text_lower for w in ["advertis", "marketing partner", "ad network", "targeted ad"]):
                    kind = "Advertising & Marketing Partners"
                    summary = "Discloses personal data to advertisers, ad networks, or promotional partners."
                elif any(w in c_text_lower for w in ["vendor", "service provider", "subprocessor", "contractor", "processor"]):
                    kind = "Service Providers & Vendors"
                    summary = "Transfers data to contracted third-party operational service providers."
                elif any(w in c_text_lower for w in ["affiliate", "subsidiary", "parent company", "group company"]):
                    kind = "Corporate Affiliates"
                    summary = "Shares personal information across internal corporate entities and affiliates."
                else:
                    kind = "Third-Party Sharing"
                    summary = "Discloses personal information to external third parties."

                sharing_findings.append({
                    "kind": kind,
                    "summary": summary,
                    "clause_text": c_text,
                    "risk": c_risk,
                    "entities": c.get("canonical_entities") or c.get("entities") or []
                })

            if any(kw in c_text_lower for kw in control_keywords):
                if any(w in c_text_lower for w in ["delete", "deletion", "erasure", "erase", "remove account"]):
                    kind = "Account / Data Deletion"
                    summary = "Provides procedures to request deletion of personal information or account data."
                elif any(w in c_text_lower for w in ["opt-out", "opt out", "unsubscribe", "promotional email"]):
                    kind = "Marketing Opt-Out"
                    summary = "Allows opting out of direct promotional communications or targeted messages."
                elif any(w in c_text_lower for w in ["cookie", "do not track", "tracker", "ad preference"]):
                    kind = "Cookie & Tracking Controls"
                    summary = "Offers controls or instructions for managing cookies and tracking technologies."
                elif any(w in c_text_lower for w in ["access", "copy", "portability", "export", "download your data"]):
                    kind = "Data Access & Portability"
                    summary = "Specifies rights to request a copy of collected personal records."
                else:
                    kind = "Privacy Rights & Requests"
                    summary = "Describes privacy preferences and request mechanisms."

                control_findings.append({
                    "kind": kind,
                    "summary": summary,
                    "clause_text": c_text,
                    "risk": c_risk,
                    "category": c.get("risk_category") or "User Control"
                })

        if len(control_findings) < 2 and text:
            raw_sentences = [s.strip() for s in text.replace("\n", " ").split(".") if len(s.strip()) > 15]
            for s in raw_sentences:
                s_lower = s.lower()
                if any(kw in s_lower for kw in control_keywords):
                    if any(w in s_lower for w in ["delete", "deletion", "erasure", "erase", "remove account"]):
                        kind = "Account / Data Deletion"
                        summary = "Provides procedures to request deletion of personal information or account data."
                    elif any(w in s_lower for w in ["opt-out", "opt out", "unsubscribe", "promotional email"]):
                        kind = "Marketing Opt-Out"
                        summary = "Allows opting out of direct promotional communications or targeted messages."
                    elif any(w in s_lower for w in ["cookie", "do not track", "tracker", "ad preference"]):
                        kind = "Cookie & Tracking Controls"
                        summary = "Offers controls or instructions for managing cookies and tracking technologies."
                    elif any(w in s_lower for w in ["access", "copy", "portability", "export", "download your data"]):
                        kind = "Data Access & Portability"
                        summary = "Specifies rights to request a copy of collected personal records."
                    else:
                        kind = "Privacy Rights & Requests"
                        summary = "Describes privacy preferences and request mechanisms."

                    if not any(cf["clause_text"] == s for cf in control_findings):
                        control_findings.append({
                            "kind": kind,
                            "summary": summary,
                            "clause_text": s,
                            "risk": 15.0,
                            "category": "User Control"
                        })
                if len(control_findings) >= 5:
                    break

        # Collection findings (Phase 2: What data is collected?)
        collection_findings = []
        for ent in sorted(list(all_canonical_entities)):
            sources = entity_sources.get(ent, [])
            quote = sources[0] if sources else None
            collection_findings.append({
                "entity": ent,
                "evidence": quote
            })

        # Assemble Response
        response_data = {
            "service_name": extracted.get("service_name"),
            "mode": mode,
            "clauses": clauses,
            "canonical_entities": sorted(list(all_canonical_entities)),
            "collection_findings": collection_findings,
            "unmapped_entities": sorted(unmapped),
            "unmapped_suggestions": unmapped,   # raw phrase -> suggested category, for review only
            "entity_sources": entity_sources,   # canonical entity -> clause text it came from
            "risk": score,              # 0-100, same key the extension already reads
            "risk_score": score,
            "risk_category": category,  # Low / Moderate / High / Very High / Inconclusive
            "raw_risk": raw_risk,       # legacy unbounded sum, not for display
            "coverage": coverage,
            "is_saved_in_portfolio": is_saved,
            "previous_scan": previous_scan,
            "sharing_findings": sharing_findings[:5],
            "control_findings": control_findings[:5],
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

@app.route('/api/service-status', methods=['GET'])
def get_service_status():
    if not os.path.exists(DB_PATH):
        return jsonify({"is_saved": False, "service": None})
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({"is_saved": False, "service": None})
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, name, category FROM services WHERE name = ? COLLATE NOCASE", (name,))
        s_row = cur.fetchone()
        if not s_row:
            # Try matching hostname variations (e.g. spotify from spotify.com)
            clean_name = name.lower().replace("www.", "").split(".")[0].capitalize()
            cur.execute("SELECT id, name, category FROM services WHERE name = ? COLLATE NOCASE", (clean_name,))
            s_row = cur.fetchone()
            
        if s_row:
            s_id, s_name, s_cat = s_row
            cur.execute("SELECT severity_score, specificity_score FROM clauses WHERE service_id = ?", (s_id,))
            c_rows = cur.fetchall()
            c_list = [{'severity_score': r[0], 'specificity_score': r[1]} for r in c_rows]
            s_score = policy_risk_score(c_list)
            cur.execute("""
                SELECT DISTINCT ce.name
                FROM canonical_entities ce
                JOIN clause_entity_mapping cem ON ce.id = cem.entity_id
                JOIN clauses c ON cem.clause_id = c.id
                WHERE c.service_id = ?
            """, (s_id,))
            entities = [r[0] for r in cur.fetchall()]
            conn.close()
            return jsonify({
                "is_saved": True,
                "service": {
                    "service_name": s_name,
                    "service_score": s_score,
                    "category": s_cat,
                    "entities": entities,
                    "clause_count": len(c_rows)
                }
            })
        conn.close()
        return jsonify({"is_saved": False, "service": None})
    except Exception as e:
        return jsonify({"error": str(e), "is_saved": False}), 500

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/proxy-fetch', methods=['POST', 'OPTIONS'])
def proxy_fetch():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        url = request.json.get("url") if request.json else None
        if not url:
            return jsonify({"error": "Missing 'url' parameter"}), 400
            
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9'
            }
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode('utf-8', errors='replace')
            if "Just a moment..." in html or "cloudflare" in html.lower() or "datadome" in html.lower():
                return jsonify({"error": "Website anti-bot protection blocked the background fetch."}), 403
            return jsonify({"html": html}), 200
    except urllib.error.HTTPError as he:
        return jsonify({"error": f"HTTP {he.code}: {he.reason}"}), 403 if he.code in [401, 403] else 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting ClauseGuard Dashboard...")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(host='127.0.0.1', port=5000, debug=True)
