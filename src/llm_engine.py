import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class LLMEngine:
    def __init__(self, provider="ollama", model_name="qwen2.5-coder"):
        self.provider = provider
        self.model_name = model_name
        # Use environment variable if available, otherwise fallback to localhost
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

    def generate_sql(self, schema_text: str, question: str) -> str:
        """
        Generate SQL query based on the retrieved database schema and natural language question.
        """
        prompt = f"""You are an advanced Text-to-SQL engine. Given the following database schema, write a SQL query that answers the user question.

Schema:
{schema_text}

User Question: {question}

CRITICAL INSTRUCTIONS:
- You must strictly use the exact table names and column names provided in the Schema above. Do NOT guess, alter, or abbreviate column names.
- If the question requires data from multiple tables (e.g., school names and enrollment stats),
 you MUST use appropriate JOIN clauses (using matching keys like CDSCode) and prefix columns with their correct table names.
- Provide ONLY the SQL query without any explanation or markdown formatting."""

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        response = requests.post(self.ollama_url, json=payload)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            raise Exception(f"Error from Ollama: {response.text}")

    def correct_sql(self, schema_text: str, question: str, bad_sql: str, error_message: str) -> str:
        """
        Takes a failed SQL query and the SQLite error message, then asks the LLM to fix it.
        """
        prompt = f"""You are an advanced Text-to-SQL correction engine. Given the database schema, the user question, a previously generated incorrect SQL query, and the SQLite error message, fix the SQL query.

Schema:
{schema_text}

User Question: {question}

Incorrect SQL:
{bad_sql}

SQLite Error:
{error_message}

CRITICAL INSTRUCTIONS:
- Fix the SQL query by strictly using the exact table and column names from the Schema. Look closely at the SQLite Error message to identify mismatched column names.
- If multiple tables are involved, ensure proper JOIN clauses are used.
- Provide ONLY the corrected SQL query without any explanation or markdown formatting."""

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        response = requests.post(self.ollama_url, json=payload)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            raise Exception(f"Error from Ollama: {response.text}")
            