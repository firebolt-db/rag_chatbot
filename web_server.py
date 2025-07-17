"""
This file starts a local web server for accessing the chatbot through a web UI.
"""

from flask import Flask, render_template, request
from run_llm import run_chatbot
import uuid
from constants import *

app = Flask(__name__)

""" The homepage of the website """
@app.route('/', methods=["GET"]) 
def index(): 
    session_id = str(uuid.uuid4()) # Generate a new session ID for this user

    return render_template('index.html', session_id=session_id) 


"""
This page is the start of a new chatbot session (where the user hasn't asked a question yet)
Function parameters: session_id - string: the unique ID of this chatbot session
"""
@app.route("/chatbot_session/<session_id>", methods=["GET"])
def new_chatbot_session(session_id):
    return render_template("new_chatbot_session.html", session_id=session_id)


"""
This page is for an existing chatbot session (where the user has already asked a question)
Function parameters: session_id - string: the unique ID of this chatbot session
(Note that "GET" is added to the methods in case the user tries to go to this URL by copy-pasting the link into the browser.
That would return a "Method Not Allowed" error if we didn't have the error page).
"""
@app.route("/chatbot_session/chatbot_response/<session_id>", methods=["POST", "GET"])
def existing_chatbot_session(session_id):
        # If the user tried to make a GET request to an existing chatbot session, display the error page
        if request.method == "GET":
             return render_template("error_page.html")
        
        # If it's a POST request, get the chatbot's response to the user's message
        else:
            customer_message = request.form.get('user_message', '').strip()
            
            if not customer_message:
                return render_template("error_page.html")
            """ Here, change the chunking_strategy argument by following the instructions in the README file. """
            llm_response = run_chatbot(user_question=customer_message, session_id=session_id, chat_history_dir = "chat_history", k=10,
                                        print_vector_search=True, chunking_strategy="Semantic chunking",
                                        similarity_metric=VectorSimilarityMetric.COSINE_SIMILARITY, is_customer=False)
            
            return render_template("chatbot_response.html", chatbot_response=llm_response, session_id=session_id)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
