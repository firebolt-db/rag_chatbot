"""
This file runs the chatbot.
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_ollama.chat_models import ChatOllama
from langchain_core.messages import trim_messages, HumanMessage, AIMessage
from langchain_core.caches import BaseCache
from langchain_core.callbacks import Callbacks
from constants import *
from operator import itemgetter
from langchain_core.runnables import RunnablePassthrough
from vector_search import vector_search
import settings
import os
import time

ChatOllama.model_rebuild()

        
"""
Gets the chat message history for the chatbot, or creates it if it doesn't exist.
Parameters: 
    - session_id: ID of the conversation with the chatbot

Returns: the chat message history
"""
def get_session_history(session_id: str) -> BaseChatMessageHistory:
    store = {} # In-memory store for the chat history

    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id] # this should return an empty ChatMessageHistory


"""
Runs the chatbot once. 
Parameters:
    - user_question: the question the chatbot user asked
    - chat_history_dir: the directory to store the chat history files in 
    - chunking_strategy: the vector search will only retrieve chunks that have this chunking strategy 
    - k: how many chunks to retrieve in the vector search
    - similarity_metric: the similarity metric to use for vector search
    - print_vector_search: Whether to print the results of the vector search
    - is_customer: whether the person running the chatbot is a customer (if so, set it to True) or an employee (if so, set it to False)
    - session_id: the unique ID of the chatbot session 

Returns: the bot's response to the question
"""
def run_chatbot(user_question: str, session_id: str, chat_history_dir: str = "chat_history", chunking_strategy: str = None, 
                k: int = 10, similarity_metric: VectorSimilarityMetric = VectorSimilarityMetric.COSINE_SIMILARITY, 
                print_vector_search: bool = False, is_customer: bool = True) -> str:
        
        request_start_time = time.time()
        
        if chunking_strategy is None:
            from chunking_and_embedding import generate_chunking_strategy_string
            from constants import ChunkingStrategy
            
            strategy_name = settings.FIREBOLT_RAG_CHATBOT_CHUNKING_STRATEGY.upper()
            if strategy_name == "RECURSIVE_CHARACTER_TEXT_SPLITTING":
                strategy_enum = ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING
            elif strategy_name == "SEMANTIC_CHUNKING":
                strategy_enum = ChunkingStrategy.SEMANTIC_CHUNKING
            elif strategy_name == "BY_PARAGRAPH":
                strategy_enum = ChunkingStrategy.BY_PARAGRAPH
            elif strategy_name == "BY_SENTENCE":
                strategy_enum = ChunkingStrategy.BY_SENTENCE
            elif strategy_name == "BY_SENTENCE_WITH_SLIDING_WINDOW":
                strategy_enum = ChunkingStrategy.BY_SENTENCE_WITH_SLIDING_WINDOW
            elif strategy_name == "EVERY_N_WORDS":
                strategy_enum = ChunkingStrategy.EVERY_N_WORDS
            else:
                strategy_enum = ChunkingStrategy.RECURSIVE_CHARACTER_TEXT_SPLITTING  # default
            
            chunking_strategy = generate_chunking_strategy_string(strategy_enum)
        print(f"\n{'='*60}", flush=True)
        print(f"Processing chatbot request for session: {session_id}", flush=True)
        print(f"Question: {user_question}", flush=True)
        print(f"{'='*60}", flush=True)

        filename = os.path.join(chat_history_dir, f"{CHAT_HISTORY_FILENAME}_{session_id}.txt") # chat history filename for this session
            
        # Create the directory if it doesn't exist
        if not os.path.exists(chat_history_dir):
            os.mkdir(chat_history_dir)

        # Create the file if it doesn't exist
        if not os.path.exists(filename):
            open(filename, "w").close()

        model = ChatOllama(model=LLM_NAME, temperature=0, num_ctx=MAX_TOKENS) 
        chat_history = ChatMessageHistory() # Message history that saves & loads chat messages (in memory)
        
        """ 
        The prompt below is the one we used for the Firebolt chatbot. 
        You must replace it with your prompt for your own use case by changing the `prompt` variable to your prompt. 
        The `{context}` part of the prompt holds the context you will pass to the chatbot for RAG, 
        so you must keep that somewhere in the prompt.
        """
        prompt = ChatPromptTemplate.from_messages([   
                ("system",
                        """ 
                        You are a support chatbot for Firebolt Analytics, a data warehousing company. 
                        You are responsible for answering users' questions about how to use the Firebolt data warehouse.
                        Use the following pieces of retrieved context to answer the question.
                        Note that the question is Firebolt-specific. 
                        Make your answer, including any code, specific to Firebolt and not another data warehouse.
                        If the information needed to answer the question is not in the context or the conversation history with the user, 
                        say that you cannot answer the question. Keep your tone formal. Do not say that you were given context.

                        Context: 
                        {context}
                        """
                ),
                MessagesPlaceholder(variable_name="messages"),
        ])

        
        # Trims the messages to the last MAX_TOKENS tokens
        trimmer = trim_messages(
                max_tokens=MAX_TOKENS, 
                strategy="last",     # Keep the last <= MAX_TOKENS tokens of the messages.
                token_counter=model, # Use our model to count the tokens 
                allow_partial=False, # Don't allow partial messages to be kept
                start_on="human",    # After the system prompt, start on a human message 
                include_system=True  # Keep the system prompt in the messages
        )


        # Trim the messages before passing them to the prompt
        chain = (RunnablePassthrough.assign(messages=itemgetter("messages") | trimmer) | prompt | model)
        
        with_message_history = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="messages",
        )

        config = {"configurable": {"session_id": session_id}}

        print(f"\nPhase 1: Processing chat history...", flush=True)
        chat_history_start = time.time()
        # Write user message to chat history file, then read the whole chat history
        with open(filename, "a") as file:
            file.write(f"{CHAT_HISTORY_SEPARATOR}\nUser: {user_question}\n")

        with open(filename, "r") as file:
            chat_history_from_file = file.read()

        
        # Load all the messages from the file into the in-memory chat history
        for message in chat_history_from_file.split(f"{CHAT_HISTORY_SEPARATOR}"):
            message = message.strip() # Remove leading and trailing whitespace

            if message.startswith("User: "): # If the line starts with "User: ", it's a human message
                chat_history.add_user_message(HumanMessage(content=message.replace("User: ", "")))
            elif message.startswith("AI: "): # If it starts with "AI: ", it's an AI message
                chat_history.add_ai_message(AIMessage(content=message.replace("AI: ", "")))
        
        chat_history_time = time.time() - chat_history_start
        print(f"Phase 1 completed in {chat_history_time:.3f}s - processed {len(chat_history.messages)} messages", flush=True)


        print(f"\nPhase 2: Performing vector search...", flush=True)
        vector_search_start = time.time()
        # Get the context to pass into the prompt from vector search
        retrieved_chunks = vector_search(user_question, chunking_strategy=chunking_strategy, k=k, 
                                         similarity_metric=similarity_metric, is_customer=is_customer)
        vector_search_time = time.time() - vector_search_start
        print(f"Phase 2 completed in {vector_search_time:.3f}s - retrieved {len(retrieved_chunks)} chunks", flush=True)

        context_string = "" # the chunks from the vector search that we'll pass into the model

        if print_vector_search:
            print(f"\n\nVECTOR SEARCH RESULTS:", flush=True)

        for i in range(len(retrieved_chunks)): 
            chunk, similarity, doc_name = retrieved_chunks[i]
            context_string += (chunk + "\n\n")

            if print_vector_search:
                print(f"\n\n{'-'*20} Result #{i+1} | Document name: {doc_name} | Similarity: {round(similarity, 3)} {'-'*20}\n\n", flush=True)
                print(chunk, flush=True)


        print(f"\nPhase 3: Generating LLM response...", flush=True)
        llm_start = time.time()
        # Get the model's response
        response = with_message_history.invoke({"messages": chat_history.messages, "question": user_question, "context": context_string}, 
                                                config=config)
        llm_time = time.time() - llm_start
        print(f"Phase 3 completed in {llm_time:.3f}s - generated {len(response.content)} characters", flush=True)

        print(f"\nPhase 4: Saving response to chat history...", flush=True)
        save_start = time.time()
        # Write the LLM response to the chat history file
        with open(filename, "a") as file:
            file.write(f"{CHAT_HISTORY_SEPARATOR}\nAI: {response.content}\n")
        save_time = time.time() - save_start
        print(f"Phase 4 completed in {save_time:.3f}s", flush=True)

        total_time = time.time() - request_start_time
        print(f"\n{'='*60}", flush=True)
        print(f"Request completed in {total_time:.3f}s total", flush=True)
        print(f"  Chat history: {chat_history_time:.3f}s ({chat_history_time/total_time*100:.1f}%)", flush=True)
        print(f"  Vector search: {vector_search_time:.3f}s ({vector_search_time/total_time*100:.1f}%)", flush=True)
        print(f"  LLM response: {llm_time:.3f}s ({llm_time/total_time*100:.1f}%)", flush=True)
        print(f"  Save response: {save_time:.3f}s ({save_time/total_time*100:.1f}%)", flush=True)
        print(f"{'='*60}", flush=True)

        return response.content
