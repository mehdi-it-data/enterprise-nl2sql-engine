+------------------------+
                   |   User Query (UI)      |
                   +-----------+------------+
                               |
                               v
                   +------------------------+
                   |  ChromaDB Vector Store | (Retrieves Schema Context)
                   +-----------+------------+
                               |
                               v
                   +------------------------+
                   |  LLM Engine (Ollama)   | (Generates SQL Query)
                   +-----------+------------+
                               |
                               v
                   +------------------------+
                   |   SQLite Database      | (Executes Query)
                   +-----------+------------+
                               |
            +------------------+------------------+
            | Success                             | Error
            v                                     v
+------------------------+            +------------------------+
|  Streamlit Display     |            | Self-Correction Loop   |
+------------------------+            +------------------------+



enterprise-nl2sql-engine/
│
├── chroma_db/                # Local ChromaDB vector database storage
├── raw/                      # Raw data and CSV files
├── src/                      # Source code directory
│   ├── app.py                # Streamlit web application interface
│   ├── llm_engine.py         # Multi-stage LLM pipeline and self-correction
│   └── database.py           # SQLite connection and query execution handler
│
├── .env                      # Environment configuration
├── .gitignore                # Git ignore configuration
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation