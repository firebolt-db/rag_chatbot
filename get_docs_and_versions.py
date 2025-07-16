"""
This file gets the documents used for RAG, their filepaths, and their versions from your local GitHub repository. It also extracts the text from the documents.
"""

import os
from pydriller import Repository
import git
import re
from constants import *
import copy
from file_parsing import extract_text_from_docx, extract_text_from_txt, extract_text_from_markdown
import pandas as pd
from pathlib import Path

"""
Get the paths of all the files in one of your document repos.

Parameters: 
    - local_repo_path: the path to the document repo on your LOCAL machine 
    - file_names_to_ignore: the names of any files that you don't want to read in. 
                            For example, passing "README.md" will read all the files except README.md.
    - internal_only: whether the repo contains documents that are internal to your company (True) or public documents (False)

Returns: A dictionary with the following keys and values:
    - key: 'filepath', value: a list of the paths to all the files that will be used for RAG in the repo
    - key: 'internal_only', value: for each filepath, whether that file is internal only or not

Precondition: For local_repo_path, you must pass the path to the repo on your local machine, NOT a URL to the repo on GitHub.
"""
def get_filepaths_in_local_repo(local_repo_path: str, file_names_to_ignore: list[str] = DISALLOWED_FILENAMES, internal_only: bool = False) -> dict:
                                
    file_paths = [] # all filepaths in the repo
    repo_name = os.path.basename(os.path.normpath(local_repo_path)) # Get the repo name from the repo path

    for entry in os.listdir(local_repo_path):
            full_path = os.path.join(local_repo_path, entry) # get the full path of each entry in the `local_repo_path` directory

            # Recursive case: If the entry is a directory, append all the contents in that directory by calling this function recursively
            if os.path.isdir(full_path):
                lowest_directory = os.path.basename(full_path) # Only the last directory in the directory tree
                
                dictionary = get_filepaths_in_local_repo(full_path, file_names_to_ignore, internal_only)
                file_paths.extend(dictionary[FILEPATHS_KEY])
            
            # Base case: If the entry is a file, we are done with the recursion; just append the filepath to the `file_paths`
            else:
                root, extension = os.path.splitext(full_path)
                lowest_directory = os.path.basename(os.path.dirname(full_path)) # Get the directory that the file is in

                # Add this filepath if it's in the list of allowed file extensions and not in the list of disallowed filenames.
                if extension in ALLOWED_FILE_EXTENSIONS and entry not in file_names_to_ignore:
                    file_paths.append(full_path)

            
    # Indicate whether each file is internal only and which repo the file is from
    return_dict = {FILEPATHS_KEY: file_paths, INTERNAL_ONLY_KEY: [internal_only for i in range(len(file_paths))]}

    return return_dict


"""
Get a list of all the text and all the document names from a list of documents, and write each text to a text file

Parameters: 
    - filepaths_dict: The dictionary returned from get_filepaths_in_local_repo()
    - indicate_md_tables: whether to indicate tables in Markdown files. 
                          If true, every table in a Markdown file will have the word "Table:" above it in the parsed text.
                          If false, it will not.
    - md_table_separator: the separator for items in a Markdown table row
   
Returns: A dictionary with the following keys and values:
            - key: 'filepath', value: a list of all the filepaths in the repo
            - key: 'internal_only', value: for each filepath, whether that file is internal only or not
            - key: 'document_text', value: the text in each file in the 'filepath' list
            - key: 'document_name', value: a list of filenames of all the docs (with no directory prefixes)                                                        
"""
def get_document_texts_and_names(filepaths_dict: dict, indicate_md_tables: bool = True, md_table_separator: str = ",") -> dict:
    document_texts = []
    document_names = []
    filepaths = filepaths_dict[FILEPATHS_KEY]
    
    print(f"\nExtracting text from {len(filepaths)} documents...")

    for i, filepath in enumerate(filepaths):
        if i % 20 == 0 or i == len(filepaths) - 1:
            print(f"  Processing document {i+1}/{len(filepaths)}: {os.path.basename(filepath)}")
        # Append the file to the list of returned files only if it's a file format that we can read
        document_text = get_text_from_document(filepath, indicate_md_tables, md_table_separator)
        document_texts.append(document_text)

        _, filename = os.path.split(filepath) # Get the filename (the head is the part of the path before the filename)
        filename_root, _ = os.path.splitext(filename) # Get the root and the extension of the filename

        document_names.append(filename)

    temp_dict = copy.deepcopy(filepaths_dict)
    temp_dict[DOC_TEXTS_KEY] = document_texts
    temp_dict[DOC_NAME_KEY] = document_names

    # Remove all the documents that have empty text from the dictionary. 
    # (Empty text means the text in that file should not be part of the documentation)
    df = pd.DataFrame.from_dict(temp_dict)
    df_non_empty = df.loc[df[DOC_TEXTS_KEY] != ""]

    return_dict = df_non_empty.to_dict(orient="list")
    return return_dict

"""
Gets the document version (which is the commit hash) of all the files in the document repo that will be used for RAG
Parameters:
    - path_to_repo: The path to the repo with the documents on your local machine
    - document_dict: The dictionary returned from get_document_texts_and_names()
    - branch_name: the branch you want to get the documents from. 
    
Returns: A dictionary with the following keys and values:
            - key: 'filepath', value: the list of filepaths passed in
            - key: 'internal_only', value: for each filepath, whether that file is internal only or not
            - key: 'document_texts', value: the text in each file in the 'filepath' list
            - key: 'document_name', value: a list of filenames of all the docs (with no directory prefixes)
            - key: 'document_version', value: the list of versions for the filepaths
            
Preconditions: 
    1. You must clone the repo to your local machine before calling this function.
    2. When running "git diff --name-status" on commits in the repo, the status of every file in every commit must be one of the following: 
        A (added), D (deleted), M (modified), or R (renamed). Other statuses are not supported.
"""
def get_document_versions(path_to_repo: str, document_dict: dict, branch_name: str = "main") -> dict: 
    versions_dict = copy.deepcopy(document_dict)
    filepaths = versions_dict[FILEPATHS_KEY]
    versions_dict[DOC_VERSION_KEY] = [None for i in range(len(filepaths))]
    versions = versions_dict[DOC_VERSION_KEY] 

    print(f"\nGetting the document versions for {len(filepaths)} files...")
    commits_processed = 0

    # Use 'reverse' to get the commits from the newest to the oldest. Use only_in_branch to get only the commits from the specified branch
    for commit in Repository(path_to_repo=path_to_repo, order='reverse', only_in_branch=branch_name).traverse_commits():
        commits_processed += 1
        if commits_processed % 100 == 0:
            remaining_files = sum(1 for v in versions if v is None)
            print(f"  Processed {commits_processed} commits, {remaining_files} files still need versions")
        modified_file_paths = [] # paths of files that were modified by this commit

        # Need to handle merge commits separately because commit.modified_files may be an empty list for merge commits
        if commit.merge:
            changed_files_string = get_commit_diff(path_to_repo, commit.hash)
            changed_files_list = changed_files_string.split("\n") # split by newline to get a list of strings containing a filename and modification type

            if changed_files_list != ['']:
                for changed_file in changed_files_list:
                    modification_type_and_filename = tuple(changed_file.split("\t")) # Split by tab to get filename and modification type separately

                    # the tuple has 2 elements if the file modification was not a rename: handle this case
                    if(len(modification_type_and_filename)) == 2:
                        modification_type, filename = modification_type_and_filename

                        # Add the file to the list of modified files only if it was not deleted in this commit (we don't need the doc version for deleted files)
                        if modification_type != "D":
                            path = os.path.join(path_to_repo, filename)
                            modified_file_paths.append(path)
                    
                    # it has 3 elements if the file modification was a rename: handle this case separately
                    elif modification_type_and_filename[0].startswith("R"):
                        modification_type, original_filename, new_filename = modification_type_and_filename
                        path = os.path.join(path_to_repo, new_filename)
                        modified_file_paths.append(path)

        else: 
            # Get the paths of the modified files for this commit
            for modified_file in commit.modified_files:

                # Add the file to the list of modified files only if it was not deleted in this commit
                if modified_file.change_type.name != "DELETE":
                    path = os.path.join(path_to_repo, modified_file.new_path)
                    modified_file_paths.append(path)

        # If the file was modified in this commit and it doesn't already have a version, set the version to the hash of this commit
        # (This works since the commits are ordered from most recent to least recent)
        for i in range(len(filepaths)):
            if filepaths[i] in modified_file_paths and versions[i] is None:
                versions_dict[DOC_VERSION_KEY][i] = commit.hash

        # If all the docs already have a version, we don't have to go through the rest of the commits
        if not (None in versions_dict[DOC_VERSION_KEY]):
            print(f"Done getting the document versions (processed {commits_processed} commits)")
            return versions_dict
        
    print(f"Done getting the document versions (processed {commits_processed} commits)")
    return versions_dict

"""
Gets the list of files modified by a merge commit. (Helper function for get_document_versions())
Parameters:
    - path_to_repo: the local path to the repo (you must clone the repo to your local machine before calling this function)
    - merge_commit_hash: the hash of the commit
"""
def get_commit_diff(path_to_repo: str, merge_commit_hash):
    repo = git.Repo(path_to_repo)

    # Get the files changed between the merge commit's first parent and the merge commit (the first parent is the branch that the commit was merged into)
    return repo.git.diff(merge_commit_hash+"^", merge_commit_hash, name_status=True)

"""
Returns the text from a single document
Parameters: 
    - filepath: the path to the file we're getting the text from
    - indicate_md_tables, md_table_separator: see the docstring for get_document_texts_and_names() for info about these
Returns: the text in the document
"""
def get_text_from_document(filepath: str, indicate_md_tables: bool = True, md_table_separator: str = ",") -> str:
    relative_filepath = Path(os.path.relpath(path=filepath, start=LOCAL_GITHUB_PATH)) # Relative path of the file with respect to the local GitHub path
    path_parts = relative_filepath.parts # get all the components of the path
    repo_name = path_parts[0] # get the name of the repo

    if filepath.endswith('.docx'):
        document_text = extract_text_from_docx(filepath)
    elif filepath.endswith('.txt'):
        document_text = extract_text_from_txt(filepath)
    elif filepath.endswith('.md'):
        document_text = extract_text_from_markdown(filepath, indicate_tables=indicate_md_tables, table_separator=md_table_separator)
    else: # Don't parse other file types
        document_text = ""

    document_text = document_text.replace("'", "''") # replace every single quote (') with two single quotes ('') to prevent a syntax error when populating the FB table
    document_text = document_text.replace("\\", "\\\\") # replace backslashes to prevent a syntax error when populating the table
    document_text = re.sub(r"\\u", r"\\\\u", document_text) # Find Unicode characters and format them so that we can put them in a Firebolt table with no errors
    
    return document_text

