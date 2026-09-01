import logging
import json
import os

logger = logging.getLogger(__name__)

class SecurityRAGService:
    """
    RAG (Retrieval-Augmented Generation) Service for Security Context.
    Stores security playbooks, behavioral baselines, and zone protocols.
    """
    
    def __init__(self):
        self.knowledge_base = {
            "Intrusion Detection": "Restricted Area Protocol: Unauthorized personnel in red zones must be flagged immediately. Check for climbing or forced entry.",
            "People Fighting": "Conflict Protocol: Aggressive physical contact, rapid movements, and surrounding behavior indicate a fight. Deploy security to the location.",
            "Person Collapsing": "Medical Protocol: Horizontal body position for >10s indicates collapse. Alert medical team immediately.",
            "Unattended Object": "Bomb/Safety Protocol: Bags or boxes left alone for >30s in high-traffic areas are high risk. Evacuate if necessary.",
            "Zone Monitoring": "Standard Protocol: Monitor occupancy limits. Alert if count exceeds 10 people in restricted zones."
        }
        self._load_custom_protocols()

    def _load_custom_protocols(self):
        """Load site-specific protocols from data folder"""
        protocol_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/security_protocols.json"))
        if os.path.exists(protocol_path):
            try:
                with open(protocol_path, "r") as f:
                    custom = json.load(f)
                    self.knowledge_base.update(custom)
                logger.info(f"Loaded {len(custom)} custom security protocols")
            except Exception as e:
                logger.error(f"Failed to load protocols: {e}")

    def get_context(self, rule_name: str):
        """Retrieve relevant protocol/context for a rule"""
        return self.knowledge_base.get(rule_name, "Standard security monitoring protocol applies.")

# Global instance
security_rag = SecurityRAGService()
