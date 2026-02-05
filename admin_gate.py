# JusticeVault/admin_gate.py
import hashlib
import json

class LegalGate:
    def __init__(self):
        self.staging_area = [] # Holds unapproved Gazette items
        self.approved_index = "approved_metadata.json"

    def review_item(self, text, metadata):
        # Generate a fingerprint for the Gazette item
        fingerprint = hashlib.sha256(text.encode()).hexdigest()
        
        # Add to staging
        item = {
            "fingerprint": fingerprint,
            "text": text,
            "metadata": metadata,
            "status": "PENDING_REVIEW"
        }
        return item

    def approve_item(self, item, admin_id):
        item["status"] = "APPROVED"
        item["approver"] = admin_id
        # This hash acts as the 'Immutable Proof' the client wants
        return item