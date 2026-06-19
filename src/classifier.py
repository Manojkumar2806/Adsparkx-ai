from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import json
import random
import time

from src.config import Config
from src.logger import setup_logger
from src.exceptions import LLMCallError

logger = setup_logger("classifier")

class ClassificationResult(BaseModel):
    persona: str = Field(
        description="Must be exactly one of: 'Technical Expert', 'Frustrated User', 'Business Executive'"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0 representing the classification strength"
    )
    reasoning: str = Field(
        description="Concise 1-2 sentence justification of why this persona matches the query"
    )
    is_sensitive: bool = Field(
        description="True if the query explicitly mentions billing, invoices, pricing, refunds, duplicate charges, legal threats, or account settings (deletion, recovery, password reset)."
    )
    sentiment: str = Field(
        description="Overall query sentiment. Must be exactly one of: 'Positive', 'Neutral', 'Negative'"
    )

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

class PersonaClassifier:
    def __init__(self):
        Config.validate()
        # Initialize the official Google GenAI client
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model = Config.GENERATIVE_MODEL

    def classify(self, message: str) -> ClassificationResult:
        """
        Analyzes a customer support message and returns a structured classification.
        """
        logger.info(f"Classifying incoming message: {message[:60]}...")
        
        system_instruction = (
            "You are an advanced sentiment, tone, and vocabulary classification engine. "
            "Your task is to analyze the customer support query and classify it into exactly one of three customer personas:\n"
            "1. 'Technical Expert': Uses jargon, code blocks, or requests exact API specs, bearer tokens, connection pooling, and configuration settings.\n"
            "2. 'Frustrated User': Uses emotional terms, caps, exclamation marks, or mentions immediate urgency, delayed service, or complaints.\n"
            "3. 'Business Executive': Focuses on business impact, ROI, timelines, contracts, billing policies, and brevity.\n\n"
            "Additionally, you must detect if the topic is 'sensitive' (billing, payments, invoices, refunds, password recoveries, account deletion, security, legal issues) "
            "and determine the sentiment (Positive, Neutral, Negative)."
        )

        try:
            # Call models.generate_content using google-genai structured output mechanism
            response = call_gemini_with_backoff(
                self.client.models.generate_content,
                model=self.model,
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ClassificationResult,
                    temperature=0.1
                )
            )
            
            # Retrieve the parsed schema object from response.parsed
            result: ClassificationResult = response.parsed
            
            logger.info(
                f"Classification Successful: Persona={result.persona}, "
                f"Confidence={result.confidence:.2f}, Sensitive={result.is_sensitive}, Sentiment={result.sentiment}"
            )
            return result

        except Exception as e:
            logger.error(f"Error during message classification: {e}")
            # Graceful fallback: return a default neutral structure instead of crashing the pipeline
            return ClassificationResult(
                persona="Business Executive",
                confidence=0.5,
                reasoning=f"Fallback triggered due to classification error: {str(e)}",
                is_sensitive=False,
                sentiment="Neutral"
            )

def classify_customer_persona(user_message: str) -> dict:
    """
    Analyzes the user's message and classifies it into one of the three target personas.
    Matches the signature specified in the reference document.
    """
    classifier = PersonaClassifier()
    result = classifier.classify(user_message)
    return {
        "persona": result.persona,
        "confidence": result.confidence,
        "reasoning": result.reasoning
    }

if __name__ == "__main__":
    # Quick visual verification of classifier
    classifier = PersonaClassifier()
    test_msgs = [
        "Where is the guide to clear cookies? It's been an hour and nothing is loading on your interface!",
        "What are the header parameter requirements for your bearer token auth implementation?",
        "Our operational uptime is decreasing. We need a timeline of when billing disputes are resolved."
    ]
    for msg in test_msgs:
        result = classify_customer_persona(msg)
        print(f"\nMessage: '{msg}'\nResult: {json.dumps(result, indent=2)}")
