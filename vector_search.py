"""
This file populates the Firebolt table and performs vector search.
"""

from firebolt.db import connect
from firebolt.db.connection import Connection
from firebolt.db.cursor import CursorV2
from dotenv import load_dotenv, dotenv_values
from firebolt.client.auth import ClientCredentials
from constants import *
from chunking_and_embedding import embed_question
import pandas as pd

"""
Connect to Firebolt using the credentials from the .env file
Parameters: none
Returns: a Firebolt Connection object and a Firebolt Cursor object. 
         Make sure to close the Connection and Cursor objects when you're done using them.
"""
def connect_to_firebolt() -> tuple[Connection, CursorV2]:
    env_variables = dotenv_values(dotenv_path=".env") # A dictionary containing the content of the .env file

    # Connect to Firebolt using a service account
    connection = connect(
        engine_name=env_variables["FIREBOLT_ENGINE"],
        database=env_variables["FIREBOLT_DB"],
        auth=ClientCredentials(env_variables["FIREBOLT_CLIENT_ID"], env_variables["FIREBOLT_CLIENT_SECRET"]),
        account_name=env_variables["FIREBOLT_ACCOUNT_NAME"]
    )

    return connection, connection.cursor()


"""
Creates the Firebolt table that stores the embeddings, if it doesn't already exist. Does nothing if it exists
Parameters: 
    - table_name: the name of the table that stores the embeddings
"""
def create_table_if_not_exists(table_name: str) -> None:
    connection, cursor = connect_to_firebolt()

    # Execute a query to create the table
    cursor.execute( 
        f"""
            CREATE TABLE IF NOT EXISTS {table_name}(
                {DOC_ID_COL} TEXT NOT NULL,
                {DOC_NAME_COL} TEXT NOT NULL,
                {DOC_VERSION_COL} TEXT NOT NULL, 
                {REPO_NAME_COL} TEXT NOT NULL,
                {CHUNK_CONTENT_COL} TEXT NOT NULL,
                {CHUNK_ID_COL} TEXT NOT NULL,
                {CHUNKING_STRATEGY_COL} TEXT NOT NULL,
                {EMBEDDING_COL} ARRAY(FLOAT NOT NULL) NOT NULL,
                {EMBEDDING_MODEL_COL} TEXT NOT NULL,
                {DATE_GENERATED_COL} DATE NOT NULL,
                {INTERNAL_ONLY_COL} BOOLEAN NOT NULL
            ) PRIMARY INDEX {DATE_GENERATED_COL}, {DOC_ID_COL}
        """
    )

    cursor.close()
    connection.close()

"""
Populates the Firebolt table with the embeddings (and the other data we need about the embeddings, like doc version, etc.)
Parameters:
    - data_dict: The dictionary returned from embed_chunks(). It contains all the data to populate the table with. 
    - table_name: name of the Firebolt table to populate
    - batch_size: Number of rows to insert into the Firebolt table at a time. 
                    (e.g.: batch_size = 100 will insert your data into the table in batches of 100 rows at a time).

Returns: nothing, but populates the table with the data in `data_dict`

Preconditions: 
    1. If the table `table_name` already exists in the database, it must have the following schema, in the following order:
                 "document_id" TEXT NOT NULL, "document_name" TEXT NOT NULL, "document_version" TEXT NOT NULL, 
                 "repo_name" TEXT NOT NULL, "chunk_content" TEXT NOT NULL, "chunk_id" TEXT NOT NULL, 
                 "chunking_strategy" TEXT NOT NULL, "embedding" ARRAY(FLOAT NOT NULL) NOT NULL, 
                 "embedding_model" TEXT NOT NULL, "date_generated" DATE NOT NULL, "internal_only" BOOLEAN NOT NULL

    2. All the data in `data_dict` must be non-null
"""

def populate_table(data_dict: dict, table_name: str, batch_size: int) -> None:
    create_table_if_not_exists(table_name) # Create the table if it doesn't already exist

    # Make sure the dictionary keys are in the same order as the table columns by making a new dictionary with the keys in that order
    ordered_data_dict = {}

    for dict_key in [DOC_ID_KEY, DOC_NAME_KEY, DOC_VERSION_KEY, REPO_NAME_KEY, 
                     CHUNK_CONTENT_KEY, CHUNK_ID_KEY, CHUNKING_STRATEGY_KEY, EMBEDDING_KEY, 
                     EMBEDDING_MODEL_KEY, DATE_GENERATED_KEY, INTERNAL_ONLY_KEY]:
        ordered_data_dict[dict_key] = data_dict[dict_key]

    connection, cursor = connect_to_firebolt()
    
    print("\nPopulating the table...")

    df = pd.DataFrame.from_dict(ordered_data_dict) # Make a DataFrame from the dictionary
    num_rows = len(df)                             # Number of rows to insert into the Firebolt table

    print(f"Number of rows being inserted: {num_rows}")

    # If the batch size is more than the number of rows in the table, or if it's less than 1, set it to a default value of 100
    if batch_size > num_rows or batch_size < 1:
        batch_size = 100

    # Insert data into the table in batches of `batch_size` rows at a time        
    for i in range(0, num_rows, batch_size):
        row_values = [] # The next batch of rows to insert

        # If there are at least `batch_size` rows left, insert the next `batch_size` rows
        if num_rows - i >= batch_size:
            rows = df.iloc[i:i+batch_size, :].to_numpy().tolist()

        # If there are less than `batch_size` rows left, insert all the remaining rows
        else: 
            rows = df.iloc[i:, :].to_numpy().tolist()

        # Convert the batch of rows into the correct format for inserting them into the Firebolt table.
        for row in rows:
            row_tuple = tuple(row) # Convert each row to a tuple

            # Unpack the tuple to get all the individual elements
            doc_id, doc_name, doc_version, repo_name, \
                chunk_content, chunk_id, chunking_strategy, embedding, \
                embedding_model, date_generated, internal_only = row_tuple

            # If the chunk does not contain only whitespace characters, 
            # put the row in the correct format for inserting it into the table, and add it to the batch of rows
            if not chunk_content.isspace():
                row_values.append(f"(E'{doc_id}', E'{doc_name}', E'{doc_version}', E'{repo_name}', \
                                     E'{chunk_content}', E'{chunk_id}', E'{chunking_strategy}', {embedding}, \
                                     E'{embedding_model}', E'{date_generated}', {internal_only})")
            
        # Execute a SQL query to insert the batch of rows all at once
        cursor.execute(f"INSERT INTO {table_name} VALUES " + ", ".join(row_values) + ";")

    cursor.close()
    connection.close()

    print("Done populating the table.")

"""
Performs vector search and returns the top k most similar rows to the user's question.
Parameters:
    - question: the user's question 
    - k: how many chunks to return
    - chunking_strategy:
            The chunking strategy of the chunks you want to retrieve.
            (e.g.: passing "Semantic chunking") only retrieves chunks that were chunked with semantic chunking.
            This parameter MUST be a string that exists in the `chunking_strategy` column of your Firebolt table. 
            To see what chunking strategies are in the table, run the following query in your Firebolt database: 
            `select distinct(chunking_strategy) from table_name;` (where table_name is the actual name of your table).
    - similarity_metric: the similarity metric to use for vector search
    - is_customer: whether the person using the chatbot is a customer (True) or an employee (False).
                            
Returns: a nested list of the k most similar rows.
         Each inner list corresponds to a row and contains the chunk content (str), document name (str), 
         and the value of the similarity metric (float) for that row.
"""
def vector_search(question: str, k: int, chunking_strategy: str, 
                    similarity_metric: VectorSimilarityMetric, is_customer: bool = True) -> list[list]:
    
    question_vector = embed_question(question) # Make an embedding of the question

    # Get Firebolt table name from .env file
    env_variables = dotenv_values(dotenv_path=".env") # A dictionary containing the content of the .env file
    table_name = env_variables["FIREBOLT_TABLE_NAME"]    
        
    connection, cursor = connect_to_firebolt()
    
    # Set the Firebolt function to call for the similarity metric
    if similarity_metric is VectorSimilarityMetric.COSINE_DISTANCE: 
        similarity_function = "VECTOR_COSINE_DISTANCE"
    elif similarity_metric is VectorSimilarityMetric.COSINE_SIMILARITY: 
        similarity_function = "VECTOR_COSINE_SIMILARITY"

    elif similarity_metric is VectorSimilarityMetric.EUCLIDEAN_DISTANCE: 
        similarity_function = "VECTOR_EUCLIDEAN_DISTANCE"
    elif similarity_metric is VectorSimilarityMetric.INNER_PRODUCT:
        similarity_function = "VECTOR_INNER_PRODUCT"

    elif similarity_metric is VectorSimilarityMetric.MANHATTAN_DISTANCE: 
        similarity_function = "VECTOR_MANHATTAN_DISTANCE"
    else: # if the similarity metric is VectorSimilarityMetric.SQUARED_EUCLIDEAN_DISTANCE 
        similarity_function = "VECTOR_SQUARED_EUCLIDEAN_DISTANCE"

    # Return results in ascending or descending order, depending on the similarity metric
    order = "DESC" if (similarity_function == "VECTOR_INNER_PRODUCT" or similarity_function == "VECTOR_COSINE_SIMILARITY") else "ASC"

    # Select the top k rows that are the most similar to the question vector. If the user is a customer, search only non-internal docs
    query = f"""SELECT {CHUNK_CONTENT_COL}, 
                       {similarity_function}({question_vector}, {EMBEDDING_COL}), 
                       {DOC_NAME_COL}
                FROM {table_name} 
                WHERE {CHUNKING_STRATEGY_COL} = '{chunking_strategy}' 
                       AND {INTERNAL_ONLY_COL} = FALSE 
                       AND {EMBEDDING_MODEL_COL} = '{EMBEDDING_MODEL_NAME}'
                ORDER BY {similarity_function}({question_vector}, {EMBEDDING_COL}) {order}
                LIMIT {k};"""
    
    # If the user is not a customer, we can use internal docs. So, remove the part of the query that filters on `INTERNAL_ONLY_COL`
    if not is_customer:
        query = query.replace(f" AND {INTERNAL_ONLY_COL} = FALSE", "")

    cursor.execute(query)
    result = cursor.fetchall()

    cursor.close()
    connection.close()

    return result

