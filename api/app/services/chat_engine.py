import re
import logging
from typing import Dict, Any, List, Tuple
from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)

# Keywords forbidden for security
FORBIDDEN_CYPHER_KEYWORDS = [
    "CREATE", "MERGE", "SET", "DELETE", "DETACH", "REMOVE", "DROP",
    "ALTER", "CALL", "APOC", "DBMS", "LOAD", "PERIODIC", "USING"
]

def validate_cypher(cypher: str) -> bool:
    """Ensure Cypher is read-only and safe."""
    upper_c = cypher.upper()
    for kw in FORBIDDEN_CYPHER_KEYWORDS:
        if re.search(r'\b' + kw + r'\b', upper_c):
            logger.warning(f"Security check rejected Cypher containing forbidden keyword: {kw}")
            return False
    return True

class ChatEngine:
    def process_question(self, question: str) -> Dict[str, Any]:
        q_lower = question.strip().lower()
        
        # 1. Fetch available property keys and values sample from Neo4j
        try:
            sample_props = neo4j_client.get_row_properties_sample()
        except Exception as e:
            logger.error(f"Error fetching schema from Neo4j: {e}")
            return {
                "answer": "I don't have that information in the uploaded data.",
                "cypher": "MATCH (r:Row) RETURN count(r)",
                "result": [],
                "grounded": False
            }

        # Check if database has any Row nodes at all
        total_rows_res = neo4j_client.execute_read_cypher("MATCH (r:Row) RETURN count(r) AS total")
        total_rows = total_rows_res[0]["total"] if total_rows_res else 0

        if total_rows == 0:
            return {
                "answer": "I don't have that information in the uploaded data.",
                "cypher": "MATCH (r:Row) RETURN count(r)",
                "result": [],
                "grounded": False
            }

        # 2. Match Intents

        # Intent A: Total row count / general count
        if any(p in q_lower for p in ["how many rows", "total rows", "how many records", "total count", "number of rows", "how many entries"]):
            cypher = "MATCH (r:Row) RETURN count(r) AS count"
            res = neo4j_client.execute_read_cypher(cypher)
            count = res[0]["count"] if res else 0
            return {
                "answer": f"There are {count} rows in the uploaded dataset.",
                "cypher": cypher,
                "result": res,
                "grounded": True
            }

        # Intent B: Distinct values for a column (e.g., "list all groups", "unique departments")
        for key in sample_props.keys():
            k_lower = key.lower()
            if f"all {k_lower}" in q_lower or f"unique {k_lower}" in q_lower or f"distinct {k_lower}" in q_lower or f"list {k_lower}" in q_lower:
                cypher = f"MATCH (r:Row) WHERE r.`{key}` IS NOT NULL RETURN DISTINCT r.`{key}` AS `{key}` LIMIT 100"
                res = neo4j_client.execute_read_cypher(cypher)
                vals = [str(r[key]) for r in res if r.get(key) is not None]
                if vals:
                    return {
                        "answer": f"The unique values for '{key}' are: {', '.join(vals[:20])}" + ("..." if len(vals) > 20 else "."),
                        "cypher": cypher,
                        "result": res,
                        "grounded": True
                    }

        # Intent C: Specific property value count or filter (e.g. "how many ... in Billing", "rows where group is Support")
        # Search across all dynamic property values for a direct word match in the question
        best_match = None
        for key, values in sample_props.items():
            for val in values:
                if val is None:
                    continue
                val_str = str(val).strip()
                if not val_str:
                    continue
                val_lower = val_str.lower()
                
                # Check if value word is present in question
                pattern = r'\b' + re.escape(val_lower) + r'\b'
                if re.search(pattern, q_lower):
                    best_match = (key, val_str)
                    break
            if best_match:
                break

        if best_match:
            matched_key, matched_val = best_match
            # Check if count query or listing query
            if any(c in q_lower for c in ["how many", "count", "number of"]):
                cypher = f"MATCH (r:Row) WHERE toLower(toString(r.`{matched_key}`)) = toLower($val) RETURN count(r) AS count"
                res = neo4j_client.execute_read_cypher(cypher, {"val": matched_val})
                count = res[0]["count"] if res else 0
                return {
                    "answer": f"There are {count} rows where {matched_key} = '{matched_val}'.",
                    "cypher": cypher.replace("$val", f"'{matched_val}'"),
                    "result": res,
                    "grounded": True
                }
            else:
                cypher = f"MATCH (r:Row) WHERE toLower(toString(r.`{matched_key}`)) = toLower($val) RETURN r LIMIT 10"
                res = neo4j_client.execute_read_cypher(cypher, {"val": matched_val})
                # Extract clean dicts for UI display
                clean_res = [dict(record["r"]) for record in res]
                return {
                    "answer": f"Found {len(clean_res)} matching rows for {matched_key} = '{matched_val}'.",
                    "cypher": cypher.replace("$val", f"'{matched_val}'"),
                    "result": clean_res,
                    "grounded": True
                }

        # Intent D: Numerical Aggregations (average, max, min, sum)
        for key in sample_props.keys():
            k_lower = key.lower()
            if k_lower in q_lower:
                if "avg" in q_lower or "average" in q_lower:
                    cypher = f"MATCH (r:Row) WHERE r.`{key}` IS NOT NULL RETURN avg(toInteger(r.`{key}`)) AS average_{key}"
                    res = neo4j_client.execute_read_cypher(cypher)
                    val = res[0].get(f"average_{key}") if res else None
                    if val is not None:
                        return {
                            "answer": f"The average of '{key}' is {round(val, 2)}.",
                            "cypher": cypher,
                            "result": res,
                            "grounded": True
                        }
                elif "max" in q_lower or "maximum" in q_lower or "highest" in q_lower:
                    cypher = f"MATCH (r:Row) WHERE r.`{key}` IS NOT NULL RETURN max(toInteger(r.`{key}`)) AS max_{key}"
                    res = neo4j_client.execute_read_cypher(cypher)
                    val = res[0].get(f"max_{key}") if res else None
                    if val is not None:
                        return {
                            "answer": f"The maximum value for '{key}' is {val}.",
                            "cypher": cypher,
                            "result": res,
                            "grounded": True
                        }

        # Intent E: General search fallback on question words
        # Extract meaningful search terms (length > 2, not common stopwords)
        stopwords = {"what", "is", "the", "are", "how", "many", "in", "of", "to", "for", "where", "show", "find", "list", "get", "tell", "me", "about"}
        words = [w for w in re.findall(r'\w+', q_lower) if w not in stopwords and len(w) > 2]
        
        for word in words:
            # Check if any row property contains this word
            cypher = "MATCH (r:Row) WHERE ANY(k IN keys(r) WHERE toLower(toString(r[k])) CONTAINS $term) RETURN r LIMIT 5"
            res = neo4j_client.execute_read_cypher(cypher, {"term": word})
            if res:
                clean_res = [dict(rec["r"]) for rec in res]
                return {
                    "answer": f"Found {len(clean_res)} row(s) containing term '{word}'.",
                    "cypher": f"MATCH (r:Row) WHERE ANY(k IN keys(r) WHERE toLower(toString(r[k])) CONTAINS '{word}') RETURN r LIMIT 5",
                    "result": clean_res,
                    "grounded": True
                }

        # 3. Default Ungrounded Response when graph cannot answer
        return {
            "answer": "I don't have that information in the uploaded data.",
            "cypher": f"MATCH (r:Row) RETURN count(r)",
            "result": [],
            "grounded": False
        }

chat_engine = ChatEngine()
