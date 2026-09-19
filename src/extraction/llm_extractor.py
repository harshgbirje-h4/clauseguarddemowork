import os
import json
import urllib.request
import urllib.error

class LLMExtractor:
    def __init__(self, service_name, category=None):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.service_name = service_name
        self.category = category

    def extract(self, candidate_clauses):
        """
        Sends candidate clauses to the LLM (or mock) and returns structured JSON.
        """
        if not candidate_clauses:
            return self._build_empty_response()
            
        if self.api_key:
            return self._call_real_llm(candidate_clauses)
        else:
            return self._call_mock_llm(candidate_clauses)

    def _build_empty_response(self):
        return {
            "service_name": self.service_name,
            "category": self.category or "Unknown",
            "clauses": []
        }

    def _call_mock_llm(self, candidate_clauses):
        """
        Deterministic mock mode for local verification.
        """
        extracted_clauses = []
        for i, text in enumerate(candidate_clauses):
            # Deterministic dummy scoring and entity extraction
            severity = 3.0 + (i % 3)
            specificity = 2.0 + (i % 2)
            
            # Simple keyword-based mock entity detection
            entities = []
            lower_text = text.lower()
            if "location" in lower_text: entities.append("Location Data")
            if "cookie" in lower_text: entities.append("Cookies")
            if "ip" in lower_text: entities.append("IP Address")
            if not entities: entities.append("General Data")
            
            extracted_clauses.append({
                "text": text,
                "entities": entities,
                "severity_score": float(severity),
                "specificity_score": float(specificity),
                "risk_category": "Mock Category"
            })
            
        return {
            "service_name": self.service_name,
            "category": self.category or "Unknown",
            "clauses": extracted_clauses
        }

    def _call_real_llm(self, candidate_clauses):
        """
        Real LLM implementation (e.g. OpenAI).
        """
        # We would implement the HTTP call to OpenAI here.
        # To avoid adding external dependencies for now, we use standard library urllib.
        # This assumes a working API key and structure.
        
        system_prompt = (
            "Extract privacy entities, severity (1-5), specificity (1-5), and a risk category "
            "for each clause. Return strict JSON matching the schema."
        )
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(candidate_clauses)}
            ]
        }
        
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                # In a real implementation, we would parse the result message.
                # For this stage, we assume the prompt engineering ensures correct JSON output.
                # This is a stub for the actual parsing logic.
                content = result['choices'][0]['message']['content']
                parsed_content = json.loads(content)
                # Ensure top level fields exist
                parsed_content["service_name"] = self.service_name
                if self.category:
                    parsed_content["category"] = self.category
                return parsed_content
        except Exception as e:
            raise RuntimeError(f"LLM API call failed: {e}")
