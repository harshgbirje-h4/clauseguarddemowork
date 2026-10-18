import json
import re
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
            "geolocation": "Location",
            "gps location": "Location",
            "gps": "Location",
            "precise location": "Precise Location",
            "exact location": "Precise Location",
            "precise location data": "Precise Location",
            
            "ip address": "IP Address",
            "ip": "IP Address",
            "internet protocol address": "IP Address",
            "internet protocol": "IP Address",
            "ip addresses": "IP Address",
            
            "email address": "Email",
            "e-mail address": "Email",
            "e-mail": "Email",
            "email": "Email",
            
            "phone number": "Phone Number",
            "phone": "Phone Number",
            "telephone number": "Phone Number",
            "telephone": "Phone Number",
            "mobile number": "Phone Number",
            "mobile": "Phone Number",
            
            "device information": "Device Information",
            "device": "Device Information",
            "device id": "Device Information",
            "hardware model": "Device Information",
            "mac address": "Device Information",
            "operating system": "Device Information",
            "os": "Device Information",
            
            "browser information": "Browser Information",
            "browser": "Browser Information",
            "browser type": "Browser Information",
            "user agent": "Browser Information",
            
            "cookie": "Cookies",
            "cookies": "Cookies",
            "web beacon": "Cookies",
            "web beacons": "Cookies",
            "pixel tag": "Cookies",
            "pixel tags": "Cookies",
            
            "usage data": "Usage Data",
            "log data": "Usage Data",
            "interaction": "Usage Data",
            "interactions": "Usage Data",
            "click": "Usage Data",
            "clicks": "Usage Data",
            "page view": "Usage Data",
            "page views": "Usage Data",
            
            "identifier": "Identifiers",
            "identifiers": "Identifiers",
            "unique identifier": "Identifiers",
            "unique identifiers": "Identifiers",
            "id": "Identifiers",
            
            "account information": "Account Information",
            "account": "Account Information",
            "password": "Account Information",
            "username": "Account Information",
            "profile": "Account Information",
            
            "payment information": "Payment Information",
            "payment": "Payment Information",
            "credit card": "Payment Information",
            "billing": "Payment Information",
            "financial information": "Payment Information",
            
            "contact information": "Contact Information",
            "contact": "Contact Information",
            "address": "Contact Information",
            "postal": "Contact Information",
            "postal address": "Contact Information",
            
            "biometric data": "Biometric Data",
            "biometric": "Biometric Data",
            "face": "Biometric Data",
            "fingerprint": "Biometric Data",
            "voiceprint": "Biometric Data",
            
            "advertising data": "Advertising Data",
            "advertising": "Advertising Data",
            "marketing": "Advertising Data",
            "ad": "Advertising Data",
            "ads": "Advertising Data",
            
            "analytics data": "Analytics Data",
            "analytics": "Analytics Data",
            "measure": "Analytics Data",
            "measurement": "Analytics Data",
            "performance": "Analytics Data",
            
            "communications": "Communications",
            "communication": "Communications",
            "message": "Communications",
            "messages": "Communications",
            "chat": "Communications",
            "chats": "Communications",
            "correspondence": "Communications",
            
            "name": "Name",
            "first name": "Name",
            "last name": "Name",
            "full name": "Name",
            
            "general data": "General Data",

            # Added after reviewing real policy phrasing (see data/evaluation/entity_phrases.json)
            "precise geolocation": "Precise Location",
            "exact geolocation": "Precise Location",
            "browsing history": "Usage Data",
            "search history": "Usage Data",
            "browsing data": "Usage Data",
            "payment card": "Payment Information",
            "payment card details": "Payment Information",
            "card details": "Payment Information",
            "biometric identifiers": "Biometric Data",
            "biometric information": "Biometric Data",
            "email addresses": "Email",
        }

    # Leading words that do not change the meaning of a data type
    _LEADING_WORDS = ("your ", "our ", "the ", "any ", "my ", "their ", "his ", "her ", "its ", "a ", "an ", "all ")

    @classmethod
    def _variants(cls, raw_entity):
        """
        Candidate spellings of one raw phrase, most specific first:
        lowercased, punctuation stripped, possessive/article prefix removed,
        and simple singular forms (addresses -> address, cookies -> cookie).
        """
        text = re.sub(r"[^a-z0-9\- ]", " ", raw_entity.lower())
        text = " ".join(text.split())
        variants = [text]
        for prefix in cls._LEADING_WORDS:
            if text.startswith(prefix):
                variants.append(text[len(prefix):])
        base = list(dict.fromkeys(variants))
        for v in base:
            if v.endswith("ies") and len(v) > 4:
                variants.append(v[:-3] + "y")
            elif v.endswith("es") and len(v) > 3:
                variants.append(v[:-2])
            if v.endswith("s") and not v.endswith("ss") and len(v) > 3:
                variants.append(v[:-1])
        return list(dict.fromkeys(variants))

    def resolve_detail(self, raw_entity):
        """
        Return a dict describing how a raw phrase was handled:

          canonical   'Unknown: <original>' unless the phrase is an exact or variant match
          is_known    True only for exact/variant matches
          match_kind  'exact' | 'suggested' | 'none'
          suggestion  for 'suggested': the category a known term appears to point to

        Partial (whole-word) matches are NEVER used as classifications. For example
        'Browser Fingerprint' contains 'fingerprint', but browser fingerprinting is not
        biometric data, so the phrase stays unknown and the category is only offered
        as a suggestion for a human reviewer.
        """
        unknown = f"Unknown: {raw_entity.strip()}" if raw_entity and raw_entity.strip() else None
        if not raw_entity or not raw_entity.strip():
            return {"canonical": None, "is_known": False, "match_kind": "none", "suggestion": None}

        variants = self._variants(raw_entity)
        for candidate in variants:
            if candidate in self.mapping:
                return {"canonical": self.mapping[candidate], "is_known": True,
                        "match_kind": "exact", "suggestion": None}

        suggestion = None
        for term in sorted(self.mapping, key=len, reverse=True):
            if len(term) < 3:
                continue  # short keys such as 'id' or 'os' match too easily inside words
            if re.search(r"\b" + re.escape(term) + r"\b", variants[0]):
                suggestion = self.mapping[term]
                break

        return {"canonical": unknown, "is_known": False,
                "match_kind": "suggested" if suggestion else "none",
                "suggestion": suggestion}

    def resolve(self, raw_entity):
        """Return (canonical_name, is_known)."""
        detail = self.resolve_detail(raw_entity)
        return detail["canonical"], detail["is_known"]

    def canonicalize(self, raw_entity):
        """
        Normalize and map raw entity to canonical entity.
        """
        canonical, _ = self.resolve(raw_entity)
        return canonical

    def is_known(self, raw_entity):
        _, known = self.resolve(raw_entity)
        return known


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

            # Clear existing clauses for this service to ensure idempotence
            cursor.execute("DELETE FROM clauses WHERE service_id = ?", (service_id,))

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
                    if not canon_name:
                        continue
                    
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
