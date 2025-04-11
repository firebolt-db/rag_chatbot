"""
This file defines the constants that are used in the code files.
"""
from enum import Enum

# These are the keys in the dictionary that stores the documents you're using for RAG
DOC_ID_KEY = "document_id"
CHUNK_ID_KEY = "chunk_id"
CHUNK_CONTENT_KEY = "chunk_content"
CHUNKING_STRATEGY_KEY = "chunking_strategy"
EMBEDDING_KEY = "embedding"
DATE_GENERATED_KEY = "date_generated"
EMBEDDING_MODEL_KEY = "embedding_model"
DOC_VERSION_KEY = "document_version"
INTERNAL_ONLY_KEY = "internal_only"
REPO_NAME_KEY = "repo_name"
DOC_NAME_KEY = "document_name"
FILEPATHS_KEY = "filepath"
DOC_TEXTS_KEY = "document_text"

# Dictionary keys for `repo_dict` in `populate_table.py`
REPO_PATHS_KEY = "repo_paths"
MAIN_BRANCH_KEY = "main_branch"

EMBEDDING_MODEL_NAME = "nomic-embed-text" 
LLM_NAME = "llama3.1"

# File extensions that are supported by the file parsing functions. Only files with these extensions from the repo will be parsed.
ALLOWED_FILE_EXTENSIONS = [".docx", ".txt", ".md"] 


# Here, add filenames that you want to ignore when reading from the document repos. (For example, the README file or the license).
DISALLOWED_FILENAMES = []

# Enum for the chunking strategies
class ChunkingStrategy(Enum):
    BY_SENTENCE = 1
    BY_SENTENCE_WITH_SLIDING_WINDOW = 2
    BY_PARAGRAPH = 3
    EVERY_N_WORDS = 4
    RECURSIVE_CHARACTER_TEXT_SPLITTING = 5
    SEMANTIC_CHUNKING = 6

# Enum for the similarity metrics for vector search
class VectorSimilarityMetric(Enum):
    COSINE_DISTANCE = 1
    COSINE_SIMILARITY = 2
    EUCLIDEAN_DISTANCE = 3
    INNER_PRODUCT = 4
    MANHATTAN_DISTANCE = 5
    SQUARED_EUCLIDEAN_DISTANCE = 6

# Set this constant to your local path to GitHub (with no spaces)
LOCAL_GITHUB_PATH = """YOUR LOCAL GITHUB PATH HERE"""

# Column names in the Firebolt table
DOC_ID_COL = DOC_ID_KEY
CHUNK_ID_COL = CHUNK_ID_KEY
CHUNK_CONTENT_COL = CHUNK_CONTENT_KEY
CHUNKING_STRATEGY_COL = CHUNKING_STRATEGY_KEY
EMBEDDING_COL = EMBEDDING_KEY
EMBEDDING_MODEL_COL = EMBEDDING_MODEL_KEY
DOC_VERSION_COL = DOC_VERSION_KEY
DATE_GENERATED_COL = DATE_GENERATED_KEY
INTERNAL_ONLY_COL = INTERNAL_ONLY_KEY
REPO_NAME_COL = REPO_NAME_KEY
DOC_NAME_COL = DOC_NAME_KEY

MAX_TOKENS = 5000 # Max number of tokens to keep in the LLM's message history

# Name of the file that stores the chat history (without the file extension). There will be a session ID added to each filename.
CHAT_HISTORY_FILENAME = "chat_history" 

# Separates each message from the next one in the chat history files
CHAT_HISTORY_SEPARATOR = "-"*15 
