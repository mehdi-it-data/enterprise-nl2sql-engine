# Enterprise NL2SQL Engine

An enterprise-grade, research-oriented Natural Language to SQL (NL2SQL) engine powered by **ChromaDB (Schema-RAG)**, **Ollama (`qwen2.5-coder`)**, **AST Read-Only Guardrails (`sqlglot`)**, **Schema Grounding Validation**, and **SQLite (BIRD-Benchmark)**.

## System Architecture

```text
+-----------------------+
|    User Query (UI)    |
+-----------+-----------+
            |
            v
+-----------------------+
| ChromaDB Vector Store | (Retrieves Schema Context)
+-----------+-----------+
            |
            v
+-----------------------+
|  LLM Engine (Ollama)  | (Generates SQL Query)
+-----------+-----------+
            |
            v
+-----------------------+
|   SQLite Database     | (Executes Query)
+-----------+-----------+
            |
     +------+------+
     |             |
     v             v
+---------+   +---------+
| Success |   |  Error  |
+----+----+   +----+----+
     |             |
     |             v
     |      +-----------------+
     |      | Self-Correction |
     |      |      Loop       |
     |      +------+----------+
     |             |
     +------+------+
            |
            v
+-----------------------+
|   Streamlit Display   |
+-----------------------+

Project Structure

enterprise-nl2sql-engine/
├── chroma_db/                  # Local ChromaDB vector database storage
├── data/                       # Evaluation datasets
│   └── benchmark_samples.json  # 14-sample multi-domain benchmark suite
├── raw/                        # Raw BIRD benchmark datasets and SQLite files
├── src/                        # Source code directory
│   ├── app.py                  # Streamlit web application & benchmark dashboard
│   ├── evaluate_retrieval.py   # Automated retrieval & grounding evaluation script
│   ├── llm_engine.py           # Multi-stage LLM pipeline and self-correction
│   ├── main.py                 # Application entry point
│   ├── schema_indexer.py       # Database schema extraction and indexing
│   ├── security.py             # AST read-only guardrail & schema grounding check
│   └── vector_store.py         # ChromaDB vector store utilities
├── .env                        # Environment configuration
├── .gitignore                  # Git ignore configuration
├── docker-compose.yml          # Multi-container orchestration
├── Dockerfile                  # Container build instructions
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation

Quick Start

1. Clone the Repository & Create Virtual Environment

git clone [https://github.com/mehdi-it-data/enterprise-nl2sql-engine.git](https://github.com/mehdi-it-data/enterprise-nl2sql-engine.git)
cd enterprise-nl2sql-engine

python -m venv venv
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate

2. Install Dependencies & Prepare Ollama Model

pip install -r requirements.txt

# Ensure Ollama is running locally and pull the SQL code generation model
ollama pull qwen2.5-coder

3. Index Schemas & Run the Application

# Index database schemas into ChromaDB (if not already populated)
python src/schema_indexer.py

# Launch the Streamlit web interface and benchmark dashboard
streamlit run src/app.py

You can also run the standalone retrieval and schema grounding evaluation script from the command line:

python src/evaluate_retrieval.py

## Docker Setup

Ollama runs directly on the host machine, and the containerized Streamlit application connects to it via `http://host.docker.internal:11434/api/generate` (`MODEL_NAME=qwen2.5-coder`)[span_2](start_span)[span_2](end_span).

1. Build and Start Containers

Run the application container (`enterprise_nl2sql_app`) using Docker Compose[span_3](start_span)[span_3](end_span):

```bash
docker-compose up --build

To run the container detached in the background:

docker-compose up -d --build

2. Access & Manage Containers
Aufzählungszeichen Web Dashboard: Open http://localhost:8502 in your browser. media-C88833D0-37BA-…
Aufzählungszeichen View Logs:

docker-compose logs -f

Stop Services:

docker-compose down

Evaluation & Error Analysis

1. Quantitative Benchmark Results

The system was evaluated using a 14-sample benchmark suite (data/benchmark_samples.json) covering all 11 BIRD databases in dev_databases (california_schools, card_games, codebase_community, debit_card_specializing, european_football_2, financial, formula_1, student_club, superhero, thrombosis_prediction, and toxicology) along with out-of-scope and edge-case queries.

Metric                   Value        Interpretation

Hit Rate @ 1             100.0%       The target database was retrieved at rank #1 
                                      across all 14     benchmark    queries.

Hit Rate @ 3             100.0%       The target database appeared within the top 3 
                                      retrieved schemas for all 14 queries.

MRR Score                1.0000       Mean Reciprocal Rank reached its maximum value,            
                                      confirming consistent top-1 schema retrieval.
Schema Mismatch Rate    21.4%(3/14)   In 3 out of 14 queries (q02, q11, q14), the generated SQL    
                                      referenced at least one column not found
                                      in the retrieved schema context.

2. Error & Edge-Case Analysis

Aufzählungszeichen Column Name Mismatch in Ranking Queries (q02 and q14 on california_schools):
Aufzählungszeichen For both school ranking queries (List top 5 schools with highest Students in San Francisco and List top 5 schools with highest students in Frankfurt), check_schema_grounding flagged Column 'Enrollment' not found in retrieved schema.
Aufzählungszeichen This indicates the model mapped the natural-language concept of student count to Enrollment, which did not directly match the extracted column names in the retrieved schema context.
Aufzählungszeichen For the valid entity (San Francisco), the query still executed on SQLite and returned results, whereas for the out-of-scope entity (Frankfurt), execution failed with a missing column error after retries.
Aufzählungszeichen Multi-Entity / Clinical Column Mismatches (q11 on thrombosis_prediction):
Aufzählungszeichen For Find patients, laboratory tests, and examinations in thrombosis prediction, multiple columns (such as First_Date, T_BIL, T_CHO, and U_PRO) were not matched in the retrieved schema text.
Aufzählungszeichen Broad multi-table prompts across domain-specific medical schemas increase the risk of ungrounded column references or incomplete schema representation/extraction in the grounding check.
Aufzählungszeichen Safe Handling of Out-of-Domain Data Queries (Which countries participate in Asian football?):
Aufzählungszeichen The query routed to european_football_2, passed the sqlglot AST read-only guardrail, executed safely, and returned no rows instead of fabricating results—demonstrating reliable anti-hallucination behavior on empty result sets.

3. Limitations & Future Work

Aufzählungszeichen Expand Benchmark Scale: Grow data/benchmark_samples.json beyond 14 samples with more complex multi-table JOIN and aggregation (GROUP BY) queries from BIRD.
Aufzählungszeichen Tighten Schema Grounding & Prompt Alignment: Inspect the indexed schema text for california_schools and thrombosis_prediction, reinforce strict schema-only column instructions in LLMEngine, and feed Schema Grounding Warning messages into the self-correction loop to reduce the 21.4% mismatch rate.                                      
                                      
                                