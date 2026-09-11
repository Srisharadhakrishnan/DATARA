import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)

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
    def _find_matching_col(self, synonyms: List[str], available_cols: List[str]) -> Optional[str]:
        """Find the first matching column key present in available_cols."""
        for syn in synonyms:
            for col in available_cols:
                if col.lower() == syn.lower() or syn.lower() in col.lower():
                    return col
        return None

    def process_question(self, question: str) -> Dict[str, Any]:
        q_text = question.strip()
        q_lower = q_text.lower()
        
        # 1. Fetch available property keys and sample values from Neo4j
        try:
            available_cols = neo4j_client.get_dataset_schema()
            sample_props = neo4j_client.get_row_properties_sample()
        except Exception as e:
            logger.error(f"Error fetching schema from Neo4j: {e}")
            return self._ungrounded_response()

        # Check total rows
        total_rows_res = neo4j_client.execute_read_cypher("MATCH (r:Row) RETURN count(r) AS total")
        total_rows = total_rows_res[0]["total"] if total_rows_res else 0

        if total_rows == 0 or not available_cols:
            return self._ungrounded_response()

        # 2. Extract Value Filters from Question
        # Search sample property values to find if user mentioned any stored value
        matched_filter = None  # Tuple: (col_name, matched_value)
        
        # First, test full word boundaries against all sample string values
        for col_name, val_list in sample_props.items():
            for val in val_list:
                if val is None:
                    continue
                v_str = str(val).strip()
                if not v_str or len(v_str) < 2:
                    continue
                
                # Word boundary match
                pattern = r'\b' + re.escape(v_str.lower()) + r'\b'
                if re.search(pattern, q_lower):
                    matched_filter = (col_name, v_str)
                    break
            if matched_filter:
                break

        # Fallback: check explicitly phrased filters like "in HR", "for HR", "from Paris"
        if not matched_filter:
            preposition_match = re.search(r'\b(?:in|for|from|belonging to|where group is|where status is|where city is)\s+([a-zA-Z0-9_\-]+)', q_text, re.IGNORECASE)
            if preposition_match:
                candidate_val = preposition_match.group(1).strip()
                # Guess column based on phrasing or default to 'group' or first string column
                guessed_col = self._find_matching_col(["group", "department", "city", "status"], available_cols) or available_cols[0]
                matched_filter = (guessed_col, candidate_val)

        # 3. Detect Operation Type
        is_count = any(k in q_lower for k in ["how many", "count", "number of", "total count"])
        is_aggregation = any(k in q_lower for k in ["total amount", "sum of", "average", "avg", "maximum", "max"])
        is_list = any(k in q_lower for k in ["show", "list", "give me", "display", "find", "which", "who", "tell me"]) or not is_count

        # 4. Detect Requested Return Fields
        requested_return_cols = []
        
        # Customer name / primary identity column
        name_col = self._find_matching_col(["customer_name", "name", "employee_name", "customer_id", "emp_id"], available_cols)
        if name_col and name_col not in requested_return_cols:
            requested_return_cols.append(name_col)

        # Additional requested fields based on question content
        if "status" in q_lower:
            st_col = self._find_matching_col(["status", "state"], available_cols)
            if st_col and st_col not in requested_return_cols:
                requested_return_cols.append(st_col)

        if any(w in q_lower for w in ["order amount", "amount", "spending", "order_amount"]):
            amt_col = self._find_matching_col(["order_amount", "spending", "amount", "salary"], available_cols)
            if amt_col and amt_col not in requested_return_cols:
                requested_return_cols.append(amt_col)

        if any(w in q_lower for w in ["order id", "order_id", "orders"]):
            ord_col = self._find_matching_col(["order_id", "emp_id"], available_cols)
            if ord_col and ord_col not in requested_return_cols:
                requested_return_cols.append(ord_col)

        if any(w in q_lower for w in ["city", "cities", "location", "from"]):
            city_col = self._find_matching_col(["city", "location", "address"], available_cols)
            if city_col and city_col not in requested_return_cols:
                requested_return_cols.append(city_col)

        if any(w in q_lower for w in ["group", "department", "dept"]):
            grp_col = self._find_matching_col(["group", "department", "role"], available_cols)
            if grp_col and grp_col not in requested_return_cols:
                requested_return_cols.append(grp_col)

        # Fallback if no return cols selected
        if not requested_return_cols:
            requested_return_cols = available_cols[:3]

        # 5. Construct Cypher Query & Execute

        # CASE A: Count Query
        if is_count:
            if matched_filter:
                f_col, f_val = matched_filter
                cypher = f"MATCH (r:Row) WHERE toLower(toString(r.`{f_col}`)) = '{f_val.lower()}' RETURN count(r) AS count"
            else:
                cypher = "MATCH (r:Row) RETURN count(r) AS count"

            if not validate_cypher(cypher):
                return self._ungrounded_response()

            res = neo4j_client.execute_read_cypher(cypher)
            count = res[0]["count"] if res else 0

            if count > 0:
                answer = f"There are {count} customers in {matched_filter[1]}." if matched_filter else f"There are {count} rows in the dataset."
                return {
                    "answer": answer,
                    "cypher": cypher,
                    "result": res,
                    "grounded": True
                }
            else:
                return {
                    "answer": "I don't have that information in the uploaded data.",
                    "cypher": cypher,
                    "result": [],
                    "grounded": False
                }

        # CASE B: Aggregation Query (e.g. total order amount for Billing)
        if is_aggregation:
            num_col = self._find_matching_col(["order_amount", "spending", "amount", "salary"], available_cols)
            if num_col:
                agg_func = "avg" if ("avg" in q_lower or "average" in q_lower) else "sum"
                if matched_filter:
                    f_col, f_val = matched_filter
                    cypher = f"MATCH (r:Row) WHERE toLower(toString(r.`{f_col}`)) = '{f_val.lower()}' RETURN {agg_func}(toInteger(r.`{num_col}`)) AS {agg_func}_{num_col}"
                else:
                    cypher = f"MATCH (r:Row) RETURN {agg_func}(toInteger(r.`{num_col}`)) AS {agg_func}_{num_col}"

                if validate_cypher(cypher):
                    res = neo4j_client.execute_read_cypher(cypher)
                    agg_val = list(res[0].values())[0] if res else None
                    if agg_val is not None and agg_val != 0:
                        val_str = f"{agg_val:,}" if isinstance(agg_val, (int, float)) else str(agg_val)
                        return {
                            "answer": f"The {agg_func} {num_col} for {matched_filter[1] if matched_filter else 'all rows'} is {val_str}.",
                            "cypher": cypher,
                            "result": res,
                            "grounded": True
                        }

        # CASE C: List / Show Query (Multi-field return support)
        return_items = [f"r.`{col}` AS `{col}`" for col in requested_return_cols]
        return_projection = ", ".join(return_items)
        order_clause = f" ORDER BY {requested_return_cols[0]}" if requested_return_cols else ""

        if matched_filter:
            f_col, f_val = matched_filter
            cypher = f"MATCH (r:Row)\nWHERE toLower(toString(r.`{f_col}`)) = '{f_val.lower()}'\nRETURN {return_projection}{order_clause}"
        else:
            cypher = f"MATCH (r:Row)\nRETURN {return_projection}{order_clause}\nLIMIT 50"

        if not validate_cypher(cypher):
            return self._ungrounded_response()

        res = neo4j_client.execute_read_cypher(cypher)

        if res and len(res) > 0:
            count = len(res)
            filter_desc = f" {matched_filter[1]}" if matched_filter else ""
            answer = f"I found {count}{filter_desc} customer(s)."
            return {
                "answer": answer,
                "cypher": cypher,
                "result": res,
                "grounded": True
            }
        else:
            return {
                "answer": "I don't have that information in the uploaded data.",
                "cypher": cypher,
                "result": [],
                "grounded": False
            }

    def _ungrounded_response(self) -> Dict[str, Any]:
        return {
            "answer": "I don't have that information in the uploaded data.",
            "cypher": "MATCH (r:Row) RETURN count(r)",
            "result": [],
            "grounded": False
        }

chat_engine = ChatEngine()
