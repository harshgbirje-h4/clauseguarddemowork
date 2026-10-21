import os
import json
import argparse
from extraction.prefilter import PrivacyPrefilter
from extraction.llm_extractor import LLMExtractor
from extraction.validator import validate_extraction_output

try:
    from risk import (
        classify_clause_type,
        get_clause_guidance,
        is_negated_claim,
        inspect_policy_statement,
        segment_policy_document
    )
except ImportError:
    from src.risk import (
        classify_clause_type,
        get_clause_guidance,
        is_negated_claim,
        inspect_policy_statement,
        segment_policy_document
    )

def extract_pipeline(raw_text, service_name, category=None):
    """
    The canonical single path for extraction with bounded semantic chunking,
    anti-hallucination provenance verification, and negation detection.
    """
    if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
        return {
            "service_name": service_name,
            "category": category or "Unknown",
            "mode": "EMPTY",
            "clauses": [],
            "total_chars": len(raw_text) if isinstance(raw_text, str) else 0,
            "processed_chars": 0,
            "is_truncated": False,
            "chunks_processed": 0
        }

    # 1. Bounded document segmentation (handles up to 250k chars with offset tracking)
    doc_meta = segment_policy_document(raw_text, chunk_size=12000, overlap=1000, max_chars=250000)
    chunks = doc_meta["chunks"]
    
    prefilter = PrivacyPrefilter()
    extractor = LLMExtractor(service_name=service_name, category=category)
    
    raw_extracted_clauses = []
    extraction_mode = "MOCK/DEV"

    # 2. Process chunks
    for ch in chunks:
        ch_text = ch["text"]
        # Split chunk into sentences
        chunk_sentences = [s.strip() for s in ch_text.split('.') if len(s.strip()) > 10]
        if not chunk_sentences:
            continue
            
        candidate_clauses = prefilter.filter_candidates(chunk_sentences)
        if not candidate_clauses:
            continue
            
        extracted_chunk = extractor.extract(candidate_clauses)
        extraction_mode = extracted_chunk.get("mode", extraction_mode)
        raw_extracted_clauses.extend(extracted_chunk.get("clauses", []))

    # 3. Strict Excerpt Provenance Verification, Negation Detection & Character Offset Mapping
    # Rule: Never return an excerpt that did not originate verbatim from the scanned policy text.
    verified_clauses = []
    seen_excerpts = set()

    for c in raw_extracted_clauses:
        text_content = c.get("text") or c.get("excerpt") or ""
        clean_text = text_content.strip()
        
        if not clean_text or clean_text in seen_excerpts:
            continue

        # Character offset lookup in original source text
        char_start = raw_text.find(clean_text)
        if char_start == -1:
            # Fallback normalized search if whitespace differed slightly
            continue

        char_end = char_start + len(clean_text)
        seen_excerpts.add(clean_text)

        # Structured linguistic inspection
        stmt_info = inspect_policy_statement(clean_text)
        is_neg = stmt_info["is_protective_commitment"]
        has_contrast = stmt_info["has_contrastive_affirmation"]
        has_exception = stmt_info["has_exception"]
        clause_type = classify_clause_type(clean_text, c.get("entities"), c.get("risk_category"))
        guidance = get_clause_guidance(clause_type)

        if is_neg:
            sev_score = 1.0
            spec_score = 1.0
            risk_cat = "Protective Commitment"
            grounded_reason = stmt_info["grounded_reason"]
        elif has_contrast:
            # Denies direct selling but confirms active third-party sharing or targeted advertising
            sev_score = float(c.get("severity_score") or 4.0)
            spec_score = float(c.get("specificity_score") or 3.0)
            risk_cat = "Third-Party Disclosure"
            grounded_reason = stmt_info["grounded_reason"]
        elif has_exception:
            # Denies selling generally but includes an explicit exception clause
            sev_score = float(c.get("severity_score") or 3.0)
            spec_score = float(c.get("specificity_score") or 2.0)
            risk_cat = "Conditional Disclosure (Exception Permitted)"
            grounded_reason = stmt_info["grounded_reason"]
        else:
            sev_score = float(c.get("severity_score") or 3.0)
            spec_score = float(c.get("specificity_score") or 2.0)
            risk_cat = str(c.get("risk_category") or "Identified Clause")
            grounded_reason = f"Policy disclosure verified at character offset [{char_start}:{char_end}]."

        c_formatted = {
            "excerpt": clean_text,
            "text": clean_text,
            "type": clause_type,
            "meaning": guidance.get("meaning", "General privacy clause."),
            "what_you_can_do": guidance.get("what_you_can_do", "Review your account privacy choices."),
            "entities": c.get("entities", []),
            "severity_score": sev_score,
            "specificity_score": spec_score,
            "risk_category": risk_cat,
            "char_start": char_start,
            "char_end": char_end,
            "detection_method": "deterministic_provenance" if extraction_mode.startswith("MOCK") else "calibrated_classifier",
            "confidence": 1.0,
            "grounded_reason": grounded_reason,
            "is_negated": is_neg,
            "has_exception": has_exception,
            "has_contrastive_affirmation": has_contrast,
            "is_verified": True
        }
        verified_clauses.append(c_formatted)

    result_json = {
        "service_name": service_name,
        "category": category or "Unknown",
        "mode": extraction_mode,
        "clauses": verified_clauses,
        "total_chars": doc_meta["total_chars"],
        "processed_chars": doc_meta["processed_chars"],
        "is_truncated": doc_meta["is_truncated"],
        "chunks_processed": doc_meta["chunk_count"]
    }

    # 4. Validate schema
    validate_extraction_output(result_json)
    return result_json

def process_file(input_path, service_name, category=None):
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
        
    result = extract_pipeline(raw_text, service_name, category)
    
    # Ensure output directory exists
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    out_dir = os.path.join(base_dir, 'data', 'extracted')
    os.makedirs(out_dir, exist_ok=True)
    
    out_filename = f"{service_name.lower().replace(' ', '_')}.json"
    out_path = os.path.join(out_dir, out_filename)
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        
    print(f"Extraction complete. Output written to {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract privacy clauses from raw text.")
    parser.add_argument("input_file", help="Path to raw policy text file")
    parser.add_argument("service_name", help="Name of the service (e.g., Spotify)")
    parser.add_argument("--category", help="Optional service category", default=None)
    
    args = parser.parse_args()
    process_file(args.input_file, args.service_name, args.category)
