import json
import chromadb

# Initialize persistent ChromaDB client stored on disk
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Create or get a collection for database schemas
collection = chroma_client.get_or_create_collection(name="bird_schemas")

# Load database schemas from dev_tables.json
tables_json_path = "raw/dev/dev_20240627/dev_tables.json"
with open(tables_json_path, "r", encoding="utf-8") as f:
    tables_data = json.load(f)

# Index each database schema into ChromaDB
for db in tables_data:
    db_id = db["db_id"]
    tables = db["table_names_original"]
    columns = db["column_names_original"]
    
    # Build text representation of the schema
    schema_text = f"Database ID: {db_id}\n"
    for t_idx, table_name in enumerate(tables):
        cols = [col[1] for col in columns if col[0] == t_idx]
        schema_text += f"Table: {table_name}, Columns: {', '.join(cols)}\n"
    
    # Add document to ChromaDB collection
    collection.add(
        documents=[schema_text],
        ids=[db_id]
    )

print(f"Successfully indexed {collection.count()} database schemas into ChromaDB.")

# Test similarity search for a sample question
query = "Show me schools in Alameda County with high free meal count"
results = collection.query(
    query_texts=[query],
    n_results=1
)

print("\nTop Retrieved Database for Query:")
print(results["ids"][0][0])