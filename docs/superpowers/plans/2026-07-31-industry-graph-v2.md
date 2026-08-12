# Industry Graph V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing file-backed knowledge base so it can store the Industry Graph V2 taxonomy, evidence-backed relationships, and graph queries needed by ZeroRealm Research.

**Architecture:** Retain `KnowledgeObject` and `Relation` as the canonical persisted models, but introduce an explicit schema module for the L0–L7 taxonomy and relation vocabulary. Evidence is represented as structured relation metadata in the first implementation to keep the JSON storage format backward-compatible; store/query methods validate graph writes and expose deterministic graph-filtered reads.

**Tech Stack:** Python 3.11, dataclasses, JSON persistence, pytest, Ruff.

## Global Constraints

- Preserve compatibility with existing `data/knowledge/kb.json` files missing new metadata fields.
- Never infer or manufacture evidence; an evidence-backed relation requires a non-empty source URL, source date, and evidence level `A`, `B`, or `C`.
- Keep canonical entity IDs and relation IDs deterministic.
- Keep all current public methods in `knowledge/store.py` callable with their current arguments.
- Run pytest and Ruff from `zerorealm-data` before every commit.

---

## File Structure

- Create `knowledge/industry_graph.py`: L0–L7 roles, valid relation types, evidence validation, graph query value objects.
- Modify `knowledge/__init__.py`: serialize the added graph attributes while preserving old JSON loading.
- Modify `knowledge/store.py`: validate evidence-backed writes and add role/layer/relation queries.
- Create `tests/test_industry_graph.py`: taxonomy, evidence, persistence, and graph-query regression tests.
- Modify `tests/test_knowledge.py`: confirm old relation construction and loading remain backward compatible.

### Task 1: Define the graph taxonomy and validation boundary

**Files:**
- Create: `knowledge/industry_graph.py`
- Test: `tests/test_industry_graph.py`

**Interfaces:**
- Produces `INDUSTRY_LAYERS: dict[str, str]`, `VALID_RELATION_TYPES: frozenset[str]`.
- Produces `EvidenceRef(url: str, published_at: str, level: str, source_name: str = "")`.
- Produces `validate_relation_evidence(relation_type: str, evidence: EvidenceRef | None) -> None`.

- [ ] **Step 1: Write the failing taxonomy and evidence tests**

```python
from knowledge.industry_graph import EvidenceRef, validate_relation_evidence

def test_valid_relation_evidence_requires_url_date_and_allowed_level():
    evidence = EvidenceRef("https://example.com/news", "2026-07-31", "A")
    validate_relation_evidence("supply", evidence)

def test_invalid_evidence_level_is_rejected():
    evidence = EvidenceRef("https://example.com/news", "2026-07-31", "D")
    with pytest.raises(ValueError, match="evidence level"):
        validate_relation_evidence("supply", evidence)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest tests/test_industry_graph.py -q`  
Expected: FAIL because `knowledge.industry_graph` does not exist.

- [ ] **Step 3: Implement the smallest explicit vocabulary**

```python
INDUSTRY_LAYERS = {
    "L0": "regulator_association", "L1": "brand", "L2": "supply_chain",
    "L3": "operator", "L4": "hardware", "L5": "ai_saas_iot",
    "L6": "instant_retail", "L7": "infrastructure",
}
VALID_RELATION_TYPES = frozenset({"supply", "purchase", "use", "integrate", "cooperate", "invest", "compete", "deliver", "pay"})
```

- [ ] **Step 4: Run focused tests and lint**

Run: `python -m pytest tests/test_industry_graph.py -q; python -m ruff check knowledge/industry_graph.py tests/test_industry_graph.py`  
Expected: tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit**

```bash
git add knowledge/industry_graph.py tests/test_industry_graph.py
git commit -m "feat: define industry graph taxonomy"
```

### Task 2: Persist an entity's graph layer and secondary roles

**Files:**
- Modify: `knowledge/__init__.py`
- Modify: `knowledge/store.py`
- Modify: `tests/test_knowledge.py`

**Interfaces:**
- `KnowledgeObject.metadata["graph_layer"]` holds an L0–L7 key.
- `KnowledgeObject.metadata["secondary_roles"]` holds a unique list of layer role values.
- `KnowledgeStore.resolve_or_create(..., graph_layer: str = "") -> KnowledgeObject` accepts an optional graph layer.

- [ ] **Step 1: Write the failing persistence test**

```python
def test_graph_layer_survives_store_save_and_load(tmp_path):
    path = str(tmp_path / "kb.json")
    store = KnowledgeStore(path)
    company = store.resolve_or_create("测试运营商", "company", graph_layer="L3")
    store.save()
    restored = KnowledgeStore(path).get(company.id)
    assert restored.metadata["graph_layer"] == "L3"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest tests/test_knowledge.py::TestKnowledgeStore::test_graph_layer_survives_store_save_and_load -q`  
Expected: FAIL because `resolve_or_create` has no `graph_layer` parameter.

- [ ] **Step 3: Add optional validated graph-layer assignment**

Validate non-empty values against `INDUSTRY_LAYERS`; write the value only into `metadata`, so old object JSON remains readable. During `_load`, retain existing metadata when the key is absent.

- [ ] **Step 4: Run regression tests and lint**

Run: `python -m pytest tests/test_knowledge.py tests/test_industry_graph.py -q; python -m ruff check knowledge/__init__.py knowledge/store.py tests/test_knowledge.py`  
Expected: all selected tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit**

```bash
git add knowledge/__init__.py knowledge/store.py tests/test_knowledge.py
git commit -m "feat: persist industry graph layers"
```

### Task 3: Store evidence-backed relationship metadata

**Files:**
- Modify: `knowledge/store.py`
- Modify: `tests/test_industry_graph.py`

**Interfaces:**
- `KnowledgeStore.add_relation(..., evidence: EvidenceRef | None = None, status: str = "confirmed") -> Relation | None`.
- An evidence object serializes into `Relation.metadata["evidence"]` with `url`, `published_at`, `level`, and `source_name`.
- Supported statuses: `confirmed`, `observed`, `revoked`; `confirmed` requires A/B/C evidence.

- [ ] **Step 1: Write the failing relationship-evidence tests**

```python
def test_confirmed_relation_persists_evidence(store):
    a = store.resolve_or_create("品牌 A", "company")
    b = store.resolve_or_create("运营商 B", "company")
    relation = store.add_relation(
        a.id, b.id, "supply",
        evidence=EvidenceRef("https://example.com", "2026-07-31", "A"),
    )
    assert relation.metadata["status"] == "confirmed"
    assert relation.metadata["evidence"]["level"] == "A"
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python -m pytest tests/test_industry_graph.py -q`  
Expected: FAIL because `add_relation` does not accept `evidence`.

- [ ] **Step 3: Implement evidence serialization without breaking old calls**

Keep `signal_id` and `confidence` behaviour unchanged. For duplicate relation IDs, merge missing evidence/status metadata rather than silently discarding a stronger later source.

- [ ] **Step 4: Run focused tests, full knowledge tests, and lint**

Run: `python -m pytest tests/test_industry_graph.py tests/test_knowledge.py -q; python -m ruff check knowledge tests/test_industry_graph.py tests/test_knowledge.py`  
Expected: tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit**

```bash
git add knowledge/store.py tests/test_industry_graph.py
git commit -m "feat: store evidence-backed graph relations"
```

### Task 4: Add deterministic graph queries

**Files:**
- Modify: `knowledge/store.py`
- Modify: `tests/test_industry_graph.py`

**Interfaces:**
- `KnowledgeStore.list_objects_by_layer(graph_layer: str) -> list[KnowledgeObject]`.
- `KnowledgeStore.list_relations(relation_type: str | None = None, min_evidence_level: str | None = None, status: str = "confirmed") -> list[Relation]`.

- [ ] **Step 1: Write the failing query tests**

```python
def test_list_relations_filters_to_confirmed_a_or_b_evidence(store):
    # create one A-level confirmed relation and one observed relation
    relations = store.list_relations(min_evidence_level="B")
    assert [item.relation_type for item in relations] == ["supply"]
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python -m pytest tests/test_industry_graph.py -q`  
Expected: FAIL because graph query methods do not exist.

- [ ] **Step 3: Implement stable filter semantics**

Sort objects by canonical name and relations by `(relation_type, from_id, to_id)`. Treat evidence levels as A > B > C; ignore relations without evidence when a minimum level is requested.

- [ ] **Step 4: Run full test and lint suite**

Run: `python -m pytest -q; python -m ruff check .`  
Expected: pytest exits 0 and Ruff exits 0.

- [ ] **Step 5: Commit**

```bash
git add knowledge/store.py tests/test_industry_graph.py
git commit -m "feat: add industry graph queries"
```

### Task 5: Seed the verified working set only after source review

**Files:**
- Create: `data/knowledge/industry-graph-seed.json`
- Create: `tests/test_industry_graph_seed.py`

**Interfaces:**
- Seed JSON shape: `{ "version": 2, "objects": [], "relations": [] }`.
- Every seeded object has a `metadata.graph_layer` value.
- Every seeded relation has `metadata.status == "confirmed"` and an A/B/C evidence record.

- [ ] **Step 1: Write the failing seed contract test**

```python
def test_seed_relations_are_evidence_backed():
    payload = json.loads(Path("data/knowledge/industry-graph-seed.json").read_text("utf-8"))
    assert all(item["metadata"]["graph_layer"] in INDUSTRY_LAYERS for item in payload["objects"])
    assert all(item["metadata"]["evidence"]["level"] in {"A", "B", "C"} for item in payload["relations"])
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/test_industry_graph_seed.py -q`  
Expected: FAIL because the seed file does not exist.

- [ ] **Step 3: Create a small, audited seed**

Seed only entities and relationships with reviewed public sources. Do not bulk-seed the 80–120 candidate list as confirmed data; keep unverified candidates in the editorial whitelist rather than the factual graph.

- [ ] **Step 4: Run complete verification**

Run: `python -m pytest -q; python -m ruff check .`  
Expected: pytest exits 0 and Ruff exits 0.

- [ ] **Step 5: Commit**

```bash
git add data/knowledge/industry-graph-seed.json tests/test_industry_graph_seed.py
git commit -m "feat: add audited industry graph seed"
```

## Plan Self-Review

- **Coverage:** taxonomy, entity layers, evidence, relationship validation, queries, audited seeding, persistence and regression tests each map to a task.
- **No placeholders:** no task depends on undefined future APIs; the exact public methods and metadata keys are defined above.
- **Compatibility:** existing `KnowledgeStore` APIs remain valid because all new arguments are optional and old JSON lacks only optional metadata.
- **Scope:** website graph visualization, automated web verification, and Agent reasoning are deliberately excluded from this plan; they depend on the verified graph contract established here.
