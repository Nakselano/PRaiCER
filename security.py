import re
import json
from typing import Optional


class SecurityGuard:
    def __init__(self):
        self.secret_patterns = [
            r"AIza[0-9A-Za-z-_]{35}",  # Google API Key
            r"gsk-[a-zA-Z0-9]{48}",  # OpenAI/Groq Key patterns
            r"postgres:\/\/[^@]+@\S+",  # Connection strings
        ]

        self.forbidden_phrases = [
            "Jesteś Inteligentnym Asystentem Zakupowym",
            "SCENARIUSZ 1",
            "SCENARIUSZ 2",
            "ignore previous instructions",
            "system prompt"
        ]

    def sanitize_output(self, text: str) -> str:
        cleaned_text = text
        for pattern in self.secret_patterns:
            cleaned_text = re.sub(pattern, "[REDACTED_SECRET]", cleaned_text)
        return cleaned_text

    def check_prompt_leakage(self, text: str) -> bool:
        text_lower = text.lower()
        for phrase in self.forbidden_phrases:
            if phrase.lower() in text_lower:
                return True
        return False

    def validate_json_only(self, text: str) -> Optional[dict]:
        pattern = r"```(?:json)?\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        candidate = match.group(1) if match else text.strip()

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    def check_path_traversal(self, text: str) -> bool:
        dangerous_patterns = [r"\.\./", r"\.\.\\", r"/etc/", r"C:\\Windows"]
        for pattern in dangerous_patterns:
            if re.search(pattern, text):
                return True
        return False

guard = SecurityGuard()