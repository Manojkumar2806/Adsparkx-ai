import json
import time
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.config import Config
from src.logger import setup_logger
from src.exceptions import LLMCallError

logger = setup_logger("escalator")

class HandoffReport(BaseModel):
    persona: str = Field(description="The customer's classified persona")
    detected_issue: str = Field(description="A concise, 1-sentence summary of the core issue reported by the customer")
    retrieved_sources: list[str] = Field(description="List of documentation files retrieved by the RAG search, if any")
    confidence_score: float = Field(description="The maximum semantic similarity score from RAG retrieval")
    consecutive_frustration_count: int = Field(description="The number of consecutive times this user has shown frustration")
    recommended_action: str = Field(description="A specific, actionable instruction for the human agent on how to resolve this specific issue")

class EscalationManager:
    def __init__(self):
        Config.validate()
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model = Config.GENERATIVE_MODEL
        self.confidence_threshold = Config.CONFIDENCE_THRESHOLD

    def evaluate(self, 
                 query: str, 
                 persona_info: dict, 
                 context_chunks: list, 
                 consecutive_frustration: int) -> dict:
        """
        Evaluates the escalation triggers and returns a dict with escalation status.
        persona_info should contain: 'persona', 'is_sensitive', 'sentiment', 'reasoning'
        """
        logger.info("Evaluating escalation triggers...")

        # Extract classification info
        persona = persona_info.get("persona", "Business Executive")
        is_sensitive = persona_info.get("is_sensitive", False)
        sentiment = persona_info.get("sentiment", "Neutral")
        
        # Calculate best retrieval score
        best_score = 0.0
        retrieved_sources = []
        if context_chunks:
            best_score = max([chunk["score"] for chunk in context_chunks])
            # Keep unique sources
            retrieved_sources = list(set([chunk["source"] for chunk in context_chunks]))

        # Escalation criteria flags
        low_confidence = best_score < self.confidence_threshold or len(context_chunks) == 0
        repeated_frustration = consecutive_frustration >= Config.CONSECUTIVE_FRUSTRATION_LIMIT

        logger.info(
            f"Escalation details: Is Sensitive={is_sensitive}, Best Score={best_score:.4f} (Threshold={self.confidence_threshold}), "
            f"Consecutive Frustration={consecutive_frustration} (Limit={Config.CONSECUTIVE_FRUSTRATION_LIMIT})"
        )

        # Decide whether to escalate
        should_escalate = is_sensitive or low_confidence or repeated_frustration
        
        if not should_escalate:
            logger.info("Escalation NOT triggered.")
            return {
                "escalated": False,
                "reason": None,
                "handoff_summary": None
            }

        # Determine escalation reason
        reasons = []
        if is_sensitive:
            reasons.append("Sensitive billing, refund, security, or account modification request detected.")
        if low_confidence:
            reasons.append(f"Low retrieval confidence (Best Score = {best_score:.4f} < {self.confidence_threshold}) or no matching documentation.")
        if repeated_frustration:
            reasons.append(f"Repeated customer frustration detected (Consecutive turns = {consecutive_frustration}).")
        
        primary_reason = " | ".join(reasons)
        logger.warning(f"ESCALATION TRIGGERED: {primary_reason}")

        # Generate structured handoff JSON using Gemini
        try:
            handoff_data = self._generate_structured_handoff(
                query=query,
                persona=persona,
                retrieved_sources=retrieved_sources,
                confidence_score=best_score,
                consecutive_frustration=consecutive_frustration
            )
            return {
                "escalated": True,
                "reason": primary_reason,
                "handoff_summary": handoff_data
            }
        except Exception as e:
            logger.error(f"Failed to generate dynamic handoff JSON: {e}. Falling back to static handoff.")
            # Fallback static JSON structure
            fallback_data = {
                "persona": persona,
                "detected_issue": query[:100] + ("..." if len(query) > 100 else ""),
                "retrieved_sources": retrieved_sources,
                "confidence_score": best_score,
                "consecutive_frustration_count": consecutive_frustration,
                "recommended_action": "Manually review the user support history and assist directly. Check error logs and verify billing logs if applicable."
            }
            return {
                "escalated": True,
                "reason": primary_reason,
                "handoff_summary": fallback_data
            }

    def _generate_structured_handoff(self, 
                                     query: str, 
                                     persona: str, 
                                     retrieved_sources: list, 
                                     confidence_score: float, 
                                     consecutive_frustration: int) -> dict:
        """
        Uses Gemini structured output to generate a high-quality handoff report.
        """
        system_instruction = (
            "You are a Support Handoff Specialist. Your task is to compile a highly structured, professional "
            "handoff report for a human agent. The report must summarize the user's issue, list document sources "
            "retrieved (if any), state the system confidence, and suggest a specific, step-by-step recommended action "
            "that the human agent should follow based on the user's request."
        )

        prompt = (
            f"User support query: '{query}'\n"
            f"Customer Persona: {persona}\n"
            f"RAG Retrieved Sources: {retrieved_sources}\n"
            f"Best Similarity Score: {confidence_score:.4f}\n"
            f"Consecutive Frustration Count: {consecutive_frustration}\n"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=HandoffReport,
                temperature=0.2
            )
        )
        
        result: HandoffReport = response.parsed
        return result.model_dump()

if __name__ == "__main__":
    # Test execution
    manager = EscalationManager()
    persona_info = {
        "persona": "Frustrated User",
        "is_sensitive": True,
        "sentiment": "Negative",
        "reasoning": "User demands immediate refund"
    }
    context = [{"text": "Refund details", "source": "refund_policy.txt", "score": 0.38}]
    
    report = manager.evaluate(
        query="My billing statement has unexpected duplicate charges. I demand an immediate refund!",
        persona_info=persona_info,
        context_chunks=context,
        consecutive_frustration=1
    )
    print(json.dumps(report, indent=2))
