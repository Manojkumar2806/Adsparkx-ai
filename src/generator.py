import random
import time
from google import genai
from google.genai import types

from src.config import Config
from src.logger import setup_logger
from src.exceptions import LLMCallError

logger = setup_logger("generator")

def call_gemini_with_backoff(func, *args, max_retries=5, **kwargs):
    """Executes a Gemini API call with exponential backoff and jitter."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Gemini API call failed after {max_retries} attempts: {e}")
                raise LLMCallError(f"Gemini API call failed: {e}") from e
            sleep_time = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"Gemini API error occurred: {e}. Retrying in {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)

class ResponseGenerator:
    def __init__(self):
        Config.validate()
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model = Config.GENERATIVE_MODEL

    def generate(self, user_query: str, persona: str, context_chunks: list) -> str:
        """
        Compiles custom persona instructions and retrieved context to generate a grounded response.
        """
        logger.info(f"Generating persona-adaptive response for persona: {persona}...")

        # 1. Select the base persona instructions
        if persona == "Technical Expert":
            persona_instructions = (
                "You are a Senior Systems Engineer. Provide clear root-cause analysis, "
                "configuration specifications, and precise API pathways or code blocks. "
                "Keep technical descriptions exact, highly structured, and diagnostic. "
                "Output actual code blocks, parameters, or configurations when relevant to the context."
            )
        elif persona == "Frustrated User":
            persona_instructions = (
                "You are a deeply empathetic, reassuring Customer Care Specialist. "
                "Begin with a warm, genuine validation of their difficulty (e.g., 'I understand how frustrating it is to deal with this...', "
                "'I completely realize how inconvenient this setup must be, and I am here to help you get this resolved.'). "
                "Use straightforward, reassuring, and simple action-oriented bullet steps. "
                "Avoid confusing technical jargon, source code snippets, or backend connection details."
            )
        else:  # Business Executive
            persona_instructions = (
                "You are a concise Client Relations Director. Focus on direct business outcomes, "
                "impact summaries, and high-level timelines for resolution. Keep responses extremely "
                "brief, highly professional, and skip unnecessary configuration or database details. "
                "Present summaries clearly and focus on operational stability and ROI."
            )

        # 2. Format context text
        context_texts = []
        for idx, chunk in enumerate(context_chunks):
            context_texts.append(f"Source [{chunk['source']}]:\n{chunk['text']}")
        context_block = "\n\n".join(context_texts)

        # 3. Assemble complete context-grounded system prompt
        system_instruction = (
            f"{persona_instructions}\n\n"
            "CRITICAL GROUNDING RULES:\n"
            "- Base your response ONLY on the provided FACTUAL CONTEXT DOCUMENTS below.\n"
            "- Do not hallucinate, extrapolate, or assume facts not explicitly found in the context documents.\n"
            "- If the context documents do not contain enough facts to answer, state clearly that you cannot find the answer in the reference manuals.\n\n"
            f"FACTUAL CONTEXT DOCUMENTS:\n{context_block}"
        )

        try:
            response = call_gemini_with_backoff(
                self.client.models.generate_content,
                model=self.model,
                contents=user_query,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )
            logger.info("Persona-adaptive response generated successfully.")
            return response.text
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise LLMCallError(f"Failed to generate response: {e}") from e

def generate_adaptive_response(user_query: str, persona: str, context_chunks: list) -> dict:
    """
    Generates a personalized response matching the classified user archetype.
    If context confidence is too low, the issue is flagged for escalation.
    Matches the exact signature specified in the reference document.
    """
    # 1. Establish the Escalation Check
    confidence_threshold = 0.40
    best_score = max([chunk["score"] for chunk in context_chunks]) if context_chunks else 0.0

    # Trigger escalation criteria if retrieval accuracy is poor
    if best_score < confidence_threshold or len(context_chunks) == 0:
        return {
            "escalated": True,
            "response": "I apologize, but I am unable to locate the precise solution to your request. I am connecting you with a live human support specialist.",
            "handoff_summary": generate_handoff_summary(user_query, persona, context_chunks)
        }

    # 2. Select System Prompt instruction set depending on classified persona
    if persona == "Technical Expert":
        persona_instructions = (
            "You are a Senior Systems Engineer. Provide clear root-cause analysis, "
            "configuration specifications, and precise API pathways or code blocks. "
            "Keep technical descriptions exact and structured."
        )
    elif persona == "Frustrated User":
        persona_instructions = (
            "You are a deeply empathetic, reassuring Customer Care Specialist. "
            "Begin with a warm, genuine validation of their difficulty. Use straightforward, "
            "reassuring, and simple action-oriented bullet steps. Avoid confusing jargon."
        )
    else:  # Business Executive
        persona_instructions = (
            "You are a concise Client Relations Director. Focus on direct business outcomes, "
            "impact summaries, and timelines for resolution. Keep responses extremely "
            "brief, professional, and skip unnecessary configuration details."
        )

    # 3. Assemble complete context-grounded system prompt
    context_text = "\n\n".join([f"Source [{c['source']}]: {c['text']}" for c in context_chunks])

    full_system_prompt = (
        f"{persona_instructions}\n\n"
        "CRITICAL RULES:\n"
        "- Base your response ONLY on the provided context.\n"
        "- Do not hallucinate or assume facts not found in the documents.\n\n"
        f"FACTUAL CONTEXT DOCUMENTS:\n{context_text}"
    )

    import os
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

    response = call_gemini_with_backoff(
        client.models.generate_content,
        model=Config.GENERATIVE_MODEL,
        contents=user_query,
        config=types.GenerateContentConfig(
            system_instruction=full_system_prompt,
            temperature=0.2
        )
    )

    return {
        "escalated": False,
        "response": response.text,
        "handoff_summary": None
    }

def generate_handoff_summary(user_query: str, persona: str, context_chunks: list) -> str:
    """Compiles detailed, structured JSON handoff data for an escalating support ticket."""
    handoff_data = {
        "persona": persona,
        "detected_issue": user_query[:100] + "...",
        "retrieved_sources": [c["source"] for c in context_chunks],
        "confidence_score": max([c["score"] for c in context_chunks]) if context_chunks else 0.0,
        "recommended_action": "Review system error codes, check API logs, and contact user directly."
    }
    import json
    return json.dumps(handoff_data, indent=2)

if __name__ == "__main__":
    # Standard check code (expects GEMINI_API_KEY in environment)
    generator = ResponseGenerator()
    context = [
        {
            "text": "For Developer subscriptions, the rate limit is 60 requests per minute (RPM). If exceeded, you receive a 429 Too Many Requests status code.",
            "source": "rate_limiting.txt",
            "score": 0.95
        }
    ]
    res = generator.generate(
        user_query="What is the rate limit for the free developer plan?",
        persona="Technical Expert",
        context_chunks=context
    )
    print("\nResult:")
    print(res)
