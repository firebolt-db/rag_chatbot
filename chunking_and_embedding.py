"""
This file chunks the documents and generates embeddings of those chunks. 
"""

import hashlib
from langchain_ollama import OllamaEmbeddings
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
import copy 
import re
import nltk
import time
from datetime import date
import json
import pickle
import pandas as pd
from pathlib import Path
from constants import *
import settings

"""
Generates a consistent chunking strategy string from environment variables.
This ensures round-trip integrity between insertion and retrieval phases.

Parameters:
    - chunking_strategy: ChunkingStrategy enum value
    - chunk_size: chunk size for recursive character text splitting (optional)
    - chunk_overlap: chunk overlap for recursive character text splitting (optional)
    - num_words_per_chunk: number of words per chunk for EVERY_N_WORDS strategy (optional)
    - num_sentences_per_chunk: number of sentences per chunk for sliding window strategy (optional)

Returns: standardized chunking strategy string for database storage
"""
def generate_chunking_strategy_string(chunking_strategy: ChunkingStrategy, 
                                    chunk_size: int = None, 
                                    chunk_overlap: int = None,
                                    num_words_per_chunk: int = None,
                                    num_sentences_per_chunk: int = None) -> str:
    
    if chunk_size is None:
        chunk_size = settings.FIREBOLT_RAG_CHATBOT_CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = settings.FIREBOLT_RAG_CHATBOT_CHUNK_OVERLAP
    if num_words_per_chunk is None:
        num_words_per_chunk = settings.FIREBOLT_RAG_CHATBOT_NUM_WORDS_PER_CHUNK
    if num_sentences_per_chunk is None:
        num_sentences_per_chunk = settings.FIREBOLT_RAG_CHATBOT_NUM_SENTENCES_PER_CHUNK
    
    if chunking_strategy is ChunkingStrategy.BY_PARAGRAPH:
        return "By paragraph"
    elif chunking_strategy is ChunkingStrategy.BY_SENTENCE:
        return "By sentence"
    elif chunking_strategy is ChunkingStrategy.BY_SENTENCE_WITH_SLIDING_WINDOW:
        return f"By {num_sentences_per_chunk} sentences with a sliding window"
    elif chunking_strategy is ChunkingStrategy.EVERY_N_WORDS:
        return f"Every {num_words_per_chunk} words"
    elif chunking_strategy is ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING:
        return f"Recursive character text splitting with chunk size = {chunk_size} and chunk overlap = {chunk_overlap}"
    else:
        return "Semantic chunking"

"""
Hashes each string in a list of strings.
Parameters: 
    - string_list: the list of strings to hash

Returns: a list of the hashes of the strings
"""
def hash_list_of_strings(string_list: list[str]) -> list[str]:
    hashes = [] # List of hashes of the strings

    for string in string_list:
        hashing_object = hashlib.sha256()
        
        # Update the hashing object with the string (the string has to be encoded)
        hashing_object.update(string.encode()) 
        
        # Create the hash and append it to the list of hashes. 
        # Use hexdigest to get a string of hexadecimal digits instead of a byte string, so we don't have to decode the byte string.
        hashes.append(hashing_object.hexdigest()) 

    return hashes


"""
Chunks a single piece of text by splitting it every n words. (i.e.: each chunk will be n words).

I took and reused this function from the following source: 
https://github.com/huggingface/transformers/blob/ad35309a6299f61f043c78f1d41da7e61800a30f/examples/research_projects/rag/use_own_knowledge_dataset.py#L28

Parameters:
    - text: input text
    - n: number of words per chunk

Returns: a list of the chunks after splitting
"""
def split_text_every_n_words(text: str, n: int = 100) -> list[str]:
    text = text.split(" ")
    return [" ".join(text[i : i + n]).strip() for i in range(0, len(text), n)]
 
"""
Chunks the documents using the provided chunking strategy.

Parameters:
    - document_dictionary: The dictionary returned from get_document_versions(), 
      but with an added key "document_id" whose value is the list of all the document IDs
    - chunking_strategy: the desired chunking strategy.
    - rcts_chunk_size: 
        Chunk size for recursive character text splitting. This will be used if chunking_strategy is 
        ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING
    - rcts_chunk_overlap: 
        Chunk overlap for recursive character text splitting. This will be used if chunking_strategy is 
        ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING
    - num_words_per_chunk:
        The number of words in each chunk. This will be used if chunking_strategy is ChunkingStrategy.EVERY_N_WORDS.
    - num_sentences_per_chunk: The number of sentences per chunk when chunking by sentences with a sliding window. 

Returns: 
    A dictionary with all the chunks that has the following keys and values:
        - key: 'document_text', value: the text in each file in the 'filepath' list
        - key: 'document_version', value: the list of versions for the filepaths
        - key: 'document_id', value: a list of all the document IDs.        
        - key: 'document_name', value: a list of filenames of all the docs 
        - key: 'chunk_content', value: a list of all the chunks
        - key: 'internal_only', value: for each filepath, whether that file is internal only or not
        - key: 'chunk_id', value: a list of the chunk IDs
        - key: 'chunking_strategy', value: a list containing the chunking strategy used for each chunk   
"""

def chunk_documents(document_dictionary: dict, chunking_strategy: ChunkingStrategy = ChunkingStrategy.EVERY_N_WORDS, 
                    rcts_chunk_size: int = None, rcts_chunk_overlap: int = None, 
                    num_words_per_chunk: int = None, num_sentences_per_chunk: int = None) -> dict:

    if rcts_chunk_size is None:
        rcts_chunk_size = settings.FIREBOLT_RAG_CHATBOT_CHUNK_SIZE
    if rcts_chunk_overlap is None:
        rcts_chunk_overlap = settings.FIREBOLT_RAG_CHATBOT_CHUNK_OVERLAP
    if num_words_per_chunk is None:
        num_words_per_chunk = settings.FIREBOLT_RAG_CHATBOT_NUM_WORDS_PER_CHUNK
    if num_sentences_per_chunk is None:
        num_sentences_per_chunk = settings.FIREBOLT_RAG_CHATBOT_NUM_SENTENCES_PER_CHUNK

    document_ids = document_dictionary[DOC_ID_KEY]
    document_texts = document_dictionary[DOC_TEXTS_KEY]
    document_versions = document_dictionary[DOC_VERSION_KEY]
    document_names = document_dictionary[DOC_NAME_KEY]
    internal_only_statuses = document_dictionary[INTERNAL_ONLY_KEY]
    
    print(f"\nChunking {len(document_ids)} documents using {chunking_strategy.name}...")

      
    # Dictionary that stores the necessary info for each chunk
    chunk_dictionary = {DOC_ID_KEY:[], DOC_VERSION_KEY:[], DOC_NAME_KEY:[], CHUNK_CONTENT_KEY:[], INTERNAL_ONLY_KEY:[]} 
    
    chunking_strategy_string = generate_chunking_strategy_string(
        chunking_strategy, rcts_chunk_size, rcts_chunk_overlap, 
        num_words_per_chunk, num_sentences_per_chunk
    )

    for i in range(len(document_ids)):
        if i % 10 == 0 or i == len(document_ids) - 1:
            print(f"  Chunking document {i+1}/{len(document_ids)}: {document_names[i]}")
        document_id = document_ids[i]
        document_text = document_texts[i]
        document_version = document_versions[i]
        internal_only_status = internal_only_statuses[i]
        document_name = document_names[i]

        # Chunk by the provided chunking strategy
        if chunking_strategy is ChunkingStrategy.BY_PARAGRAPH:
            current_document_chunks = re.split(r'\n{2,}', document_text) 
        elif chunking_strategy is ChunkingStrategy.BY_SENTENCE:
            current_document_chunks = split_text_into_sentences(document_text)
        elif chunking_strategy is ChunkingStrategy.BY_SENTENCE_WITH_SLIDING_WINDOW:
            current_document_chunks = chunk_by_sentences_with_sliding_window(document_text, chunk_size=num_sentences_per_chunk)
        elif chunking_strategy is ChunkingStrategy.EVERY_N_WORDS:
            current_document_chunks = split_text_every_n_words(document_text, num_words_per_chunk)
        elif chunking_strategy is ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=rcts_chunk_size, chunk_overlap=rcts_chunk_overlap)    
            current_document_chunks = text_splitter.split_text(document_text)
        else:
            text_splitter = SemanticChunker(OllamaEmbeddings(model=EMBEDDING_MODEL_NAME))
            current_document_chunks = text_splitter.split_text(document_text)

        num_of_chunks = len(current_document_chunks)

        # All the chunks for one doc should have the same doc ID, version, and "internal_only" status
        current_document_ids = [document_id for j in range(num_of_chunks)] 
        current_document_versions = [document_version for j in range(num_of_chunks)]
        current_internal_only_statuses = [internal_only_status for j in range(num_of_chunks)]
        current_document_names = [document_name for j in range(num_of_chunks)]

        chunk_dictionary[DOC_ID_KEY].extend(current_document_ids)
        chunk_dictionary[CHUNK_CONTENT_KEY].extend(current_document_chunks)
        chunk_dictionary[DOC_VERSION_KEY].extend(current_document_versions)
        chunk_dictionary[INTERNAL_ONLY_KEY].extend(current_internal_only_statuses)
        chunk_dictionary[DOC_NAME_KEY].extend(current_document_names)

    chunk_dictionary[CHUNK_ID_KEY] = hash_list_of_strings(chunk_dictionary[CHUNK_CONTENT_KEY]) # Hash the chunks to get the chunk IDs
    chunk_dictionary[CHUNKING_STRATEGY_KEY] = [chunking_strategy_string for i in range(len(chunk_dictionary[CHUNK_CONTENT_KEY]))]

    total_chunks = len(chunk_dictionary[CHUNK_CONTENT_KEY])
    print(f"Done chunking the documents - generated {total_chunks} chunks")

    return chunk_dictionary

"""
Splits a piece of text into sentences.
Parameters: 
    - text: The text to split

Returns: a list of the sentences in the text
"""
def split_text_into_sentences(text: str) -> list[str]:
    nltk.download('punkt')
    sentences = nltk.sent_tokenize(text)

    return sentences

"""
Chunks a piece of text by sentences, with a sliding window.
A sliding window is defined as follows. Suppose we have the following text:
    "Sentence 0. Sentence 1. Sentence 2. Sentence 3. Sentence 4."

Then, chunking this text by sentences with a 3-sentence sliding window creates the following chunks:
    ["Sentence 0. Sentence 1. Sentence 2.", "Sentence 1. Sentence 2. Sentence 3.", "Sentence 2. Sentence 3. Sentence 4."]

Parameters:
    - text: The text to chunk
    - chunk_size: How many sentences are in each chunk
Returns: the list of chunks
"""
def chunk_by_sentences_with_sliding_window(text: str, chunk_size: int = 3) -> list[str]:
    sentences = split_text_into_sentences(text) # split text into non-overlapping sentences
    num_sentences = len(sentences) # how many sentences there are in the text
    chunks = []

    # Make overlapping chunks with a sliding window from the non-overlapping sentences
    for i in range(num_sentences - chunk_size + 1):
        chunks.append(" ".join(sentences[i : i + chunk_size]))

    return chunks

"""
Generates embeddings of all the chunks that will be loaded into the Firebolt table.
Parameters:
    - chunk_dictionary: The dictionary returned from chunk_documents(), but with the added key 'repo_name', 
                      whose value is a list of the repos that each chunk is from

Returns: The input dictionary, but with the following keys and values added:
            - key: 'embeddings', value: a list of the embeddings corresponding to each chunk
            - key: 'embedding_model', value: a list containing the embedding model used to embed each chunk                                             
            - key: 'date_generated', value: a list containing the date each embedding was generated                                             
"""

def embed_chunks(chunk_dictionary: dict) -> dict:
    chunks = chunk_dictionary[CHUNK_CONTENT_KEY]
    total_chunks = len(chunks)
    print(f"\nEmbedding {total_chunks} chunks using {EMBEDDING_MODEL_NAME}...")
    print("Note: Ollama may output 'decode: cannot decode batches' warnings during embedding generation")
    print("These are normal verbose logs from the embedding model and do not indicate errors")
    
    start_time = time.time()

    ollama_emb = OllamaEmbeddings(model=EMBEDDING_MODEL_NAME)
    dictionary = copy.deepcopy(chunk_dictionary) # use deepcopy() to make sure changes to this dictionary don't change the original one
    dictionary[EMBEDDING_KEY] = []

    # Add model name and date generated
    dictionary[EMBEDDING_MODEL_KEY] = []
    dictionary[DATE_GENERATED_KEY] = []

    for i in range(len(chunks)):
        if i % 50 == 0 or i == len(chunks) - 1:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  Embedding chunk {i+1}/{total_chunks} ({rate:.1f} chunks/sec)")
        current_chunk = chunks[i]
        embedding = ollama_emb.embed_documents([current_chunk])

        # Ollama embeddings return a list of lists, so we flatten it to a 1D list here
        embedding_as_numpy = np.array(embedding) # need to convert to numpy array to use the reshape method
        flattened_embedding = embedding_as_numpy.reshape(embedding_as_numpy.size).tolist()

        dictionary[EMBEDDING_KEY].append(flattened_embedding)

        # Add the embedding model and date for every embedding
        dictionary[EMBEDDING_MODEL_KEY].append(EMBEDDING_MODEL_NAME)
        dictionary[DATE_GENERATED_KEY].append(date.today())

    elapsed = time.time() - start_time
    avg_rate = total_chunks / elapsed if elapsed > 0 else 0
    print(f"Done embedding the chunks - {total_chunks} chunks in {elapsed:.1f}s ({avg_rate:.1f} chunks/sec)")
    return dictionary

"""
Generate an embedding for a user question.
Parameters: 
    - query: the query to embed

Returns: the embedding for that query
"""
def embed_question(query: str) -> list[float]:
    ollama_emb = OllamaEmbeddings(model=EMBEDDING_MODEL_NAME)
    
    embedding_start = time.time()
    result = ollama_emb.embed_query(query)
    embedding_time = time.time() - embedding_start
    print(f"  Question embedding completed in {embedding_time:.3f}s")
    
    return result


def save_embeddings_to_file(embeddings_dict: dict, file_path: str, format: str = "pickle") -> None:
    """
    Save embeddings dictionary to disk in the specified format.
    
    Parameters:
        - embeddings_dict: Dictionary returned from embed_chunks()
        - file_path: Path where to save the embeddings file
        - format: File format - "pickle", "json", or "parquet"
    """
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == "pickle":
            with open(file_path, 'wb') as f:
                pickle.dump(embeddings_dict, f)
        elif format.lower() == "json":
            json_dict = copy.deepcopy(embeddings_dict)
            if DATE_GENERATED_KEY in json_dict:
                json_dict[DATE_GENERATED_KEY] = [str(d) for d in json_dict[DATE_GENERATED_KEY]]
            with open(file_path, 'w') as f:
                json.dump(json_dict, f, indent=2)
        elif format.lower() == "parquet":
            df = pd.DataFrame(embeddings_dict)
            df.to_parquet(file_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
            
        print(f"Embeddings saved to {file_path} in {format} format")
        
    except Exception as e:
        print(f"Error saving embeddings to {file_path}: {e}")
        raise


def load_embeddings_from_file(file_path: str, format: str = "pickle") -> dict:
    """
    Load embeddings dictionary from disk.
    
    Parameters:
        - file_path: Path to the embeddings file
        - format: File format - "pickle", "json", or "parquet"
        
    Returns:
        - Dictionary with embeddings and metadata
    """
    try:
        if format.lower() == "pickle":
            with open(file_path, 'rb') as f:
                embeddings_dict = pickle.load(f)
        elif format.lower() == "json":
            with open(file_path, 'r') as f:
                embeddings_dict = json.load(f)
            if DATE_GENERATED_KEY in embeddings_dict:
                from datetime import datetime
                embeddings_dict[DATE_GENERATED_KEY] = [
                    datetime.strptime(d, '%Y-%m-%d').date() if isinstance(d, str) else d 
                    for d in embeddings_dict[DATE_GENERATED_KEY]
                ]
        elif format.lower() == "parquet":
            df = pd.read_parquet(file_path)
            embeddings_dict = df.to_dict('list')
            if EMBEDDING_KEY in embeddings_dict:
                embeddings_dict[EMBEDDING_KEY] = [
                    emb.tolist() if hasattr(emb, 'tolist') else emb 
                    for emb in embeddings_dict[EMBEDDING_KEY]
                ]
        else:
            raise ValueError(f"Unsupported format: {format}")
            
        print(f"Embeddings loaded from {file_path}")
        return embeddings_dict
        
    except Exception as e:
        print(f"Error loading embeddings from {file_path}: {e}")
        raise


def generate_embeddings_filename(repo_name: str, chunking_strategy: str, format: str = "pickle") -> str:
    """
    Generate a standardized filename for embeddings persistence.
    
    Parameters:
        - repo_name: Name of the repository
        - chunking_strategy: String representation of chunking strategy
        - format: File format extension
        
    Returns:
        - Filename string
    """
    clean_repo = re.sub(r'[^\w\-_]', '_', repo_name)
    clean_strategy = re.sub(r'[^\w\-_]', '_', chunking_strategy.replace(' ', '_'))
    
    extension = {"pickle": "pkl", "json": "json", "parquet": "parquet"}.get(format.lower(), "pkl")
    return f"embeddings_{clean_repo}_{clean_strategy}.{extension}"
