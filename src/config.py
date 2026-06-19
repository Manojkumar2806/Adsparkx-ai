import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load env variables from root directory
dotenv_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path, override=True)

class Config:
    # Project Paths
    ROOT_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = ROOT_DIR / "data"
    CHROMA_LOCAL_PATH = str(ROOT_DIR / "chroma_db")
    LOG_FILE = ROOT_DIR / "app.log"

    # API Keys & Credentials
    # Fallback to system environment variable if not defined in .env
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
    CHROMA_HOST = os.getenv("CHROMA_HOST", "api.trychroma.com")
    CHROMA_TENANT = os.getenv("CHROMA_TENANT")
    CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "default")
    
    # Collection Name
    COLLECTION_NAME = "AdSparxAI"

    # Models
    # Using the latest stable Gemini and Embedding models
    GENERATIVE_MODEL = "gemini-3-pro-preview"
    EMBEDDING_MODEL = "gemini-embedding-2"

    # Thresholds & Limits
    # Distance in Chroma is cosine distance (or L2, inner product depending on configuration)
    # Cosine Similarity = 1.0 - Cosine Distance. We want similarity >= 0.40.
    CONFIDENCE_THRESHOLD = 0.40
    CONSECUTIVE_FRUSTRATION_LIMIT = 2

    @classmethod
    def validate(cls):
        """Validate critical configuration elements."""
        if not cls.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is missing. "
                "Please configure it in your .env file or environment variables."
            )
