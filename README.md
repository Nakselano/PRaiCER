# PRaiCER - Intelligent AI Shopping Assistant 🛒

## 🛠️ Technologies and Requirements

* **Backend:** Python 3.10, FastAPI, SQLModel (PostgreSQL)
* **AI/LLM:** Google Gemini Pro / Groq (Llama 3), LangChain (concept), SentenceTransformers
* **Frontend:** Streamlit
* **Tools:** Docker, Docker Compose, SerpApi

---

## ⚙️ Installation and Setup

### Method 1: Docker (Recommended) 🐳

Requires Docker Desktop installed.

1.  Clone the repository.
2.  Copy the `.env.template` file to `.env` and fill in the API keys (Gemini/Groq/SerpApi):
    ```bash
    cp .env.template .env
    ```
3.  Start the environment:
    ```bash
    docker-compose up --build
    ```
4.  Open the application in your browser:
    * **Frontend:** [http://localhost:8501](http://localhost:8501)
    * **Backend Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### Method 2: Local (Python) 🐍

Requires Python 3.10+ and a running PostgreSQL database.

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Set variables in `.env` (DATABASE_URL must point to your database).
3.  Start Backend:
    ```bash
    uvicorn main:app --reload --port 8000
    ```
4.  Start Frontend (in a new terminal):
    ```bash
    streamlit run frontend.py
    ```
