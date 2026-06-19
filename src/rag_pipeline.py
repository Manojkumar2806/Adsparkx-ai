import os
from pathlib import Path
import chromadb
from google import genai
from google.genai import types
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from src.config import Config
from src.logger import setup_logger
from src.exceptions import VectorDBError, IngestionError, LLMCallError

logger = setup_logger("rag_pipeline")

class RAGPipeline:
    def __init__(self, force_local: bool = False):
        Config.validate()
        self.gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.chroma_client = None
        self.collection_name = Config.COLLECTION_NAME

        # Initialize ChromaDB Client
        if Config.CHROMA_API_KEY and not force_local:
            try:
                logger.info("Attempting to connect to ChromaDB Cloud client...")
                tenant = Config.CHROMA_TENANT or "default"
                database = Config.CHROMA_DATABASE or "default"
                
                # Check for CloudClient or fall back to HttpClient
                if hasattr(chromadb, "CloudClient"):
                    self.chroma_client = chromadb.CloudClient(
                        tenant=tenant,
                        database=database,
                        api_key=Config.CHROMA_API_KEY
                    )
                else:
                    logger.warning("chromadb.CloudClient not available. Using chromadb.HttpClient for Cloud token auth.")
                    from chromadb.config import Settings
                    self.chroma_client = chromadb.HttpClient(
                        host=Config.CHROMA_HOST,
                        settings=Settings(
                            chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                            chroma_client_auth_credentials=Config.CHROMA_API_KEY,
                            chroma_tenant=tenant,
                            chroma_database=database
                        )
                    )
                logger.info("Successfully connected to ChromaDB Cloud.")
            except Exception as e:
                logger.error(f"ChromaDB Cloud connection failed: {e}. Falling back to local PersistentClient.")
                self._init_local_client()
        else:
            logger.info("Initializing local ChromaDB PersistentClient...")
            self._init_local_client()

        # Connect or create collection with cosine similarity configuration
        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Connected to collection '{self.collection_name}'. Current size: {self.collection.count()} items.")
        except Exception as e:
            logger.error(f"Error accessing collection '{self.collection_name}': {e}")
            raise VectorDBError(f"Failed to initialize Chroma DB collection: {e}") from e

    def _init_local_client(self):
        """Initializes a local persistent client, with self-healing on corruption."""
        import shutil
        db_path = Path(Config.CHROMA_LOCAL_PATH)
        try:
            self.chroma_client = chromadb.PersistentClient(path=str(db_path))
            logger.info(f"Initialized local PersistentClient at: {db_path}")
        except Exception as e:
            logger.warning(f"Chroma DB local initialization failed: {e}. Attempting self-healing by deleting corrupted database folder...")
            try:
                if db_path.exists():
                    shutil.rmtree(db_path)
                    logger.info("Successfully deleted corrupted Chroma database directory.")
                self.chroma_client = chromadb.PersistentClient(path=str(db_path))
                logger.info(f"Self-healed local PersistentClient successfully initialized at: {db_path}")
            except Exception as retry_err:
                logger.critical(f"Critical: Local Chroma DB client self-healing failed: {retry_err}")
                raise VectorDBError(f"Failed to initialize local Chroma DB: {retry_err}") from retry_err

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Calls the Gemini Embedding model to generate dense vectors in batches.
        """
        logger.info(f"Generating embeddings for {len(texts)} chunks using {Config.EMBEDDING_MODEL}...")
        try:
            response = self.gemini_client.models.embed_content(
                model=Config.EMBEDDING_MODEL,
                contents=[types.Content(parts=[types.Part(text=s)]) for s in texts]
            )
            # Handle both single embedding return and batch list returns
            if hasattr(response, 'embeddings') and response.embeddings:
                return [emb.values for emb in response.embeddings]
            else:
                raise LLMCallError("No embeddings returned in response.")
        except Exception as e:
            logger.error(f"Gemini embedding generation failed: {e}")
            raise LLMCallError(f"Gemini embedding API failed: {e}") from e

    def get_embedding(self, text: str) -> list[float]:
        """Wrapper for single text embedding."""
        return self.get_embeddings([text])[0]

    def parse_document(self, filepath: Path) -> str:
        """
        Parses text based on file format (.txt, .md, .pdf).
        """
        logger.info(f"Parsing document: {filepath.name}")
        if not filepath.exists():
            raise IngestionError(f"File not found: {filepath}")

        suffix = filepath.suffix.lower()
        
        try:
            if suffix in [".txt", ".md"]:
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            elif suffix == ".pdf":
                reader = PdfReader(filepath)
                text_list = []
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_list.append(page_text)
                return "\n".join(text_list)
            else:
                logger.warning(f"Unsupported file format: {suffix}. Skipping {filepath.name}.")
                return ""
        except Exception as e:
            logger.error(f"Error parsing file {filepath.name}: {e}")
            raise IngestionError(f"Failed to parse {filepath.name}: {e}") from e

    def ingest_all_documents(self, force: bool = False):
        """
        Reads data directory, chunks files, embeds, and loads them into the collection.
        If force=False and the collection is already populated, it will skip ingestion to save time and API costs.
        """
        data_dir = Config.DATA_DIR
        if not data_dir.exists() or not list(data_dir.iterdir()):
            logger.warning(f"Data directory '{data_dir}' is empty or does not exist. Ingestion skipped.")
            return

        if not force and self.collection.count() > 0:
            logger.info("Vector database already contains documents. Skipping automatic ingestion.")
            return

        logger.info("Starting knowledge base ingestion pipeline...")
        
        # Clear existing entries in collection
        if self.collection.count() > 0:
            logger.info("Clearing existing entries from vector collection for complete re-indexing...")
            # Deleting all by retrieving all ids
            all_ids = self.collection.get()["ids"]
            if all_ids:
                self.collection.delete(ids=all_ids)

        splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)
        
        all_chunks = []
        all_metadatas = []
        all_ids = []
        
        for filepath in data_dir.iterdir():
            if filepath.is_file() and filepath.name != ".gitkeep":
                try:
                    content = self.parse_document(filepath)
                    if not content.strip():
                        continue
                    
                    chunks = splitter.split_text(content)
                    logger.info(f"Document {filepath.name} split into {len(chunks)} chunks.")
                    
                    for idx, chunk in enumerate(chunks):
                        all_chunks.append(chunk)
                        all_metadatas.append({
                            "source": filepath.name,
                            "chunk_index": idx
                        })
                        all_ids.append(f"{filepath.name}_chunk_{idx}")
                except Exception as e:
                    logger.error(f"Error preparing {filepath.name} for ingestion: {e}")
                    
        if not all_chunks:
            logger.warning("No text chunks found for ingestion.")
            return

        # Batch embed and write to DB
        # To avoid rate limits on very large datasets, we process in chunks of 50
        batch_size = 50
        total_chunks = len(all_chunks)
        logger.info(f"Indexing {total_chunks} total chunks to ChromaDB...")
        
        for i in range(0, total_chunks, batch_size):
            end_idx = min(i + batch_size, total_chunks)
            batch_texts = all_chunks[i:end_idx]
            batch_metadata = all_metadatas[i:end_idx]
            batch_ids = all_ids[i:end_idx]
            
            try:
                embeddings = self.get_embeddings(batch_texts)
                self.collection.add(
                    ids=batch_ids,
                    embeddings=embeddings,
                    metadatas=batch_metadata,
                    documents=batch_texts
                )
                logger.info(f"Indexed chunks {i+1} to {end_idx} of {total_chunks}.")
            except Exception as e:
                logger.critical(f"Critical error during batch indexing: {e}")
                raise IngestionError(f"Database ingestion failed: {e}") from e

        logger.info("Ingestion pipeline finished successfully.")

    def retrieve_context(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Embeds query and performs semantic cosine similarity search in Chroma.
        Returns a list of structured items: {'text': ..., 'source': ..., 'score': ...}
        """
        logger.info(f"Querying context for: '{query[:60]}' with top_k={top_k}")
        try:
            query_vector = self.get_embedding(query)
            
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=top_k
            )
            
            retrieved_items = []
            if results and results.get('documents') and results['documents'][0]:
                documents = results['documents'][0]
                metadatas = results['metadatas'][0]
                # Distances: cosine distance in Chroma is 1.0 - cosine_similarity
                # Cosine distance ranges from 0 (identical) to 2 (opposite).
                # Similarity = 1.0 - distance
                distances = results['distances'][0] if results.get('distances') else [0.0] * len(documents)
                
                for idx in range(len(documents)):
                    distance = distances[idx]
                    similarity = 1.0 - distance
                    
                    retrieved_items.append({
                        "text": documents[idx],
                        "source": metadatas[idx]["source"],
                        "score": max(0.0, min(1.0, similarity)) # clamp between 0.0 and 1.0
                    })
                    
            logger.info(f"Retrieved {len(retrieved_items)} chunks. Best similarity score: {retrieved_items[0]['score']:.4f}" if retrieved_items else "No chunks retrieved.")
            return retrieved_items
        except Exception as e:
            logger.error(f"Error during context retrieval: {e}")
            # Graceful fallback: return empty list
            return []

    def ingest_document(self, doc_name: str, content: str):
        """Split document and add the chunks to the vector database. Matching the signature in the reference document."""
        splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)
        chunks = splitter.split_text(content)
        
        for idx, chunk in enumerate(chunks):
            embedding = self.get_embedding(chunk)
            chunk_id = f"{doc_name}_chunk_{idx}"
            
            self.collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                metadatas=[{"source": doc_name, "chunk_index": idx}],
                documents=[chunk]
            )

class LocalRAGPipeline(RAGPipeline):
    def __init__(self, db_dir="./chroma_db"):
        # Temporary override config local path to db_dir
        old_local_path = Config.CHROMA_LOCAL_PATH
        Config.CHROMA_LOCAL_PATH = db_dir
        super().__init__(force_local=True)
        Config.CHROMA_LOCAL_PATH = old_local_path

if __name__ == "__main__":
    # Test execution
    pipeline = RAGPipeline(force_local=True)
    # Re-ingest
    pipeline.ingest_all_documents(force=True)
    # Search test
    test_query = "What is the billing cycle?"
    context = pipeline.retrieve_context(test_query)
    for c in context:
        print(f"\nSource: {c['source']} | Score: {c['score']:.4f}\nContent: {c['text'][:120]}...")
