"""NER Evaluation — measure Precision / Recall / F1 against Golden Set.

Usage::

    python -m tests.eval_ner                    # run with real LLM
    python -m tests.eval_ner --dry-run          # parse-only (no LLM)

Aligned with Execution Architecture §5.6 (Evaluation Hook) and
§2.9 (golden_sets table).
"""

import os
import sys

import yaml

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from processors.ner import parse_ner_response, NERResult


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def entity_match(predicted: list[dict], expected: list[dict]) -> dict:
    """Compute entity-level P/R/F1.

    Matching rule: predicted entity matches expected if
    - type matches exactly AND
    - text overlaps (one contains the other, or exact match)
    """
    tp = 0
    matched_pred = set()

    for exp in expected:
        exp_text = exp["text"]
        exp_type = exp["type"]
        for i, pred in enumerate(predicted):
            if i in matched_pred:
                continue
            if pred.get("type") != exp_type:
                continue
            pred_text = pred.get("text", "")
            # Fuzzy match: containment in either direction
            if exp_text in pred_text or pred_text in exp_text:
                tp += 1
                matched_pred.add(i)
                break

    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(expected) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp}


def event_match(predicted: list[dict], expected: list[dict]) -> dict:
    """Compute event-level P/R/F1.

    Matching rule: type matches AND subject overlaps.
    """
    tp = 0
    matched_pred = set()

    for exp in expected:
        exp_type = exp["type"]
        exp_subject = exp.get("subject", "")
        for i, pred in enumerate(predicted):
            if i in matched_pred:
                continue
            if pred.get("type") != exp_type:
                continue
            pred_subject = pred.get("subject", "")
            if not exp_subject or exp_subject in pred_subject or pred_subject in exp_subject:
                tp += 1
                matched_pred.add(i)
                break

    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(expected) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp}


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------


def load_golden_set(path: str | None = None) -> list[dict]:
    """Load golden set YAML."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "golden_sets", "ner_golden_v1.yaml")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


def evaluate_predictions(cases: list[dict], predictions: list[NERResult | None]) -> dict:
    """Evaluate predictions against golden set cases."""
    entity_metrics_all = []
    event_metrics_all = []

    for case, pred in zip(cases, predictions):
        expected = case.get("expected", {})
        exp_entities = expected.get("entities", [])
        exp_events = expected.get("events", [])

        if pred is None:
            # Failed prediction → 0 scores
            entity_metrics_all.append({"precision": 0, "recall": 0, "f1": 0, "tp": 0})
            event_metrics_all.append({"precision": 0, "recall": 0, "f1": 0, "tp": 0})
            continue

        pred_entities = [e.to_dict() for e in pred.entities]
        pred_events = [ev.to_dict() for ev in pred.events]

        entity_metrics_all.append(entity_match(pred_entities, exp_entities))
        event_metrics_all.append(event_match(pred_events, exp_events))

    # Aggregate (macro average)
    n = len(cases)
    avg_entity = {
        "precision": sum(m["precision"] for m in entity_metrics_all) / n,
        "recall": sum(m["recall"] for m in entity_metrics_all) / n,
        "f1": sum(m["f1"] for m in entity_metrics_all) / n,
    }
    avg_event = {
        "precision": sum(m["precision"] for m in event_metrics_all) / n,
        "recall": sum(m["recall"] for m in event_metrics_all) / n,
        "f1": sum(m["f1"] for m in event_metrics_all) / n,
    }

    return {
        "total_cases": n,
        "entity": avg_entity,
        "event": avg_event,
        "per_case_entities": entity_metrics_all,
        "per_case_events": event_metrics_all,
    }


def run_evaluation(llm_client=None, golden_path: str | None = None) -> dict:
    """Run full NER evaluation.

    When llm_client is None, returns empty results (dry-run mode).
    """
    cases = load_golden_set(golden_path)

    if llm_client is None:
        print(f"[eval] Dry-run: {len(cases)} cases loaded, no LLM client.")
        return {"total_cases": len(cases), "entity": {}, "event": {}}

    from crawlers.base import RawItem
    from processors.ner import extract_entities

    predictions: list[NERResult | None] = []
    for case in cases:
        inp = case["input"]
        item = RawItem(
            id=case["id"],
            source=inp.get("source", "test"),
            source_type="rss",
            language="zh-CN",
            title=inp["title"],
            url="",
            published_at="2026-07-26T08:00:00+08:00",
            crawled_at="2026-07-26T09:00:00+08:00",
            run_id="eval",
            crawl_status="success",
            http_status=200,
            content_html="",
            content_text=inp.get("summary", ""),
            summary=inp.get("summary", ""),
            author="",
            metadata={},
        )
        result = extract_entities(item, llm_client)
        predictions.append(result)

    return evaluate_predictions(cases, predictions)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="NER Evaluation")
    parser.add_argument("--dry-run", action="store_true", help="Load golden set only")
    parser.add_argument("--golden", type=str, help="Path to golden set YAML")
    args = parser.parse_args()

    if args.dry_run:
        result = run_evaluation(llm_client=None, golden_path=args.golden)
    else:
        from ai_runtime.client import LLMClient

        client = LLMClient()
        result = run_evaluation(llm_client=client, golden_path=args.golden)

    print(json.dumps(result, ensure_ascii=False, indent=2))
