import sqlite3

try:
    from risk import clause_risk_0_100, TOP_K
except ImportError:  # when imported as src.scoring
    from src.risk import clause_risk_0_100, TOP_K

class ScoringEngine:
    def __init__(self, w1=1.0, w2=1.0):
        # Default weights. Plan states uniform starting assumption.
        self.w1 = w1
        self.w2 = w2

    def calculate_clause_score(self, severity, specificity):
        """
        Calculates the deterministic risk score for a single clause.
        Formula: (w1 * severity) + (w2 * specificity)
        """
        sev = float(severity) if severity is not None else 0.0
        spec = float(specificity) if specificity is not None else 0.0
        return (self.w1 * sev) + (self.w2 * spec)

    def calculate_service_score_from_clauses(self, clauses):
        """
        Calculates the risk score for a service by aggregating its clauses.
        Assumption: Sum aggregation (as the Mean vs Sum decision is explicitly deferred to Phase 2).
        """
        return sum(self.calculate_clause_score(c['severity_score'], c['specificity_score']) for c in clauses)

    def get_portfolio_data(self, db_path, exclude_service_name=None):
        """
        Extracts the portfolio structure and calculates baseline risk.
        Returns a structured dictionary of the portfolio.
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all services
        cursor.execute("SELECT id, name FROM services")
        services = cursor.fetchall()
        
        portfolio_score = 0.0
        service_details = []
        portfolio_entities = set()
        
        for service_id, service_name in services:
            if exclude_service_name and service_name == exclude_service_name:
                continue
                
            # Get clauses for service
            cursor.execute("SELECT id, severity_score, specificity_score FROM clauses WHERE service_id = ?", (service_id,))
            clauses = cursor.fetchall()
            
            clause_dicts = [{'severity_score': c[1], 'specificity_score': c[2]} for c in clauses]
            svc_score = self.calculate_service_score_from_clauses(clause_dicts)
            portfolio_score += svc_score
            
            # Get entities for service
            cursor.execute("""
                SELECT ce.name 
                FROM canonical_entities ce
                JOIN clause_entity_mapping cem ON ce.id = cem.entity_id
                JOIN clauses c ON cem.clause_id = c.id
                WHERE c.service_id = ?
            """, (service_id,))
            entities = {row[0] for row in cursor.fetchall()}
            portfolio_entities.update(entities)
            
            service_details.append({
                "service_name": service_name,
                "service_score": svc_score,
                "entities": list(entities)
            })
            
        conn.close()
        
        return {
            "portfolio_score": portfolio_score,
            "services": service_details,
            "all_canonical_entities": list(portfolio_entities)
        }

    def get_exposure_by_data_type(self, db_path, exclude_service_name=None):
        """
        Portfolio view that counts each data type ONCE.

        The additive portfolio_score counts a data type again for every service
        that collects it (two services that both take email count email twice).
        Here each canonical data type is scored once, at the risk of the worst
        clause that touches it, and the services that share it are listed.

        portfolio_risk_0_100 is the mean of the TOP_K highest data-type risks,
        using the same aggregation as a single policy.
        """
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ce.name, s.name, c.severity_score, c.specificity_score, c.text
                FROM clause_entity_mapping cem
                JOIN canonical_entities ce ON ce.id = cem.entity_id
                JOIN clauses c ON c.id = cem.clause_id
                JOIN services s ON s.id = c.service_id
            """)
            rows = cursor.fetchall()
        finally:
            conn.close()

        exposure = {}
        for entity, service, sev, spec, text in rows:
            if exclude_service_name and service == exclude_service_name:
                continue
            risk = clause_risk_0_100(sev, spec)
            item = exposure.setdefault(entity, {"risk_0_100": 0.0, "services": {}, "worst_clause": None})
            if risk > item["risk_0_100"] or item["worst_clause"] is None:
                item["risk_0_100"] = risk
                item["worst_clause"] = (text or "")[:200]
            item["services"][service] = max(item["services"].get(service, 0.0), risk)

        ranked = sorted(exposure.items(), key=lambda kv: kv[1]["risk_0_100"], reverse=True)
        top = [item["risk_0_100"] for _, item in ranked[:TOP_K]]
        portfolio_risk = round(sum(top) / len(top), 1) if top else 0.0

        return {
            "portfolio_risk_0_100": portfolio_risk,
            "exposure_by_data_type": {
                entity: {
                    "risk_0_100": round(item["risk_0_100"], 1),
                    "services": sorted(item["services"], key=item["services"].get, reverse=True),
                    "worst_clause": item["worst_clause"],
                }
                for entity, item in ranked
            },
        }

