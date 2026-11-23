import streamlit as st
import sqlite3
import os
import json
import chromadb
import pandas as pd
from llm_engine import LLMEngine
from security import validate_and_sanitize_sql, check_schema_grounding

# Page Configuration
st.set_page_config(
    page_title="Enterprise NL2SQL Engine",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Enterprise-Grade NL2SQL Engine")
st.markdown(
    "Powered by **ChromaDB (Schema-RAG with n_results=3)**, "
    "**Ollama (qwen2.5-coder)**, **AST Guardrail (sqlglot)**, and **SQLite (BIRD-Benchmark)**"
)
st.markdown("---")

DEFAULT_BENCHMARK_SAMPLES = [
    {
        "id": "q01",
        "question": "Please remove 5 countries from the list of European football participants?",
        "true_db_id": "european_football_2",
        "category": "filter_lookup",
        "expected_status": "success",
    },
    {
        "id": "q02",
        "question": "List top 5 schools with highest Students in San Francisco",
        "true_db_id": "california_schools",
        "category": "join_ranking",
        "expected_status": "success",
    },
    {
        "id": "q03",
        "question": "Find all circuits located in country Australia",
        "true_db_id": "formula_1",
        "category": "filter_lookup",
        "expected_status": "success",
    },
]


def load_benchmark_samples(json_path: str = "data/benchmark_samples.json") -> list[dict]:
    """Load benchmark evaluation samples from a JSON file with a safe fallback."""
    if not os.path.exists(json_path):
        return DEFAULT_BENCHMARK_SAMPLES
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception:
        pass
    return DEFAULT_BENCHMARK_SAMPLES


def clean_sql_output(raw_sql: str) -> str:
    """Strip markdown code fences from generated SQL strings."""
    return raw_sql.replace("```sql", "").replace("```", "").strip()


# Initialize ChromaDB and LLM Engine (Cached to prevent reloading)
@st.cache_resource
def init_chroma():
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    return chroma_client.get_or_create_collection(name="bird_schemas")


@st.cache_resource
def init_llm():
    return LLMEngine(provider="ollama", model_name="qwen2.5-coder")


collection = init_chroma()
llm_engine = init_llm()

# User Input Section
question = st.text_input(
    "💬 Enter your natural language question (in English):",
)

if st.button("Generate & Execute SQL"):
    if not question:
        st.warning("Please enter a valid question.")
    else:
        with st.spinner("🔍 Retrieving top schemas and generating SQL via LLM..."):
            # 1. Retrieve top 3 schemas using ChromaDB for enhanced accuracy
            retrieved_results = collection.query(
                query_texts=[question],
                n_results=3,
            )

            db_id = retrieved_results["ids"][0][0]
            schemas = retrieved_results["documents"][0]
            schema_text = "\n\n---\n\n".join(schemas)

            # 2. Generate initial SQL query
            raw_sql = llm_engine.generate_sql(schema_text, question)
            sql_query = clean_sql_output(raw_sql)

        # 🛡️ 3. Apply AST Security & Guardrail Check
        is_safe, sanitized_or_error = validate_and_sanitize_sql(sql_query)

        # Display Metadata & Schema in Expandable Box
        st.info(f"📌 **Retrieved Database ID:** `{db_id}`")
        with st.expander("👁️ View Retrieved Database Schemas (RAG Context)"):
            st.code(schema_text, language="sql")

        st.markdown("### 📝 Generated SQL Query")
        st.code(sql_query, language="sql")

        if not is_safe:
            st.error(f"❌ **AST Security Blocked:** {sanitized_or_error}")
        else:
            sql_query = sanitized_or_error
            st.success("✅ **AST Guardrail Passed:** Query is safe and read-only.")

            # 🔍 Schema Grounding Check (Anti-Hallucination against retrieved schema)
            schema_warnings = check_schema_grounding(sql_query, schema_text, dialect="sqlite")
            if schema_warnings:
                st.warning(
                    "⚠️ **Schema Grounding Warning (Potential Table/Column Hallucination):**\n- "
                    + "\n- ".join(schema_warnings)
                )

            # 4. Execution & Self-Correction Loop
            db_path = f"raw/dev/dev_20240627/dev_databases/{db_id}/{db_id}.sqlite"

            if not os.path.exists(db_path):
                st.error(f"❌ Database file not found at `{db_path}`")
            else:
                max_retries = 3
                success = False
                results = []
                columns = []

                with st.spinner("⚡ Executing query against SQLite (with Self-Correction)..."):
                    for attempt in range(max_retries):
                        try:
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            cursor.execute(sql_query)
                            results = cursor.fetchall()
                            columns = [description[0] for description in cursor.description]
                            conn.close()
                            success = True
                            break
                        except Exception as e:
                            error_msg = str(e)
                            if attempt < max_retries - 1:
                                raw_corrected = llm_engine.correct_sql(
                                    schema_text, question, sql_query, error_msg
                                )
                                raw_sql_corrected = clean_sql_output(raw_corrected)

                                # Re-validate corrected query through AST guardrail
                                is_safe_corr, sanitized_corr_or_err = validate_and_sanitize_sql(
                                    raw_sql_corrected
                                )
                                if not is_safe_corr:
                                    st.error(
                                        f"❌ **Security Blocked on Corrected Query:** {sanitized_corr_or_err}"
                                    )
                                    break
                                sql_query = sanitized_corr_or_err
                            else:
                                st.error(f"❌ SQL Execution Error after retries: {error_msg}")

                if success:
                    st.success("🎉 Query executed successfully!")
                    st.markdown("### 📊 Execution Results")
                    if results:
                        df = pd.DataFrame(results, columns=columns)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("The query executed successfully, but returned no rows.")

# --- Retrieval & Schema Grounding Benchmark Dashboard Section ---
st.markdown("---")
st.sidebar.header("📊 Evaluation & Benchmarking")
if st.sidebar.button("Run Retrieval Benchmark"):
    benchmark_samples = load_benchmark_samples("data/benchmark_samples.json")
    with st.spinner(
        f"Running retrieval and schema grounding benchmark across {len(benchmark_samples)} samples..."
    ):
        hits = {1: 0, 3: 0}
        reciprocal_ranks = []
        mismatched_queries = 0
        total_queries = len(benchmark_samples)
        eval_results = []

        for sample in benchmark_samples:
            sample_id = sample.get("id", "-")
            category = sample.get("category", "general")
            q = sample["question"]
            true_id = sample["true_db_id"]

            res = collection.query(
                query_texts=[q],
                n_results=3,
                include=["documents"],
            )
            retrieved_ids = res["ids"][0]
            retrieved_docs = (
                res["documents"][0] if res.get("documents") and res["documents"][0] else []
            )
            sample_schema_text = "\n\n---\n\n".join(retrieved_docs)

            found_rank = None
            for rank, db_id in enumerate(retrieved_ids, start=1):
                if db_id == true_id:
                    found_rank = rank
                    break

            if found_rank:
                if found_rank <= 1:
                    hits[1] += 1
                if found_rank <= 3:
                    hits[3] += 1
                reciprocal_ranks.append(1.0 / found_rank)
            else:
                reciprocal_ranks.append(0.0)

            # Generate SQL and check schema grounding against retrieved schemas
            sample_warnings = []
            try:
                raw_sample_sql = llm_engine.generate_sql(sample_schema_text, q)
                sample_sql = clean_sql_output(raw_sample_sql)
                is_safe_sample, sanitized_sample = validate_and_sanitize_sql(sample_sql)
                sql_to_check = sanitized_sample if is_safe_sample else sample_sql
                sample_warnings = check_schema_grounding(
                    sql_to_check, sample_schema_text, dialect="sqlite"
                )
            except Exception as bench_err:
                sample_warnings = [f"Evaluation error: {bench_err}"]

            has_mismatch = len(sample_warnings) > 0
            if has_mismatch:
                mismatched_queries += 1

            eval_results.append(
                {
                    "ID": sample_id,
                    "Category": category,
                    "Question": q,
                    "Target DB": true_id,
                    "Top Retrieved": retrieved_ids[0] if retrieved_ids else None,
                    "Found Rank": found_rank if found_rank else "Not in Top 3",
                    "Schema Mismatch": "Yes" if has_mismatch else "No",
                    "Schema Warnings": " | ".join(sample_warnings) if sample_warnings else "-",
                }
            )

        hr_1 = (hits[1] / total_queries) * 100
        hr_3 = (hits[3] / total_queries) * 100
        mrr_score = sum(reciprocal_ranks) / total_queries
        schema_mismatch_rate = (mismatched_queries / total_queries) * 100

        # Display Metrics in Streamlit
        st.subheader("🎯 RAG Retrieval & Schema Grounding Benchmark Results")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Hit Rate @ 1", f"{hr_1:.1f}%")
        col2.metric("Hit Rate @ 3", f"{hr_3:.1f}%")
        col3.metric("MRR Score", f"{mrr_score:.4f}")
        col4.metric(
            "Schema Mismatch Rate",
            f"{schema_mismatch_rate:.1f}%",
            delta=f"{mismatched_queries}/{total_queries} queries",
            delta_color="inverse",
        )

        st.markdown("#### Detailed Query Evaluation Log")
        st.dataframe(pd.DataFrame(eval_results), use_container_width=True)
