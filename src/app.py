import streamlit as st
import sqlite3
import os
import chromadb
import pandas as pd
from llm_engine import LLMEngine

# Page Configuration
st.set_page_config(
    page_title="Enterprise NL2SQL Engine",
    page_icon="🤖",
    layout="wide"
)

st.title("🚀 Enterprise-Grade NL2SQL Engine")
st.markdown("Powered by **ChromaDB (Schema-RAG)**, **Ollama (qwen2.5-coder)**, and **SQLite (BIRD-Benchmark)**.")
st.markdown("---")

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
        with st.spinner("🔄 Retrieving schema and generating SQL via LLM..."):
            # 1. Retrieve schema via ChromaDB
            retrieved_results = collection.query(
                query_texts=[question],
                n_results=1
            )
            
            db_id = retrieved_results["ids"][0][0]
            schema_text = retrieved_results["documents"][0][0]

            # 2. Generate initial SQL query
            raw_sql = llm_engine.generate_sql(schema_text, question)
            sql_query = raw_sql.replace("```sql", "").replace("```", "").strip()

        # Display Metadata & Schema in Expandable Box
        st.info(f"📁 **Retrieved Database ID:** `{db_id}`")
        with st.expander("🔍 View Retrieved Database Schema (RAG Context)"):
            st.code(schema_text, language="sql")

        st.markdown("### 📝 Generated SQL Query")
        st.code(sql_query, language="sql")

        # 3. Execution & Self-Correction Loop
        db_path = f"raw/dev/dev_20240627/dev_databases/{db_id}/{db_id}.sqlite"
        
        if not os.path.exists(db_path):
            st.error(f"⚠️ Database file not found at {db_path}")
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
                            # Trigger Self-Correction
                            raw_corrected = llm_engine.correct_sql(schema_text, question, sql_query, error_msg)
                            sql_query = raw_corrected.replace("```sql", "").replace("```", "").strip()
                        else:
                            st.error(f"❌ SQL Execution Error after retries: {error_msg}")

            if success:
                st.success("✅ Query executed successfully!")
                st.markdown("### 📊 Execution Results")
                if results:
                    df = pd.DataFrame(results, columns=columns)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("The query executed successfully, but returned no rows.")