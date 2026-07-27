"""Knowledge Processor — build knowledge base from NER results.

Bridges Understand Context (NER) → Knowledge Context (KnowledgeObject / Relation).

Pipeline position: after NER, before daily report generation.
Takes items with metadata["ner"] and resolves entities into the KB.

Usage::

    from processors.knowledge import apply_knowledge
    from knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    items = apply_knowledge(items, store)
    store.save()
"""

from __future__ import annotations

from crawlers.base import RawItem
from knowledge import generate_entity_id, generate_relation_id
from knowledge.store import KnowledgeStore
from utils.logger import get_logger

# Event type → relation type mapping
EVENT_TO_RELATION: dict[str, str] = {
    "financing": "invest",
    "cooperation": "cooperate",
    "expansion": "compete",       # expansion implies competitive dynamics
    "product_launch": "supply",   # product launch → supply chain
    "policy": "cooperate",        # policy → regulatory relationship
    "competition": "compete",
    "technology": "supply",       # tech provider → supply
}

# Known company aliases (seed data from boost.yaml company_keywords)
KNOWN_COMPANIES: dict[str, dict] = {
    "友宝": {"role": "operator", "segment": "vending"},
    "友宝在线": {"role": "operator", "segment": "vending"},
    "丰e足食": {"role": "operator", "segment": "vending"},
    "便利蜂": {"role": "operator", "segment": "convenience"},
    "美团": {"role": "operator", "segment": "instant_retail"},
    "元气森林": {"role": "brand", "segment": "beverage"},
    "农夫山泉": {"role": "brand", "segment": "beverage"},
    "可口可乐": {"role": "brand", "segment": "beverage"},
    "伊利": {"role": "brand", "segment": "dairy"},
    "蒙牛": {"role": "brand", "segment": "dairy"},
    "康师傅": {"role": "brand", "segment": "instant_food"},
    "三只松鼠": {"role": "brand", "segment": "snack"},
    "商汤": {"role": "technology", "segment": "ai"},
    "商汤科技": {"role": "technology", "segment": "ai"},
    "旷视": {"role": "technology", "segment": "ai"},
    "旷视科技": {"role": "technology", "segment": "ai"},
    "海康威视": {"role": "technology", "segment": "ai_vision"},
    "移远通信": {"role": "technology", "segment": "iot"},
    "涂鸦智能": {"role": "technology", "segment": "iot"},
    "顺丰": {"role": "channel", "segment": "logistics"},
    "万科": {"role": "channel", "segment": "property"},
}


def _infer_industry_role(entity_text: str, entity_type: str) -> str:
    """Infer industry_role from known companies or entity type."""
    # Check known companies (match by containment)
    for name, info in KNOWN_COMPANIES.items():
        if name in entity_text or entity_text in name:
            return info["role"]

    # Fallback by entity type
    type_role_map = {
        "company": "",
        "person": "",
        "product": "vendor",
        "technology": "technology",
        "location": "channel",
    }
    return type_role_map.get(entity_type, "")


def _infer_segment(entity_text: str) -> str:
    """Infer industry_segment from known companies."""
    for name, info in KNOWN_COMPANIES.items():
        if name in entity_text or entity_text in name:
            return info["segment"]
    return ""


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process_item_knowledge(
    item: RawItem,
    store: KnowledgeStore,
) -> dict:
    """Process a single item's NER results into the knowledge store.

    Returns a summary dict with counts.
    """
    ner = item.metadata.get("ner", {})
    if not ner:
        return {"entities_resolved": 0, "relations_created": 0}

    entities = ner.get("entities", [])
    events = ner.get("events", [])

    resolved_ids: dict[str, str] = {}  # entity_text → object_id
    entities_resolved = 0
    relations_created = 0

    # Step 1: Resolve entities
    for ent in entities:
        text = ent.get("text", "").strip()
        ent_type = ent.get("type", "company")
        confidence = ent.get("confidence", 60)

        if not text or len(text) < 2:
            continue

        role = _infer_industry_role(text, ent_type)
        obj = store.resolve_or_create(
            name=text,
            entity_type=ent_type,
            signal_id=item.id,
            industry_role=role,
            confidence=confidence,
        )
        resolved_ids[text] = obj.id
        entities_resolved += 1

    # Step 2: Create relations from events
    for event in events:
        event_type = event.get("type", "")
        subject = event.get("subject", "").strip()
        obj_text = event.get("object", "").strip()
        confidence = event.get("confidence", 50)

        relation_type = EVENT_TO_RELATION.get(event_type)
        if not relation_type:
            continue

        # Resolve subject
        subject_id = resolved_ids.get(subject)
        if not subject_id and subject:
            subj_obj = store.resolve_or_create(
                name=subject,
                entity_type="company",
                signal_id=item.id,
                industry_role=_infer_industry_role(subject, "company"),
            )
            subject_id = subj_obj.id
            resolved_ids[subject] = subject_id

        # Resolve object (if present)
        object_id = resolved_ids.get(obj_text) if obj_text else None
        if not object_id and obj_text:
            obj_obj = store.resolve_or_create(
                name=obj_text,
                entity_type="company",
                signal_id=item.id,
                industry_role=_infer_industry_role(obj_text, "company"),
            )
            object_id = obj_obj.id
            resolved_ids[obj_text] = object_id

        # Create relation (need both sides)
        if subject_id and object_id:
            rel = store.add_relation(
                from_id=subject_id,
                to_id=object_id,
                relation_type=relation_type,
                signal_id=item.id,
                confidence=confidence,
            )
            if rel:
                relations_created += 1

    return {"entities_resolved": entities_resolved, "relations_created": relations_created}


# ---------------------------------------------------------------------------
# Batch API
# ---------------------------------------------------------------------------


def apply_knowledge(
    items: list[RawItem],
    store: KnowledgeStore | None = None,
    persist: bool = True,
) -> list[RawItem]:
    """Process all items' NER results into the knowledge store.

    Parameters
    ----------
    items:
        Items with metadata["ner"] populated (from apply_ner).
    store:
        KnowledgeStore instance. Creates default if None.
    persist:
        Whether to save the store after processing.

    Returns items unchanged (side-effect: store is updated).
    """
    logger = get_logger()

    if store is None:
        store = KnowledgeStore()

    total_entities = 0
    total_relations = 0
    items_with_ner = 0

    for item in items:
        if not item.metadata.get("ner"):
            continue
        items_with_ner += 1
        result = process_item_knowledge(item, store)
        total_entities += result["entities_resolved"]
        total_relations += result["relations_created"]

    logger.info(
        "[knowledge] Processed %d items: %d entities resolved, %d relations created. "
        "KB size: %d objects, %d relations",
        items_with_ner,
        total_entities,
        total_relations,
        store.object_count,
        store.relation_count,
    )

    if persist:
        store.save()

    return items
