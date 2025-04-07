"""
This file populates the Firebolt table with the documents you are using for RAG.
"""

from get_docs_and_versions import get_filepaths_in_local_repo, get_document_versions, get_document_texts_and_names
from vector_search import populate_table
from chunking_and_embedding import chunk_documents, embed_chunks, hash_list_of_strings
from constants import *
import os
from dotenv import dotenv_values


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

Returns: nothing
"""
def generate_embeddings_and_populate_table(repo_dict: dict, chunking_strategies: list[ChunkingStrategy], batch_size: int = 100,
                                            rcts_chunk_size: int = 600, rcts_chunk_overlap: int = 125, 
                                            num_words_per_chunk: int = 100, num_sentences_per_chunk: int = 3) -> None:
        repo_paths = repo_dict[REPO_PATHS_KEY]
        main_branches = repo_dict[MAIN_BRANCH_KEY]
        internal_only_statuses = repo_dict[INTERNAL_ONLY_KEY]

        # Get Firebolt table name from .env file
        env_variables = dotenv_values(dotenv_path=".env") # A dictionary containing the content of the .env file
        table_name = env_variables["FIREBOLT_TABLE_NAME"]    
        
        for i in range(len(repo_paths)):
            repo_path = repo_paths[i]
            repo_name = os.path.basename(os.path.normpath(repo_path)) # Get the repo name from the repo path

            # For each of these chunking strategies, chunk and embed the docs and populate the table
            for chunking_strategy in chunking_strategies:
                main_branch = main_branches[i]
                internal_only_status = internal_only_statuses[i]

                # Get all the filepaths in the current repo
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

                chunk_dictionary = chunk_documents(document_dict, 
                                                    chunking_strategy=chunking_strategy, 
                                                    rcts_chunk_size=rcts_chunk_size,
                                                    rcts_chunk_overlap=rcts_chunk_overlap, 
                                                    num_words_per_chunk=num_words_per_chunk, 
                                                    num_sentences_per_chunk=num_sentences_per_chunk)

                # Add the repo name to the dictionary
                chunk_dictionary[REPO_NAME_KEY] = [repo_name for i in range(len(chunk_dictionary[CHUNK_CONTENT_KEY]))] 

                embeddings_dict = embed_chunks(chunk_dictionary) # Get the embeddings
                populate_table(embeddings_dict, table_name, batch_size) 


if __name__ == '__main__':

        """ This dictionary contains information about the repos containing the documents you want to use for RAG.
            It will be passed into `generate_embeddings_and_populate_table` as the `repo_dict` argument.

            To populate the table using one or more GitHub repos of documents, add the following to the corresponding lists in this dictionary:
                - The LOCAL path of the repo(s)
                - The name of the main branch of the repo(s)
                - Whether the repo(s) have documents that are internal to your organization, or user-facing 
                  documents that anyone can access. (True for internal, False for user-facing).
            
            The repo paths and main branches in the dictionary below are just placeholders. 
            You must replace them with the corresponding information for your own repos.
        """
        repo_dict = {REPO_PATHS_KEY: [os.path.join(LOCAL_GITHUB_PATH, "repo_name_1"), os.path.join(LOCAL_GITHUB_PATH, "repo_name_2")], 
                     MAIN_BRANCH_KEY: ["main_branch_1", "main_branch_2"], 
                     INTERNAL_ONLY_KEY: [False, True]}
        
        chunking_strategies = [ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING]
        
        generate_embeddings_and_populate_table(repo_dict=repo_dict, batch_size=100,
                                               chunking_strategies=chunking_strategies, 
                                               rcts_chunk_size = 600, rcts_chunk_overlap=0)

                                                                                                                                       
    