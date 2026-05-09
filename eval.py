import os
import json
import asyncio
from agent import run_agent
from models import Message
from retrieval import load_index
from catalog import load_catalog

# ─────────────────────────────────────────────────────────────────
# METRIC FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def recall_at_k(predicted: list[str], relevant: list[str], k: int = 10) -> float:
    """Fraction of relevant items found in top-K predictions."""
    predicted_k = predicted[:k]
    hits = len(set(predicted_k) & set(relevant))
    return hits / len(relevant) if relevant else 0.0

def precision_at_k(predicted: list[str], relevant: list[str], k: int = 10) -> float:
    """Fraction of top-K predictions that are actually relevant."""
    predicted_k = predicted[:k]
    hits = len(set(predicted_k) & set(relevant))
    return hits / len(predicted_k) if predicted_k else 0.0

def groundedness_score(recommendations: list, catalog: list[dict]) -> float:
    """
    1.0 if ALL recommendation URLs exist verbatim in catalog.json.
    Partial score based on fraction of grounded URLs.
    """
    if not recommendations:
        return 1.0  # empty recs are trivially grounded
    valid_urls = {e["url"] for e in catalog}
    grounded = sum(1 for r in recommendations if r.url in valid_urls)
    return grounded / len(recommendations)

def relevance_score(recommendations: list, expected: list[str]) -> float:
    """
    Jaccard similarity between predicted names and expected shortlist.
    Measures overlap quality regardless of ordering.
    """
    if not expected and not recommendations:
        return 1.0
    predicted_set = {r.name for r in recommendations}
    expected_set = set(expected)
    if not predicted_set | expected_set:
        return 0.0
    return len(predicted_set & expected_set) / len(predicted_set | expected_set)

def schema_compliance(resp) -> bool:
    """Hard check: response has reply, recommendations list, and end_of_conversation bool."""
    return (
        isinstance(resp.reply, str) and len(resp.reply) > 0
        and isinstance(resp.recommendations, list)
        and isinstance(resp.end_of_conversation, bool)
    )

def test_type_validity(recommendations: list) -> bool:
    """Hard check: all test_type values are from the allowed set."""
    valid_types = {"A", "B", "C", "D", "E", "K", "O", "P", "S"}
    return all(r.test_type in valid_types for r in recommendations)


# ─────────────────────────────────────────────────────────────────
# TRACE RUNNER
# ─────────────────────────────────────────────────────────────────

def run_trace(trace: dict, catalog: list[dict]) -> dict:
    """Run a single trace through the agent and collect all metrics."""
    messages = [Message(role=m["role"], content=m["content"]) for m in trace["messages"]]
    resp = asyncio.run(run_agent(messages))

    predicted_names = [r.name for r in resp.recommendations]
    expected = trace.get("expected_shortlist", [])

    return {
        "trace_id": trace.get("id", "?"),
        "expected": expected,
        "predicted": predicted_names,
        "recall_10":     recall_at_k(predicted_names, expected, k=10),
        "precision_10":  precision_at_k(predicted_names, expected, k=10),
        "groundedness":  groundedness_score(resp.recommendations, catalog),
        "relevance":     relevance_score(resp.recommendations, expected),
        "schema_ok":     schema_compliance(resp),
        "types_ok":      test_type_validity(resp.recommendations),
        "turn_count":    len(messages),
        "turn_cap_ok":   len(messages) <= 8 or not resp.end_of_conversation,
        "reply_snippet": resp.reply[:80],
    }


# ─────────────────────────────────────────────────────────────────
# HARD EVAL SUMMARY
# ─────────────────────────────────────────────────────────────────

def print_report(results: list[dict]):
    print("\n" + "=" * 60)
    print("  SHL ASSESSMENT RECOMMENDER -- EVALUATION REPORT")
    print("=" * 60)

    hard_pass = sum(1 for r in results if r["schema_ok"] and r["types_ok"] and r["groundedness"] == 1.0 and r["turn_cap_ok"])
    schema_pass = sum(1 for r in results if r["schema_ok"])
    types_pass  = sum(1 for r in results if r["types_ok"])
    ground_pass = sum(1 for r in results if r["groundedness"] == 1.0)
    turn_pass   = sum(1 for r in results if r["turn_cap_ok"])
    n = len(results)

    print(f"\n{'HARD EVALS (must be 100%)':-<45}")
    print(f"  Schema compliance :  {schema_pass}/{n}")
    print(f"  Test type validity:  {types_pass}/{n}")
    print(f"  URL groundedness  :  {ground_pass}/{n}  (0 hallucinated URLs)")
    print(f"  Turn cap honored  :  {turn_pass}/{n}")
    print(f"  -> Overall hard    :  {hard_pass}/{n} ({'PASS OK' if hard_pass == n else 'FAIL X'})")

    mean_recall   = sum(r["recall_10"] for r in results) / n
    mean_prec     = sum(r["precision_10"] for r in results) / n
    mean_relevance= sum(r["relevance"] for r in results) / n
    mean_ground   = sum(r["groundedness"] for r in results) / n

    print(f"\n{'SOFT METRICS':-<45}")
    print(f"  Mean Recall@10   :  {mean_recall:.2f}")
    print(f"  Mean Precision@10:  {mean_prec:.2f}")
    print(f"  Mean Relevance   :  {mean_relevance:.2f}  (Jaccard)")
    print(f"  Mean Groundedness:  {mean_ground:.2f}")

    print(f"\n{'PER-TRACE BREAKDOWN':-<45}")
    for r in results:
        status = "OK" if r["schema_ok"] and r["groundedness"] == 1.0 else "X"
        print(f"  [{status}] {r['trace_id']:15s}  R@10={r['recall_10']:.2f}  "
              f"Ground={r['groundedness']:.2f}  Reply: {r['reply_snippet']}...")

    overall = "READY TO DEPLOY" if hard_pass == n and mean_recall >= 0.5 else "NEEDS IMPROVEMENT"
    print("=" * 60)
    print(f"  OVERALL: {overall}")
    print("=" * 60 + "\n")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    load_index()
    catalog = load_catalog()

    traces_dir = "tests/traces/"
    traces = []
    for f in sorted(os.listdir(traces_dir)):
        if f.endswith(".json"):
            with open(os.path.join(traces_dir, f), "r", encoding="utf-8") as fp:
                traces.append(json.load(fp))

    print(f"Evaluating {len(traces)} traces...")
    results = [run_trace(t, catalog) for t in traces]
    print_report(results)
