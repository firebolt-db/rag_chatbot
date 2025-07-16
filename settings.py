"""
Centralized settings module for the RAG chatbot application.
Loads all environment variables from .env file using dotenv.
"""

import os
from dotenv import dotenv_values

_env_variables = dotenv_values(dotenv_path=".env")

FIREBOLT_RAG_CHATBOT_ENGINE = _env_variables.get("FIREBOLT_RAG_CHATBOT_ENGINE")
FIREBOLT_RAG_CHATBOT_DB = _env_variables.get("FIREBOLT_RAG_CHATBOT_DB")
FIREBOLT_RAG_CHATBOT_CLIENT_ID = _env_variables.get("FIREBOLT_RAG_CHATBOT_CLIENT_ID")
FIREBOLT_RAG_CHATBOT_CLIENT_SECRET = _env_variables.get("FIREBOLT_RAG_CHATBOT_CLIENT_SECRET")
FIREBOLT_RAG_CHATBOT_ACCOUNT_NAME = _env_variables.get("FIREBOLT_RAG_CHATBOT_ACCOUNT_NAME")
FIREBOLT_RAG_CHATBOT_TABLE_NAME = _env_variables.get("FIREBOLT_RAG_CHATBOT_TABLE_NAME")
FIREBOLT_RAG_CHATBOT_LOCAL_GITHUB_PATH = _env_variables.get("FIREBOLT_RAG_CHATBOT_LOCAL_GITHUB_PATH", "YOUR LOCAL GITHUB PATH HERE")

LOCAL_GITHUB_PATH = FIREBOLT_RAG_CHATBOT_LOCAL_GITHUB_PATH
if not os.path.exists(LOCAL_GITHUB_PATH) and os.path.exists('/github'):
    LOCAL_GITHUB_PATH = '/github'
