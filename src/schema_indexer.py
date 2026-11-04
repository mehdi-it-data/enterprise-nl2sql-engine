import json

# Define the path to the BIRD dev tables JSON file
tables_json_path = "raw/dev/dev_20240627/dev_tables.json"

# Load the database schemas and metadata
with open(tables_json_path, "r", encoding="utf-8") as f:
    tables_data = json.load(f)

print(f"Loaded schema metadata for {len(tables_data)} databases successfully.")

# Function to get schema representation for a specific database ID
def get_database_schema(db_id: str):
    for db in tables_data:
        if db["db_id"] == db_id:
            tables = db["table_names_original"]
            columns = db["column_names_original"]
            
            schema_info = f"Database: {db_id}\n"
            for t_idx, table_name in enumerate(tables):
                cols = [col[1] for col in columns if col[0] == t_idx]
                schema_info += f"Table: {table_name}, Columns: {', '.join(cols)}\n"
            return schema_info
    return None

# Test the schema extraction for california_schools
sample_schema = get_database_schema("california_schools")
if sample_schema:
    print("\nSample Schema Output:")
    print(sample_schema[:300])  # Print preview of the schema