import json
import os
import sqlite3

# Define the path to the BIRD dev dataset files
json_path = "raw/dev/dev_20240627/dev.json"

# Load the dev.json file containing natural language questions and SQL queries
with open(json_path, "r", encoding="utf-8") as f:
    dev_data = json.load(f)

# Pick the first sample from the dataset to test
sample = dev_data[0]
db_id = sample["db_id"]
question = sample["question"]
ground_truth_sql = sample["SQL"]

print(f"Database ID: {db_id}")
print(f"Question: {question}")
print(f"Target SQL: {ground_truth_sql}\n")

# Construct the path to the specific SQLite database file
db_path = f"raw/dev/dev_20240627/dev_databases/{db_id}/{db_id}.sqlite"

# Check if the database file exists and execute the ground truth query
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(ground_truth_sql)
    results = cursor.fetchall()
    print("Database Query Results (Sample):", results[:3])
    conn.close()
else:
    print(f"Warning: Database file not found at {db_path}")