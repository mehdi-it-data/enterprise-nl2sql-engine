import json
import sqlite3
import os
import chromadb
from llm_engine import LLMEngine
from security import validate_and_sanitize_sql

def run_nl2sql_pipeline():
    # 1. Initialize persistent ChromaDB client and collection
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    collection = chroma_client.get_or_create_collection(name="bird_schemas")

    # 2. Initialize LLM Engine
    llm_engine = LLMEngine(provider="ollama", model_name="qwen2.5-coder")

    # 3. Get natural language question dynamically from the user
    question = input("Enter your question: ")
    print(f"\nUser Question: {question}\n")

    # 4. Retrieve top 3 most relevant database schemas using ChromaDB for higher accuracy
    retrieved_results = collection.query(
        query_texts=[question],
        n_results=3
    )
    
    # Get the top database ID for SQLite execution (the most relevant one)
    db_id = retrieved_results["ids"][0][0]
    
    # Extract all 3 retrieved schema documents and combine them into a single context string
    schemas = retrieved_results["documents"][0]
    schema_text = "\n\n---\n\n".join(schemas)
    
    print(f"Retrieved Top Database ID: {db_id}")

    # 5. Generate initial SQL query using the LLM engine
    print("Generating initial SQL query via LLM...")
    raw_sql = llm_engine.generate_sql(schema_text, question)

    # Clean up markdown code blocks if present
    sql_query = raw_sql.replace("```sql", "").replace("```", "").strip()
    print(f"\nGenerated SQL Query:\n{sql_query}\n")

    # 🛡️ 6. Apply AST Security & Guardrail Check before execution
    print("Running AST Security & Guardrail Check...")
    is_safe, sanitized_or_error = validate_and_sanitize_sql(sql_query)

    if not is_safe:
        print(f"\n❌ Security Blocked: {sanitized_or_error}")
        return
    else:
        sql_query = sanitized_or_error
        print("✅ AST Guardrail Passed: Query is safe and read-only.")

    # 7. Locate SQLite database
    db_path = f"raw/dev/dev_20240627/dev_databases/{db_id}/{db_id}.sqlite"

    if not os.path.exists(db_path):
        print(f"Warning: Database file not found at {db_path}")
        return

    # 8. Execution and Self-Correction Loop
    max_retries = 3
    success = False

    for attempt in range(max_retries):
        try:
            print(f"Executing SQL query (Attempt {attempt + 1}/{max_retries})...")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(sql_query)
            results = cursor.fetchall()

            print("\n✅ SQL Execution Successful!")
            print("Execution Results (Sample):")
            for row in results[:5]:  # Print top 5 rows
                print(row)

            conn.close()
            success = True
            break

        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ SQL Execution Error: {error_msg}")

            if attempt < max_retries - 1:
                print("Triggering Self-Correction: Sending error back to LLM...")
                raw_corrected = llm_engine.correct_sql(schema_text, question, sql_query, error_msg)
                raw_sql_corrected = raw_corrected.replace("```sql", "").replace("```", "").strip()
                
                # Re-validate the corrected query through AST Guardrail for safety
                is_safe, sanitized_or_error = validate_and_sanitize_sql(raw_sql_corrected)
                if not is_safe:
                    print(f"\n❌ Security Blocked on Corrected Query: {sanitized_or_error}")
                    break
                    
                sql_query = sanitized_or_error
                print(f"\nCorrected & Verified SQL Query:\n{sql_query}\n")
            else:
                print("\n⚠️ Max retries reached. Could not resolve the SQL error automatically.")

if __name__ == "__main__":
    run_nl2sql_pipeline()