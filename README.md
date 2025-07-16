# rag_chatbot
This repository contains code and instructions for running your own Firebolt-powered chatbot that uses retrieval-augmented generation (RAG).

## Quick Start

### Option 1: Docker Setup (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd rag_chatbot

# Run the automated setup script
./setup.sh --docker

# Start the chatbot
docker-compose up -d

# View logs
docker-compose logs -f
```

### Option 2: Local Setup
```bash
# Clone the repository
git clone <repository-url>
cd rag_chatbot

# Run the automated setup script
./setup.sh --local

# Activate virtual environment
source .venv/bin/activate

# Start the chatbot
python web_server.py
```

### Option 3: Task-based Setup
If you have [Task](https://taskfile.dev/) installed:
```bash
# Install dependencies
task install-deps

# Setup Ollama models
task setup-ollama

# Start the server
task start-server
```

## Configuration
1. Copy `.env.example` to `.env` and fill in your Firebolt credentials
2. Update `LOCAL_GITHUB_PATH` in `constants.py` with your local GitHub path
3. Run `python populate_table.py` to populate your vector database

### Docker Setup for populate_table.py
When using Docker, you can populate the table using the following methods:

**Option 1: Using Task (Recommended)**
```bash
# This automatically detects Docker vs local setup
task populate
```

**Option 2: Direct Docker Command**
```bash
# Ensure your Docker services are running
docker compose up -d

# Run populate_table.py inside the container
docker compose exec rag_chatbot python populate_table.py
```

**Important Notes for Docker:**
- The `LOCAL_GITHUB_PATH` environment variable should point to your local GitHub repositories directory
- This directory is automatically mounted to `/github` inside the Docker container
- The script will automatically use `/github` as the base path when running in Docker
- Make sure your document repositories are cloned locally in the `LOCAL_GITHUB_PATH` directory before running

## Troubleshooting
- **GPU Support**: For Docker GPU support, ensure NVIDIA Docker runtime is installed
- **Ollama Models**: Models are automatically downloaded but may take time on first run
- **Port Conflicts**: Default ports are 5000 (web) and 11434 (Ollama)

---

# Prerequisites before setting up your chatbot
1. [Register for Firebolt](https://docs.firebolt.io/Guides/getting-started/index.html)
2. Create a database by following the instructions under the "Create a Database" section [here](https://docs.firebolt.io/Guides/getting-started/get-started-sql.html)
3. After you've created the database, Firebolt may have automatically created an engine called `my_engine`. If so, then you can use that engine to programatically access Firebolt. If not, then create an engine by following the instructions under the "Create an Engine" section [here](https://docs.firebolt.io/Guides/getting-started/get-started-sql.html).
4. Follow [these instructions](https://docs.firebolt.io/Guides/managing-your-organization/managing-accounts.html) to obtain the name of the account that Firebolt has prepared for you, or to create a new account if you would like to.
5. To set up your service account, follow the sections "Create a service account", "Get a service account ID", "Generate a secret", and "Create a user" under [these instructions](https://docs.firebolt.io/Guides/managing-your-organization/service-accounts.html)
    - It doesn't matter whether you designate the service account as an organization admin using the `Is organization admin?` toggle switch.
    - The instructions for creating a user are slightly different from the ones in the "Create a user" section on the website. Here are the differences:
        - The button in step 3 of those instructions is called `Create New User`
        - In step 4 of those instructions, to associate the user with a service account, select `Service Account` in the `Assign To` dropdown menu. Now, in the `Service account name` dropdown menu, select your service account. When selecting a role using the `Role` dropdown menu, you must select the `account_admin` role. It doesn't matter whether you associate the user with your engine and your database.
6. Optional: If you plan to use Firebolt after you've used up your initial free $200 credit, you may follow the instructions under the "Register through the AWS Marketplace" section [here](https://docs.firebolt.io/Guides/getting-started/get-started-next.html)
7. Make sure the machine where you're running this code has a GPU and that the GPU is being utilized. This is necessary for the chatbot to run quickly. Many local computers have GPUs, but if yours does not, you can host this code on an AWS EC2 instance with a GPU for faster runtime. The instructions below assume you're using your local machine.
8. Download Python 3.12 to your local machine, if it's not already downloaded
   
# How to set up and use your chatbot
1. Clone this GitHub repository to your local machine, and open the repository in Visual Studio Code
3. In Visual Studio Code, create a `.venv` virtual environment to run this project in
4. Download Ollama [here](https://ollama.com/download)
5. In your terminal, run `ollama pull llama3.1`. Then run `ollama pull nomic-embed-text`
6. Activate the virtual environment. Inside the virtual environment, run the following command to install all the required libraries: 
`pip install torch pydriller GitPython mistletoe bs4 langchain-community numpy langchain langchain-experimental nltk langchain-ollama uuid python-docx pandas langchain-core firebolt-sdk python-dotenv transformers flask`
7. Add your Firebolt service account credentials and other Firebolt connection information
    - Go to the `.env` file and set the environment variables to their correct values:
        - Set the `FIREBOLT_CLIENT_ID` variable to the ID of your service account
        - Set the `FIREBOLT_CLIENT_SECRET` to the secret of your service account
        - Set `FIREBOLT_ENGINE` to the name of your Firebolt engine
        - Set `FIREBOLT_DB` to the name of your Firebolt database
        - Set `FIREBOLT_ACCOUNT_NAME` to the name of the account that you obtained or created in step 4 of the "Prerequisities before setting up the chatbot" section
        - Set `FIREBOLT_TABLE_NAME` to the name that you would like your Firebolt table for the vector database to have. (That table does not have to already exist).
    - If any of the values or credentials in the `.env` file change, you will have to go to the `.env` file and change the appropriate environment variables.
8. Populate the Firebolt table with the documents you will use for RAG:
    - Put the documents in one or more GitHub repositories. Clone ALL of those repositories to your local machine.
    - Go to `constants.py` and set the `LOCAL_GITHUB_PATH` variable to the path to GitHub on your local machine. There must be no spaces in the string value of `LOCAL_GITHUB_PATH`
    - Optionally, you may specify files that you want the code for reading documents from the GitHub repos to ignore. To do so, go to `constants.py` and add the names of those files to the `DISALLOWED_FILENAMES` variable. For example, you might not want the README or the license to be in the Firebolt table. 
    - Go to `populate_table.py` and do the following:
        - In the main method, set the `chunking_strategies` variable to a list of one or more chunking strategies that you want to use to chunk the documents.
        - If needed, you may change the `batch_size`, `rcts_chunk_size`, `rcts_chunk_overlap`, `num_words_per_chunk`, and/or `num_sentences_per_chunk` arguments in the call to `generate_embeddings_and_populate_table()` 
        - Update the `repo_dict` variable in `populate_table.py` with your GitHub repos (see `populate_table.py` for information about how to do that)
            - The instructions in `populate_table.py` mention internal documents and user-facing documents. This may not be applicable to your use case. But, for the Firebolt chatbot, it was necessary to indicate whether each document was internal or user-facing. This is because our chatbot will be used by both employees and customers. So, if the user is a customer, we need to filter out the internal documents, and if the user is a Firebolt employee, we can keep them. If you also have some internal documents and some user-facing ones, and if both employees of your organization and public users will use your chatbot, you will have to appropriately specify which repos have internal or user-facing documents (respectively) in `populate_table.py`.
    - Now run `populate_table.py`. For local setup, run `python populate_table.py`. For Docker setup, see the "Docker Setup for populate_table.py" section above or use `task populate`. This will create and populate the Firebolt table. Make sure the table is done being populated before you do step 10 of these instructions.
9. Change the prompt given to the chatbot to suit your use case. To do so, change the `prompt` variable in the `run_chatbot()` function in `run_llm.py`. For example, if you are building a healthcare chatbot that answers medical questions, you might start the prompt with "You are a healthcare chatbot that assists medical professionals in answering questions...". Be sure to follow the instructions in the comments above that variable. 
10. To run a local web server where you can use the chatbot:
    - Do the following to pass the correct chunking strategy to the `run_chatbot()` function:
        - Run the following SQL query on your Firebolt table: `SELECT DISTINCT chunking_strategy FROM table_name;` (using the actual name of your table).
        - From the results of that query, choose the chunking strategy you would like the RAG system to use.
        - Go to `web_server.py`. In the line of code that calls `run_chatbot()`, set the `chunking_strategy` argument to the chunking strategy you want to use. This must be the exact string value of the chunking strategy that was returned from the Firebolt SQL query. For example, suppose that one of the results of the query is `"Recursive character text splitting with chunk size = 600 and chunk overlap = 125"`, and that this is the chunking strategy you want to use. Then, you must set the `chunking_strategy` argument to `"Recursive character text splitting with chunk size = 600 and chunk overlap = 125"`.
        - If you want, you may change the `k`, `similarity_metric`, `chat_history_dir`, and/or `print_vector_search` arguments in the call to `run_chatbot()` in `web_server.py`.
    - Run `web_server.py`
    - To go to the webpage, go to your browser and enter the URL `http://127.0.0.1:5000`
    - Use the web UI to interact with the chatbot. 
    - On the webpage, when you click the `Home Page` link in the middle of a conversation with the chatbot, the existing conversation will disappear. The next conversation with the chatbot will be a new conversation where the LLM does not remember the old conversation. 
    - If you refresh the page while the chatbot is generating its response, the chatbot may hallucinate.
    - If you try to type the URL `http://127.0.0.1:5000/chatbot_session/chatbot_response/<any session id here>` into the browser, that is not the correct way to access a chatbot session, so you will be taken to an error page. Instead, to start a new chatbot session, go to the homepage and click on the link there.

## Things to note about strings in Firebolt tables
- In your documents, be careful about special character sequences that cannot be loaded into Firebolt tables:
    - Documents that contain the null character cannot be read into Firebolt tables. This is because Firebolt tables cannot contain escape string literals with null characters in them. If any of your documents contain a null character, the code for populating the table will throw an error. To add those documents to the table, you must manually remove every occurrence of the null character from the documents.
    - If your documents contain Unicode character values, hexadecimal byte values, or octal byte values, make sure these characters are valid in Firebolt. If they are not valid, the code for populating the table will throw an error. To add those documents to the table, you must manually change the invalid characters to valid ones. 
        - See [this link](https://docs.firebolt.io/sql_reference/data-types.html#text) for information about what constitutes a valid Unicode, hexadecimal, or octal character.

## Things to note about the code
- If a document contains images, those images will not be read into the Firebolt table or used by the chatbot.
- Only documentation files with the following extensions are supported: `.docx`, `.txt`, `.md`.
- The documents in each GitHub repository must be either ALL internal or ALL user-facing. If one repo has both internal and user-facing documents, then every time after you run `populate_table.py`, you will have to write and run a Firebolt SQL query to manually change the values in the `internal_only` column where appropriate.
- This code does not detect if the chatbot user is an employee of your organization or an external user. The code assumes the user is an employee. Therefore, internal documents can be passed to the chatbot. If the user of your chatbot is a customer, you will have to change the code manually:
    - Go to `web_server.py`
    - In the `run_chatbot` function, change the value of the `is_customer` argument from `False` to `True`.

## Things you must do to prevent execution errors:
- Make sure that every Markdown file in your documents has valid Markdown syntax. If there is a Markdown file with invalid syntax (e.g., not closing parentheses), the Firebolt SDK will throw an error when you try to insert that document into the table. 

# Example Dataset

We have provided an example dataset that you can use to build your chatbot! You can find the dataset at [this GitHub repository](https://github.com/firebolt-analytics/rag_dataset), and it contains documentation for HuggingFace Transformers.
