"""
This file populates the Firebolt table with the documents you are using for RAG.
"""

from get_docs_and_versions import get_filepaths_in_local_repo, get_document_versions, get_document_texts_and_names
from vector_search import populate_table, connect_to_firebolt
from chunking_and_embedding import chunk_documents, embed_chunks, hash_list_of_strings, save_embeddings_to_file, load_embeddings_from_file, generate_embeddings_filename, generate_chunking_strategy_string
from constants import *
import os
import time
import settings


"""
Populates the Firebolt table with the chunks, the embeddings, and all the other information in the table schema.

Parameters:
    - repo_dict: dictionary with the following keys and values:
            - key: 'repo_paths', value: a list of all the local paths to all the document repos you want to use. 
            - key: 'main_branch', value: a list of the names of the main branches of each repo. 
            - key: 'internal_only', value: a list of Booleans indicating whether that repo contains docs that are internal only. 
        See main for an example of this dictionary.
            
    - chunking_strategies: the chunking strategies to use for chunking the docs.
                            All the docs will be chunked with each of these chunking strategies, and all those chunks will be loaded into the table
    - batch_size: Number of rows to insert into the Firebolt table at a time. 
                    (e.g.: batch_size = 100 will insert your data into the table in batches of 100 rows at a time).                                                             
    - rcts_chunk_size: Chunk size for recursive character text splitting. 
                           This will be used if chunking_strategies contains ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING
    - rcts_chunk_overlap: Chunk overlap for recursive character text splitting. 
                              This will be used if chunking_strategies contains ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING
    - num_words_per_chunk: The number of words in each chunk. Will be used if chunking_strategies contains ChunkingStrategy.EVERY_N_WORDS
    - num_sentences_per_chunk: The number of sentences per chunk when chunking by sentences with a sliding window. 
                               Will be used if chunking_strategies contains ChunkingStrategy.BY_SENTENCE_WITH_SLIDING_WINDOW
    - persist_embeddings: Whether to save embeddings to disk after generation and load them on retry (default: False)
    - embeddings_format: Format for persisting embeddings - "pickle", "json", or "parquet" (default: "pickle")
    - embeddings_dir: Directory to store cached embeddings files (default: "embeddings_cache")

Returns: nothing
"""
def generate_embeddings_and_populate_table(repo_dict: dict, chunking_strategies: list[ChunkingStrategy], batch_size: int = 100,
                                            rcts_chunk_size: int = None, rcts_chunk_overlap: int = None, 
                                            num_words_per_chunk: int = None, num_sentences_per_chunk: int = None,
                                            persist_embeddings: bool = False, embeddings_format: str = "pickle",
                                            embeddings_dir: str = "embeddings_cache") -> None:
        if rcts_chunk_size is None:
            rcts_chunk_size = settings.FIREBOLT_RAG_CHATBOT_CHUNK_SIZE
        if rcts_chunk_overlap is None:
            rcts_chunk_overlap = settings.FIREBOLT_RAG_CHATBOT_CHUNK_OVERLAP
        if num_words_per_chunk is None:
            num_words_per_chunk = settings.FIREBOLT_RAG_CHATBOT_NUM_WORDS_PER_CHUNK
        if num_sentences_per_chunk is None:
            num_sentences_per_chunk = settings.FIREBOLT_RAG_CHATBOT_NUM_SENTENCES_PER_CHUNK

        repo_paths = repo_dict[REPO_PATHS_KEY]
        main_branches = repo_dict[MAIN_BRANCH_KEY]
        internal_only_statuses = repo_dict[INTERNAL_ONLY_KEY]

        # Get Firebolt table name from settings
        table_name = settings.FIREBOLT_RAG_CHATBOT_TABLE_NAME    
        
        print(f"\nValidating chunking strategy consistency...")
        validation_start = time.time()
        
        for strategy in chunking_strategies:
            current_strategy_string = generate_chunking_strategy_string(
                strategy, rcts_chunk_size, rcts_chunk_overlap, 
                num_words_per_chunk, num_sentences_per_chunk
            )
            
            try:
                connection, cursor = connect_to_firebolt()
                cursor.execute(f"SELECT DISTINCT {CHUNKING_STRATEGY_COL} FROM {table_name}")
                existing_strategies = cursor.fetchall()
                cursor.close()
                connection.close()
                
                if existing_strategies:
                    existing_strategy_strings = [row[0] for row in existing_strategies]
                    if current_strategy_string not in existing_strategy_strings:
                        print(f"\n⚠️  WARNING: Chunking strategy mismatch detected!")
                        print(f"Current strategy: '{current_strategy_string}'")
                        print(f"Existing strategies in database: {existing_strategy_strings}")
                        print(f"\nMixing different chunking strategies will break retrieval accuracy.")
                        print(f"Consider:")
                        print(f"  1. Use the same strategy as existing embeddings")
                        print(f"  2. Clear the database and repopulate with new strategy")
                        print(f"  3. Use a different table for the new strategy")
                        
                        response = input(f"\nContinue anyway? (y/N): ").strip().lower()
                        if response != 'y' and response != 'yes':
                            print(f"Aborting population to prevent strategy mismatch.")
                            return
                        else:
                            print(f"Continuing with mixed strategies (not recommended)...")
                    else:
                        print(f"✓ Strategy '{current_strategy_string}' matches existing embeddings")
                else:
                    print(f"✓ No existing embeddings found, proceeding with strategy '{current_strategy_string}'")
                    
            except Exception as e:
                print(f"⚠️  Could not validate chunking strategy (table may not exist yet): {e}")
                print(f"Proceeding with strategy '{current_strategy_string}'")
        
        validation_time = time.time() - validation_start
        print(f"Validation completed in {validation_time:.1f}s")
        
        for i in range(len(repo_paths)):
            repo_path = repo_paths[i]
            repo_name = os.path.basename(os.path.normpath(repo_path)) # Get the repo name from the repo path

            print(f"\n{'='*60}")
            print(f"Processing repository {i+1}/{len(repo_paths)}: {repo_name}")
            print(f"{'='*60}")

            # For each of these chunking strategies, chunk and embed the docs and populate the table
            for strategy_num, chunking_strategy in enumerate(chunking_strategies, 1):
                print(f"\nStrategy {strategy_num}/{len(chunking_strategies)}: {chunking_strategy.name}")
                
                phase_start = time.time()
                main_branch = main_branches[i]
                internal_only_status = internal_only_statuses[i]

                # Get all the filepaths in the current repo
                print(f"\nPhase 1: Discovering documents in {repo_name}...")
                discovery_start = time.time()
                filepaths_dict = get_filepaths_in_local_repo(local_repo_path=repo_path,
                                                             file_names_to_ignore=DISALLOWED_FILENAMES, 
                                                             internal_only=internal_only_status) 
                                
                # Get the text and name of every file in the repo
                document_texts_dict = get_document_texts_and_names(filepaths_dict) 

                # Get the versions of all the files
                versions_dict = get_document_versions(path_to_repo=repo_path, document_dict=document_texts_dict, branch_name=main_branch) 

                document_dict = versions_dict

                filepaths = document_dict[FILEPATHS_KEY]
                document_dict[DOC_ID_KEY] = hash_list_of_strings(filepaths) # Hash the filepaths to get the document IDs
                
                discovery_time = time.time() - discovery_start
                print(f"Phase 1 completed in {discovery_time:.1f}s - found {len(filepaths)} documents")

                print(f"\nPhase 2: Chunking documents...")
                chunking_start = time.time()
                chunk_dictionary = chunk_documents(document_dict, 
                                                    chunking_strategy=chunking_strategy, 
                                                    rcts_chunk_size=rcts_chunk_size,
                                                    rcts_chunk_overlap=rcts_chunk_overlap, 
                                                    num_words_per_chunk=num_words_per_chunk, 
                                                    num_sentences_per_chunk=num_sentences_per_chunk)

                # Add the repo name to the dictionary
                chunk_dictionary[REPO_NAME_KEY] = [repo_name for i in range(len(chunk_dictionary[CHUNK_CONTENT_KEY]))] 
                
                chunking_time = time.time() - chunking_start
                print(f"Phase 2 completed in {chunking_time:.1f}s")

                print(f"\nPhase 3: Generating embeddings...")
                embedding_start = time.time()
                
                if persist_embeddings:
                    chunking_strategy_str = chunking_strategy.name.lower().replace('_', '-')
                    embeddings_filename = generate_embeddings_filename(repo_name, chunking_strategy_str, embeddings_format)
                    embeddings_file_path = os.path.join(embeddings_dir, embeddings_filename)
                    
                    if os.path.exists(embeddings_file_path):
                        print(f"Loading existing embeddings from {embeddings_file_path}...")
                        embeddings_dict = load_embeddings_from_file(embeddings_file_path, embeddings_format)
                        print(f"Successfully loaded {len(embeddings_dict.get(CHUNK_CONTENT_KEY, []))} cached embeddings")
                        embedding_time = time.time() - embedding_start
                        print(f"Phase 3 completed in {embedding_time:.1f}s (loaded from cache)")
                    else:
                        print("No cached embeddings found, generating new embeddings...")
                        embeddings_dict = embed_chunks(chunk_dictionary)
                        save_embeddings_to_file(embeddings_dict, embeddings_file_path, embeddings_format)
                        embedding_time = time.time() - embedding_start
                        print(f"Phase 3 completed in {embedding_time:.1f}s")
                else:
                    embeddings_dict = embed_chunks(chunk_dictionary)
                    embedding_time = time.time() - embedding_start
                    print(f"Phase 3 completed in {embedding_time:.1f}s")
                
                print(f"\nPhase 4: Populating database...")
                db_start = time.time()
                populate_table(embeddings_dict, table_name, batch_size)
                db_time = time.time() - db_start
                print(f"Phase 4 completed in {db_time:.1f}s")
                
                total_time = time.time() - phase_start
                print(f"\nStrategy {strategy_num} completed in {total_time:.1f}s total")


def get_chunking_strategy_from_env() -> ChunkingStrategy:
    """
    Maps environment variable string to ChunkingStrategy enum.
    
    Returns: ChunkingStrategy enum value based on environment configuration
    """
    strategy_name = settings.FIREBOLT_RAG_CHATBOT_CHUNKING_STRATEGY.upper()
    
    if strategy_name == "RECURSIVE_CHARACTER_TEXT_SPLITTING":
        return ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING
    elif strategy_name == "SEMANTIC_CHUNKING":
        return ChunkingStrategy.SEMANTIC_CHUNKING
    elif strategy_name == "BY_PARAGRAPH":
        return ChunkingStrategy.BY_PARAGRAPH
    elif strategy_name == "BY_SENTENCE":
        return ChunkingStrategy.BY_SENTENCE
    elif strategy_name == "BY_SENTENCE_WITH_SLIDING_WINDOW":
        return ChunkingStrategy.BY_SENTENCE_WITH_SLIDING_WINDOW
    elif strategy_name == "EVERY_N_WORDS":
        return ChunkingStrategy.EVERY_N_WORDS
    else:
        print(f"Warning: Unknown chunking strategy '{strategy_name}', defaulting to RECURSIVE_CHARACTER_TEXT_SPLITTING")
        return ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING


if __name__ == '__main__':

        """ This dictionary contains information about the repos containing the documents you want to use for RAG.
            It will be passed into `generate_embeddings_and_populate_table` as the `repo_dict` argument.

            To populate the table using one or more GitHub repos of documents, add the following to the corresponding lists in this dictionary:
                - The LOCAL path of the repo(s)
                - The name of the main branch of the repo(s)
                - Whether the repo(s) have documents that are internal to your organization, or user-facing 
                  documents that anyone can access. (True for internal, False for user-facing).
            
            The repo paths and main branches in the dictionary below are just placeholders and examples of how to do this. 
            You must replace them with the corresponding information for your own repos.
        """
        repo_dict = {REPO_PATHS_KEY: [os.path.join(os.path.normpath(LOCAL_GITHUB_PATH), "rag_dataset")],
                     MAIN_BRANCH_KEY: ["main"],
                     INTERNAL_ONLY_KEY: [False]}
        
        chunking_strategy = get_chunking_strategy_from_env()
        chunking_strategies = [chunking_strategy]
        
        generate_embeddings_and_populate_table(
            repo_dict=repo_dict, 
            batch_size=settings.FIREBOLT_RAG_CHATBOT_BATCH_SIZE,
            chunking_strategies=chunking_strategies, 
            rcts_chunk_size=settings.FIREBOLT_RAG_CHATBOT_CHUNK_SIZE, 
            rcts_chunk_overlap=settings.FIREBOLT_RAG_CHATBOT_CHUNK_OVERLAP,
            num_words_per_chunk=settings.FIREBOLT_RAG_CHATBOT_NUM_WORDS_PER_CHUNK,
            num_sentences_per_chunk=settings.FIREBOLT_RAG_CHATBOT_NUM_SENTENCES_PER_CHUNK,
            persist_embeddings=True, 
            embeddings_format="parquet",
            embeddings_dir="embeddings_cache"
        )



                                                                                                                    
    