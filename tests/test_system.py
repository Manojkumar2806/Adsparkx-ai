import json
import sys
from pathlib import Path

# Add root folder to path to enable package import when run directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.logger import setup_logger
from src.classifier import PersonaClassifier
from src.rag_pipeline import RAGPipeline
from src.escalator import EscalationManager
from src.generator import ResponseGenerator

logger = setup_logger("test_system")

TEST_SCENARIOS = [
    {
        "id": 1,
        "message": "Where is the guide to clear cookies? It's been an hour and nothing is loading on your interface!",
        "expected_persona": "Frustrated User",
        "description": "Tests cache clearing instructions and empathetic tone."
    },
    {
        "id": 2,
        "message": "What are the header parameter requirements for your bearer token auth implementation?",
        "expected_persona": "Technical Expert",
        "description": "Tests API headers documentation retrieval and structured code blocks response."
    },
    {
        "id": 3,
        "message": "Our operational uptime is decreasing. We need a timeline of when billing disputes are resolved.",
        "expected_persona": "Business Executive",
        "description": "Tests billing disputes query and concise timeline/business impact summary."
    },
    {
        "id": 4,
        "message": "I'm experiencing an issue with your database integration that's causing internal errors.",
        "expected_persona": "Technical Expert",
        "description": "Tests database integration documentation retrieval and step-by-step pathway."
    },
    {
        "id": 5,
        "message": "My billing statement has unexpected duplicate charges. I demand an immediate refund!",
        "expected_persona": "Frustrated User",
        "description": "Tests billing sensitivity and triggers immediate human escalation handoff."
    }
]

def run_test_suite():
    print("=" * 80)
    print("                 SUPPORT AGENT END-TO-END VERIFICATION TEST SUITE             ")
    print("=" * 80)
    
    try:
        Config.validate()
    except ValueError as e:
        print(f"\nConfiguration Error: {e}")
        print("\nPlease add GEMINI_API_KEY to your .env file to run this test suite.")
        sys.exit(1)

    # 1. Initialize Pipeline Services
    print("\n[System Setup] Initializing modules...")
    classifier = PersonaClassifier()
    pipeline = RAGPipeline(force_local=False)
    escalator = EscalationManager()
    generator = ResponseGenerator()

    # 2. Automatically ingest documents (skips if already indexed)
    print("[System Setup] Verifying vector index is loaded...")
    pipeline.ingest_all_documents(force=False)
    
    print(f"[System Setup] Vector database count: {pipeline.collection.count()} chunks.")
    print("=" * 80)

    # 3. Process Test Scenarios
    for scen in TEST_SCENARIOS:
        print(f"\n--- SCENARIO #{scen['id']} (Expected: {scen['expected_persona']}) ---")
        print(f"Description: {scen['description']}")
        print(f"User Message: \"{scen['message']}\"\n")
        
        # Turn 1: Classify
        classification = classifier.classify(scen["message"])
        print(f"-> Classified Persona: {classification.persona} (Confidence: {classification.confidence:.2f})")
        print(f"-> Sentiment: {classification.sentiment} | Is Sensitive: {classification.is_sensitive}")
        print(f"-> Reasoning: {classification.reasoning}")
        
        # Turn 2: Retrieve Context
        context_chunks = pipeline.retrieve_context(scen["message"], top_k=2)
        print(f"-> Retrieved {len(context_chunks)} document chunks.")
        for i, chk in enumerate(context_chunks):
            print(f"   [{i+1}] Source: {chk['source']} | Score: {chk['score']:.4f} | Snippet: {chk['text'][:80].strip()}...")

        # Turn 3: Check Escalation (we simulate 0 consecutive frustrations for Turn 1)
        escalation_result = escalator.evaluate(
            query=scen["message"],
            persona_info=classification.model_dump(),
            context_chunks=context_chunks,
            consecutive_frustration=1 if classification.persona == "Frustrated User" else 0
        )
        
        if escalation_result["escalated"]:
            print("\n*** ESCALATED TO HUMAN AGENT ***")
            print(f"Escalation Reason: {escalation_result['reason']}")
            print("Structured Handoff JSON:")
            print(json.dumps(escalation_result["handoff_summary"], indent=2))
        else:
            # Turn 4: Generate Response
            print("\n*** GENERATING AGENT RESPONSE ***")
            response_text = generator.generate(
                user_query=scen["message"],
                persona=classification.persona,
                context_chunks=context_chunks
            )
            print("Response Output:")
            print("-" * 50)
            print(response_text)
            print("-" * 50)
            
        # Rate Limit Guard for Free Tier API (5 requests/minute limit)
        import time
        if scen != TEST_SCENARIOS[-1]:
            print("\n[Rate Limit Guard] Sleeping 15 seconds between scenarios to prevent rate limits...")
            time.sleep(15)

        print("=" * 80)

if __name__ == "__main__":
    run_test_suite()
