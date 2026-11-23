import re
import sqlglot
from sqlglot import exp


def validate_and_sanitize_sql(sql_query: str) -> tuple[bool, str]:
    """
    Validates the generated SQL query using AST (Abstract Syntax Tree) analysis.
    Ensures that only safe SELECT queries are executed and blocks destructive operations.
    """
    try:
        # Parse the SQL string into an AST using sqlglot
        parsed_expressions = sqlglot.parse(sql_query, read="sqlite")

        if not parsed_expressions:
            return False, "Invalid SQL: Could not parse query."

        # We only take the first statement for evaluation
        expression = parsed_expressions[0]

        # Security Rule 1: Allow strictly SELECT statements (Read-Only Guardrail)
        if not isinstance(expression, exp.Select):
            return (
                False,
                f"Security Violation: Only SELECT queries are permitted.Detected statement type: {type(expression).__name__}",
            )

        # Security Rule 2: Check for forbidden write/destructive commands embedded in expression
        forbidden_exprs = (exp.Drop, exp.Delete, exp.Update, exp.Insert, exp.Alter, exp.Create)
        if expression.find(*forbidden_exprs):
            return (
                False,
                "Security Violation: Destructive or modifying operations "
                "(DROP, DELETE, UPDATE, INSERT, ALTER, CREATE) are strictly blocked.",
            )

        # If all checks pass, return the sanitized string representation
        return True, expression.sql(dialect="sqlite")

    except Exception as e:
        return False, f"AST Parsing & Validation Error: {str(e)}"


def extract_schema_objects(schema_text: str) -> tuple[set[str], set[str]]:
    """
    Extracts table names and column names from retrieved schema text.
    Supports both SQL DDL (CREATE TABLE) and text-formatted schema representations.
    """
    tables: set[str] = set()
    columns: set[str] = set()

    if not schema_text:
        return tables, columns

    # 1. Extract tables and column definitions from SQL DDL statements via sqlglot
    try:
        parsed_statements = sqlglot.parse(schema_text, read="sqlite")
        for stmt in parsed_statements:
            if isinstance(stmt, exp.Create) and isinstance(stmt.this, exp.Schema):
                table_expr = stmt.this.this
                if isinstance(table_expr, exp.Table) and table_expr.name:
                    tables.add(table_expr.name.lower())
                for col_def in stmt.this.find_all(exp.ColumnDef):
                    if col_def.name:
                        columns.add(col_def.name.lower())
    except Exception:
        pass

    # 2. Extract from text-formatted lines such as: "Table: League, Columns: id, country_id, name"
    for line in schema_text.splitlines():
        table_match = re.search(r"Table:\s*([A-Za-z0-9_]+)", line, flags=re.IGNORECASE)
        if table_match:
            tables.add(table_match.group(1).lower())

        cols_match = re.search(r"Columns:\s*(.+)$", line, flags=re.IGNORECASE)
        if cols_match:
            raw_cols = cols_match.group(1).split(",")
            for col in raw_cols:
                clean_col = col.strip().strip("`\"'").lower()
                if clean_col:
                    columns.add(clean_col)

    return tables, columns


def check_schema_grounding(
    sql_query: str, schema_text: str, dialect: str = "sqlite"
) -> list[str]:
    """
    Checks whether tables and columns referenced in the SQL query exist in the retrieved schema.
    Returns a list of schema grounding warning messages (empty if no mismatches are found).
    """
    warnings: list[str] = []
    allowed_tables, allowed_columns = extract_schema_objects(schema_text)

    # Skip check if no structured schema objects could be extracted to avoid false positives
    if not allowed_tables and not allowed_columns:
        return warnings

    try:
        parsed = sqlglot.parse_one(sql_query, read=dialect)
    except Exception:
        return warnings

    # Collect table/expression aliases so they are not misclassified as missing columns
    aliases: set[str] = set()
    for alias_expr in parsed.find_all(exp.Alias):
        if alias_expr.alias:
            aliases.add(alias_expr.alias.lower())
    for table_expr in parsed.find_all(exp.Table):
        if table_expr.alias:
            aliases.add(table_expr.alias.lower())

    # Validate referenced table names against retrieved schema tables
    checked_tables: set[str] = set()
    for table_expr in parsed.find_all(exp.Table):
        table_name = (table_expr.name or "").lower()
        if not table_name or table_name in checked_tables:
            continue
        checked_tables.add(table_name)

        if allowed_tables and table_name not in allowed_tables:
            warnings.append(f"Table `{table_expr.name}` not found in retrieved schema.")

    # Validate referenced column names (excluding wildcards '*' and aliases)
    checked_columns: set[str] = set()
    for col_expr in parsed.find_all(exp.Column):
        if isinstance(col_expr.this, exp.Star):
            continue
        col_name = (col_expr.name or "").lower()
        if not col_name or col_name in checked_columns or col_name in aliases:
            continue
        checked_columns.add(col_name)

        if allowed_columns and col_name not in allowed_columns:
            warnings.append(f"Column `{col_expr.name}` not found in retrieved schema.")

    return warnings