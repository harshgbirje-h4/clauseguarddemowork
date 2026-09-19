import json
import sqlite3
import os

class EntityCanonicalizer:
    def __init__(self):
        # A small explicit canonical mapping for demo purposes.
        self.mapping = {
            "location data": "Location",
            "location information": "Location",
            "user location": "Location",
            "location": "Location",
            
            "ip address": "IP Address",
            "ip": "IP Address",
            "internet protocol address": "IP Address",
            
            "email address": "Email",
            "email": "Email"
        }

    def canonicalize(self, raw_entity):
        """
        Normalize and map raw entity to canonical entity.
        """
        # Trim whitespace and convert to lowercase for matching
        normalized_input = " ".join(raw_entity.split()).strip().lower()
        
        # Check explicit mapping
        if normalized_input in self.mapping:
            return self.mapping[normalized_input]
            
        # If unknown, create a deterministic human-readable canonical form (Title Case)
        return " ".join(raw_entity.split()).strip().title()


class DatabaseLoader:
    def __init__(self, db_path):
        self.db_path = db_path

    def load_extraction(self, extraction_data, canonicalizer):
        """
        Idempotent load of extraction JSON into SQLite database.
        """
        service_name = extraction_data.get("service_name")
        category = extraction_data.get("category")
        clauses = extraction_data.get("clauses", [])

        if not service_name:
            raise ValueError("Missing service_name in extraction data")

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        try:
            # 1. Insert or get Service
            cursor.execute("INSERT OR IGNORE INTO services (name, category) VALUES (?, ?)", (service_name, category))
            cursor.execute("SELECT id FROM services WHERE name = ?", (service_name,))
            service_row = cursor.fetchone()
            if not service_row:
                raise RuntimeError("Failed to retrieve service_id")
            service_id = service_row[0]

            # 2. Process Clauses
            for clause in clauses:
                text = clause.get("text")
                severity = clause.get("severity_score")
                specificity = clause.get("specificity_score")
                risk_category = clause.get("risk_category")
                raw_entities = clause.get("entities", [])

                if not text:
                    continue

                # Idempotency check for clause (prevent duplicate clauses for same service)
                cursor.execute("""
                    SELECT id FROM clauses 
                    WHERE service_id = ? AND text = ?
                """, (service_id, text))
                clause_row = cursor.fetchone()

                if not clause_row:
                    cursor.execute("""
                        INSERT INTO clauses (service_id, text, severity_score, specificity_score, risk_category)
                        VALUES (?, ?, ?, ?, ?)
                    """, (service_id, text, severity, specificity, risk_category))
                    clause_id = cursor.lastrowid
                else:
                    clause_id = clause_row[0]

                # 3. Canonicalize and Insert Entities + Mapping
                for raw_entity in raw_entities:
                    canon_name = canonicalizer.canonicalize(raw_entity)
                    
                    # Insert or get Canonical Entity
                    cursor.execute("INSERT OR IGNORE INTO canonical_entities (name) VALUES (?)", (canon_name,))
                    cursor.execute("SELECT id FROM canonical_entities WHERE name = ?", (canon_name,))
                    entity_row = cursor.fetchone()
                    if not entity_row:
                        raise RuntimeError("Failed to retrieve entity_id")
                    entity_id = entity_row[0]

                    # Insert mapping
                    cursor.execute("""
                        INSERT OR IGNORE INTO clause_entity_mapping (clause_id, entity_id)
                        VALUES (?, ?)
                    """, (clause_id, entity_id))
                    
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

def process_canonicalization(input_json_path, db_path):
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    canonicalizer = EntityCanonicalizer()
    loader = DatabaseLoader(db_path)
    loader.load_extraction(data, canonicalizer)
    
    print(f"Canonicalization and DB loading complete for {input_json_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Canonicalize entities and load to DB.")
    parser.add_argument("input_json", help="Path to extracted JSON file")
    
    args = parser.parse_args()
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    db_file_path = os.path.join(base_dir, 'data', 'db', 'portfolio.db')
    
    process_canonicalization(args.input_json, db_file_path)
