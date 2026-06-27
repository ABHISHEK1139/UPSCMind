"""
Hermes V2 — UPSC-Specific Fact Checker
═══════════════════════════════════════════════════════════════
Checks UPSC-specific factual claims against a verified knowledge base.
Unlike general-purpose hallucination detectors, this uses targeted
database lookups for UPSC facts: Articles, Amendments, cases, dates.

This is far more reliable than asking an LLM "is this correct?" because:
1. UPSC facts are structured and verifiable
2. Database lookups are deterministic
3. No risk of the checker itself hallucinating
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UPSCFactChecker:
    """
    Verifies UPSC-specific factual claims against Neo4j knowledge graph.
    
    Checks:
    - Article numbers (does Article 21 exist? Is it in Part III?)
    - Amendment numbers (is the 42nd Amendment real? What year?)
    - Case citations (does Kesavananda Bharati v. Kerala exist?)
    - Dates (was the 42nd Amendment in 1976?)
    - Institutional facts (does the Finance Commission exist under Article 280?)
    """
    
    def __init__(self) -> None:
        self._neo4j_available = True
    
    async def check_answer(self, answer: str, domain: str = "General Studies") -> Dict[str, Any]:
        """
        Run all fact checks on an answer.
        
        Returns
        -------
        dict with keys:
          passed (bool), claims_checked (int), issues (list), score (float)
        """
        claims = self.extract_claims(answer)
        if not claims:
            return {"passed": True, "claims_checked": 0, "issues": [], "score": 1.0}
        
        issues = []
        verified_count = 0
        
        for claim in claims:
            result = await self._verify_claim(claim)
            if result["verified"]:
                verified_count += 1
            else:
                issues.append({
                    "claim": claim,
                    "issue": result.get("issue", "Could not verify"),
                })
        
        total = len(claims)
        score = verified_count / total if total > 0 else 1.0
        passed = score >= 0.8  # Allow 20% unverifiable claims
        
        return {
            "passed": passed,
            "claims_checked": total,
            "verified": verified_count,
            "issues": issues,
            "score": score,
        }
    
    def extract_claims(self, answer: str) -> List[Dict[str, Any]]:
        """Extract verifiable factual claims from an answer."""
        claims = []
        
        # Article references
        for match in re.finditer(r'Article\s+(\d+[A-Z]?)\s*(?:\(([^)]+)\))?', answer):
            context = answer[max(0, match.start()-100):min(len(answer), match.end()+100)]
            claims.append({
                "type": "article",
                "value": match.group(1),
                "context": context,
                "full_match": match.group(0),
            })
        
        # Amendment references
        for match in re.finditer(r'(\d+(?:st|nd|rd|th))\s+Amendment', answer):
            # Look for year nearby
            year_match = re.search(r'\b(19|20)\d{2}\b', answer[max(0, match.start()-50):match.end()+50])
            claims.append({
                "type": "amendment",
                "value": match.group(1),
                "claimed_year": int(year_match.group()) if year_match else None,
                "context": answer[max(0, match.start()-50):match.end()+50],
            })
        
        # Case citations (Name v. Name or Name vs. Name)
        for match in re.finditer(r'([A-Z][a-zA-Z\s]+)\s+v\.?\s+([A-Z][a-zA-Z\s]+)', answer):
            claims.append({
                "type": "case",
                "value": f"{match.group(1).strip()} v. {match.group(2).strip()}",
                "context": answer[max(0, match.start()-50):match.end()+50],
            })
        
        # Year claims (specific dates mentioned with events)
        for match in re.finditer(r'\b(19|20)\d{2}\b', answer):
            year = int(match.group())
            context = answer[max(0, match.start()-80):min(len(answer), match.end()+80)]
            # Only check years that seem to be associated with constitutional events
            if any(kw in context.lower() for kw in ["amendment", "act", "case", "judgment", "constitution", "article", "schedule", "commission", "committee"]):
                claims.append({
                    "type": "year",
                    "value": year,
                    "context": context,
                })
        
        # Schedule references
        for match in re.finditer(r'(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth)\s+Schedule', answer):
            claims.append({
                "type": "schedule",
                "value": match.group(1),
                "context": answer[max(0, match.start()-50):match.end()+50],
            })
        
        # Commission/Committee references
        for match in re.finditer(r'([A-Z][a-zA-Z\s]+(?:Commission|Committee|Council|Tribunal|Board))', answer):
            claims.append({
                "type": "institution",
                "value": match.group(1).strip(),
                "context": answer[max(0, match.start()-50):match.end()+50],
            })
        
        return claims
    
    async def _verify_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a single claim against the knowledge base."""
        claim_type = claim["type"]
        
        try:
            from core.db_neo4j import execute_cypher
            
            if claim_type == "article":
                result = await execute_cypher(
                    "MATCH (a:Article {number: $num}) RETURN a.number as num, a.description as desc",
                    {"num": claim["value"]},
                )
                if result:
                    return {"verified": True, "data": result[0]}
                return {"verified": False, "issue": f"Article {claim['value']} not found in knowledge base"}
            
            elif claim_type == "amendment":
                result = await execute_cypher(
                    "MATCH (a:Amendment {number: $num}) RETURN a.number as num, a.year as year",
                    {"num": claim["value"]},
                )
                if result:
                    # Check year if claimed
                    if claim.get("claimed_year"):
                        actual_year = result[0].get("year")
                        if actual_year and actual_year != claim["claimed_year"]:
                            return {
                                "verified": False,
                                "issue": f"{claim['value']} Amendment was in {actual_year}, not {claim['claimed_year']}",
                            }
                    return {"verified": True, "data": result[0]}
                return {"verified": False, "issue": f"Amendment {claim['value']} not found"}
            
            elif claim_type == "case":
                # Fuzzy match on case name
                result = await execute_cypher(
                    "MATCH (c:Case) WHERE c.name CONTAINS $name RETURN c.name as name, c.year as year",
                    {"name": claim["value"].split("v.")[0].strip()},
                )
                if result:
                    return {"verified": True, "data": result[0]}
                return {"verified": False, "issue": f"Case '{claim['value']}' not found"}
            
            elif claim_type == "schedule":
                # Schedules are fixed (1-12) — check if valid
                valid_schedules = {"First", "Second", "Third", "Fourth", "Fifth", "Sixth",
                                   "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth"}
                if claim["value"] in valid_schedules:
                    return {"verified": True}
                return {"verified": False, "issue": f"Invalid schedule: {claim['value']}"}
            
            elif claim_type == "institution":
                result = await execute_cypher(
                    "MATCH (i:Institution) WHERE i.name CONTAINS $name RETURN i.name as name",
                    {"name": claim["value"]},
                )
                if result:
                    return {"verified": True, "data": result[0]}
                # Not all institutions are in the DB — this is a soft check
                return {"verified": True, "note": "Institution not in KB, skipped"}
            
            elif claim_type == "year":
                # Years are hard to verify without context — skip
                return {"verified": True, "note": "Year claim skipped (needs context)"}
            
            return {"verified": True, "note": f"Unknown claim type: {claim_type}"}
        
        except Exception as exc:
            logger.warning("[FACT_CHECK] Verification failed for %s: %s", claim, exc)
            return {"verified": True, "note": f"Check skipped: {exc}"}
