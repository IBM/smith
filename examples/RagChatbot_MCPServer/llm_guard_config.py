import logging
from llm_guard import scan_prompt, scan_output
from llm_guard.input_scanners import (
    PromptInjection, 
    Secrets as InputSecrets, 
    Toxicity as InputToxicity,
    Anonymize,      # Masks PII (SSN, etc.) before the LLM sees it
    InvisibleText,  # Detects hidden Unicode/Zero-width character attacks
    Language,
    BanSubstrings   # For custom pattern blocking
)
from llm_guard.output_scanners import (
    Sensitive, 
    Toxicity as OutputToxicity,
    NoRefusal,
    Relevance,
    BanSubstrings as OutputBanSubstrings
)
from llm_guard.vault import Vault

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MCP-Guard")

class EnhancedLLMGuardWrapper:
    def __init__(self):
        # Initialize vault for anonymization
        self.vault = Vault()
        
        # 1. Input Scanners: Modern Intent-Based Detection
        self.input_scanners = [
            PromptInjection(threshold=0.3, match_type="full"),
            InvisibleText(),

            Anonymize(
                vault=self.vault,
                entity_types=["US_SSN", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", "PERSON", "LOCATION"],
                preamble="Sensitive information detected and anonymized: ",
                use_faker=True
            ),
            

            BanSubstrings(
                substrings=[
                    "ssn", "social security", "social security number",
                    "home address", "bank account", "personal email",
                    "healthcare plan", "emergency contact",
                    "show all", "bypass", "ignore all", "override all",
                    "admin access", "unlimited access", "show passwords",
                    "reveal secrets", "dump database"
                ],
                match_type="word",
                case_sensitive=False,
                redact=True
            ),
            
            InputSecrets(),
            InputToxicity(threshold=0.8),
            Language(valid_languages=["en"], threshold=0.1)
        ]
        
        # 2. Output Scanners
        self.output_scanners = [
            Sensitive(
                redact=True,
                entity_types=["CREDIT_CARD", "SSN", "PHONE_NUMBER", "EMAIL_ADDRESS", "PERSON", "LOCATION"]
            ),
            OutputBanSubstrings(
                substrings=[
                    "123-45-6789", "234-56-7890",  # Example SSNs from database
                    "Oak Street", "Pine Avenue",    # Example addresses from database
                    "****1234", "****5678",         # Example bank accounts from database
                    "HC123456789", "HC234567890"    # Example healthcare IDs from database
                ],
                match_type="str",
                case_sensitive=False,
                redact=True
            ),
            OutputToxicity(threshold=0.7),
            Relevance(threshold=0.5),
            NoRefusal(threshold=0.5)
        ]

    def scan_incoming_prompt(self, text: str):
        """
        Maintains your original signature.
        Uses ML to detect injection and masks PII before processing.
        """
        try:
            sanitized_text, is_valid, risk_score = scan_prompt(
                self.input_scanners,
                text
            )
            
            if isinstance(is_valid, dict):
                overall_valid = all(is_valid.values())
            else:
                overall_valid = is_valid
            
            if not overall_valid:
                logger.warning(f"MCP Security: Input blocked. Risk: {risk_score}")
                return sanitized_text, False
            
            logger.debug(f"Input passed. Risk: {risk_score}")
            return sanitized_text, True
            
        except Exception as e:
            logger.error(f"Error in prompt scanning: {e}")
            return text, True

    def scan_tool_output(self, user_prompt: str, tool_result: str):
        """
        Maintains your original signature.
        Scans tool outputs for sensitive data leakage.
        """
        try:
            sanitized_text, is_valid, risk_score = scan_output(
                self.output_scanners,
                user_prompt,
                tool_result
            )
            
            if not is_valid:
                logger.warning(f"MCP Security: Sensitive data redacted from output.")
            
            return sanitized_text, is_valid
            
        except Exception as e:
            logger.error(f"Error in output scanning: {e}")
            return "Output blocked due to security scanning error.", False

# Global instance
guard = EnhancedLLMGuardWrapper()
