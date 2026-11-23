import os
import json
from typing import Callable, Optional
import chromadb

try:
    from src.security import check_schema_grounding
except ImportError:
    from security import check_schema_grounding


def evaluate_retrieval_pipeline(
    sql_generator: Optional[Callable[[str, str], str]] = None,
) -> dict:
    """
    Runs the retrieval benchmarking suite and evaluates schema grounding mismatches.
    An optional sql_generator(question, retrieved_schema_text) callable can be passed
    to generate SQL queries dynamically during evaluation.
    """
    print("🚀 Initializing Retrieval & Schema Grounding Benchmarking Suite...")

    # 1. Initialize ChromaDB client and collection
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    collection = chroma_client.get_or_create_collection(name="bird_schemas")

    # 2. Define a benchmark evaluation dataset (Sample queries with their true db_ids)
    # In a full research setup, this would load from a JSON file containing BIRD dev set samples.
    benchmark_samples = [
        {
            "question": "Please remove 5 countries from the list of European football participants?",
            "true_db_id": "european_football_2",
        },
        {
            "question": "List top 5 schools with highest Students in San Francisco",
            "true_db_id": "student_club",  # Or respective actual database ID in your dataset
        },
        {
            "question": "Find all circuits located in country Australia",
            "true_db_id": "formula_1",
        },
    ]

    k_values = [1, 3]
    hits = {1: 0, 3: 0}
    reciprocal_ranks = []

    mismatched_queries = 0
    evaluated_sql_queries = 0
    total_schema_warnings = 0
    detailed_logs = []

    total_queries = len(benchmark_samples)
    print(f"\nEvaluating {total_queries} benchmark queries across K={k_values}...\n")

    for idx, sample in enumerate(benchmark_samples):
        question = sample["question"]
        true_db_id = sample["true_db_id"]

        # Query ChromaDB to retrieve top 3 results including documents/schemas
        results = collection.query(
            query_texts=[question],
            n_results=3,
            include=["documents", "metadatas", "distances"],
        )

        retrieved_ids = results["ids"][0] if results.get("ids") else []
        retrieved_docs = (
            results["documents"][0]
            if results.get("documents") and results["documents"][0]
            else []
        )
        retrieved_schema_text = "\n\n".join(doc for doc in retrieved_docs if doc)

        print(f"[{idx+1}] Q: {question}")
        print(f"    Target DB: {true_db_id}")
        print(f"    Retrieved IDs: {retrieved_ids}")

        # Calculate Hit Rate@1 and Hit Rate@3
        found_rank = None
        for rank, db_id in enumerate(retrieved_ids, start=1):
            if db_id == true_db_id:
                found_rank = rank
                break

        if found_rank is not None:
            if found_rank <= 1:
                hits[1] += 1
            if found_rank <= 3:
                hits[3] += 1
            reciprocal_ranks.append(1.0 / found_rank)
            print(f"    ✅ Found at rank {found_rank}")
        else:
            reciprocal_ranks.append(0.0)
            print("    ❌ Not found in top 3")

        # Resolve SQL query for schema grounding check if available
        generated_sql = sample.get("generated_sql", "")
        if not generated_sql and callable(sql_generator):
            try:
                generated_sql = sql_generator(question, retrieved_schema_text) or ""
            except Exception as exc:
                print(f"    ⚠️ SQL generation skipped due to error: {exc}")
                generated_sql = ""

        schema_warnings = []
        has_schema_mismatch = False
        if generated_sql.strip():
            evaluated_sql_queries += 1
            schema_warnings = check_schema_grounding(
                generated_sql, retrieved_schema_text, dialect="sqlite"
            )
            has_schema_mismatch = len(schema_warnings) > 0
            if has_schema_mismatch:
                mismatched_queries += 1
                total_schema_warnings += len(schema_warnings)
                print(f"    ⚠️ Schema Mismatch Detected ({len(schema_warnings)}):")
                for warn in schema_warnings:
                    print(f"       - {warn}")
            else:
                print("    🛡️ Schema Grounding Passed: No table/column mismatch.")
        else:
            print("    ℹ️ Schema Mismatch Check: No SQL provided/generated for this sample.")

        print()

        detailed_logs.append(
            {
                "index": idx + 1,
                "question": question,
                "true_db_id": true_db_id,
                "top_retrieved_db_id": retrieved_ids[0] if retrieved_ids else None,
                "retrieved_ids": retrieved_ids,
                "found_rank": found_rank,
                "schema_mismatch": has_schema_mismatch,
                "schema_warnings_count": len(schema_warnings),
                "schema_warnings": schema_warnings,
            }
        )

    # Compute final retrieval metrics
    hit_rate_at_1 = (hits[1] / total_queries) * 100 if total_queries > 0 else 0.0
    hit_rate_at_3 = (hits[3] / total_queries) * 100 if total_queries > 0 else 0.0
    mrr = sum(reciprocal_ranks) / total_queries if total_queries > 0 else 0.0

    # Compute schema mismatch rate over evaluated SQL queries (or total queries if none had SQL)
    mismatch_denominator = (
        evaluated_sql_queries if evaluated_sql_queries > 0 else total_queries
    )
    schema_mismatch_rate = (
        (mismatched_queries / mismatch_denominator) * 100
        if mismatch_denominator > 0
        else 0.0
    )

    print("=" * 55)
    print("📊 RETRIEVAL & SCHEMA GROUNDING BENCHMARK RESULTS:")
    print(f"  • Hit Rate @ 1          : {hit_rate_at_1:.2f}%")
    print(f"  • Hit Rate @ 3          : {hit_rate_at_3:.2f}%")
    print(f"  • MRR (Mean Reciprocal) : {mrr:.4f}")
    print(
        f"  • Schema Mismatch Rate  : {schema_mismatch_rate:.2f}% "
        f"({mismatched_queries}/{evaluated_sql_queries} SQL queries evaluated, "
        f"{total_schema_warnings} total warnings)"
    )
    print("=" * 55)

    return {
        "total_queries": total_queries,
        "hit_rate_at_1": hit_rate_at_1,
        "hit_rate_at_3": hit_rate_at_3,
        "mrr": mrr,
        "evaluated_sql_queries": evaluated_sql_queries,
        "mismatched_queries": mismatched_queries,
        "total_schema_warnings": total_schema_warnings,
        "schema_mismatch_rate": schema_mismatch_rate,
        "logs": detailed_logs,
    }


if __name__ == "__main__":
    evaluate_retrieval_pipeline()