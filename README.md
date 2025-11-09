# Realtime Chat Server

This is a full-featured, realtime chat application built with FastAPI, Socket.IO, and MongoDB. It includes secure authentication, one-to-one and group chats, a persistent message store, and an integrated AI assistant with web search capabilities.

## Features

- **Realtime Messaging**: Instant communication using WebSockets (Socket.IO).
- **Multiple Chat Options**:
  - **One-to-One (DM)**: Private conversations between two users.
  - **Group Chat**: Conversations with multiple participants.
- **Secure Authentication**:
  - User signup and login.
  - Secure token-based authentication using HttpOnly cookies (Access & Refresh tokens).
  - Full "Forgot Password" flow with OTP email verification.
- **Persistent Storage**: All users, chats, and messages are stored in a MongoDB database.
- **AI Assistant**:
  - A built-in AI chat assistant available to all users.
  - Uses LangGraph to decide between regular chat and performing a web search for up-to-date answers.
  - Persistent conversation history with the AI.

## Tech Stack

- **Backend**:
  - **Framework**: FastAPI
  - **Realtime**: `python-socketio`
  - **Database**: MongoDB with `motor` (async driver in place of pymongo)
  - **AI**: `langchain`, `langgraph`, `groq` for LLM inference, `tavily-python` for web search.
  - **Authentication**: `python-jose` for JWTs, `passlib` for hashing with bcrypt backend.
- **Frontend**:
  - Plain HTML, CSS, and JavaScript.
  - **Styling**: TailwindCSS
  - **Realtime**: `socket.io-client`

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/EngineerLambda/realtime-chat
    cd realtime-chat
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**
    Create a `.env` file in the project root and add the following variables. A MongoDB instance is required.

    ```env
    # --- Database & App ---
    MONGO_URI="mongodb://localhost:27017" # change for your own mongo connection string
    MONGO_DB="realtime_chat"
    JWT_SECRET="a_very_secret_key_for_jwt_tokens" # 32 bytes hex string generated. Can be generated using: `openssl rand -hex 32`.

    # --- AI Services (Required for AI Assistant) ---
    GROQ_API_KEY="your_groq_api_key" # Gotten from https://groq.com/
    TAVILY_API_KEY="your_tavily_api_key" # Gotten from https://tavily.com/

    # --- Email Service from https://www.zoho.com (Required for Forgot Password) ---
    ZOHO_SMTP_SERVER="smtp.zoho.com"
    ZOHO_SMTP_PORT="465"
    ZOHO_EMAIL="your_email@zoho.com"
    ZOHO_APP_PASSWORD="your_zoho_app_specific_password"
    ```

## Running the Application

Run the development server using Uvicorn:

```bash
uvicorn app.main:app --reload
```

- The application will be available at `http://127.0.0.1:8000`.
- The interactive API documentation (Swagger UI) is at `http://127.0.0.1:8000/docs`.