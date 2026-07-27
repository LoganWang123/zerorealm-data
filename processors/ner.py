"""NER — Named Entity Recognition + Event Extraction via LLM.

Aligned with Execution Architecture §1.2 (Understand Context):
- EntityMention: text / entity_type / confidence
- Events: type / subject / action / object / confidence
- Topics: free-form tags

M2: LLM-based extraction, results stored in item.metadata["entities"].
M3+: migrate to structured entity_mentions table + entity resolution.
"""

from dataclasses import dataclass, field

import yaml

from crawlers.base import RawItem
from utils.logger import get_logger


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class EntityMention:
    """A single named entity extracted from text."""

    text: str
    entity_type: str          # company / person / product / technology / location
    confidence: int = 80      # 0-100

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "type": self.entity_type,
            "confidence": self.confidence,
        }


@dataclass
class EventMention:
    """A structured event extracted from text."""

    event_type: str           # financing / cooperation / expansion / ...
    subject: str              # who did it
    action: str               # what happened
    obj: str = ""             # to whom / what
    confidence: int = 80

    def to_dict(self) -> dict:
        return {
            "type": self.event_type,
            "subject": self.subject,
            "action": self.action,
            "object": self.obj,
            "confidence": self.confidence,
        }


@dataclass
class NERResult:
    """Aggregated NER output for one signal."""

    entities: list[EntityMention] = field(default_factory=list)
    events: list[EventMention] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    model: str = ""
    prompt_version: int | None = None

    def to_dict(self) -> dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "events": [ev.to_dict() for ev in self.events],
            "topics": self.topics,
            "ner_model": self.model,
            "ner_prompt_version": self.prompt_version,
        }

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def event_count(self) -> int:
        return len(self.events)

    def companies(self) -> list[str]:
        """Return all company entity texts."""
        return [e.text for e in self.entities if e.entity_type == "company"]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_ner_response(content: str) -> NERResult | None:
    """Parse LLM YAML output into NERResult. Returns None on failure."""
    try:
        text = content
        if "```yaml" in text:
            text = text.split("```yaml")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = yaml.safe_load(text.strip())
        if not isinstance(data, dict):
            return None

        entities = []
        for e in data.get("entities", []):
            if isinstance(e, dict) and "text" in e:
                entities.append(EntityMention(
                    text=str(e["text"]),
                    entity_type=e.get("type", "unknown"),
                    confidence=int(e.get("confidence", 80)),
                ))

        events = []
        for ev in data.get("events", []):
            if isinstance(ev, dict) and "type" in ev:
                events.append(EventMention(
                    event_type=ev["type"],
                    subject=ev.get("subject", ""),
                    action=ev.get("action", ""),
                    obj=ev.get("object", ""),
                    confidence=int(ev.get("confidence", 80)),
                ))

        topics = [str(t) for t in data.get("topics", []) if t]

        return NERResult(entities=entities, events=events, topics=topics)

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_entities(item: RawItem, llm_client=None) -> NERResult | None:
    """Run NER on a single item via LLM.

    Returns None when llm_client is unavailable or extraction fails.
    """
    if llm_client is None:
        return None

    logger = get_logger()

    try:
        from ai_runtime.prompt_registry import PromptRegistry

        registry = PromptRegistry()
        tpl = registry.get("ner_extraction")
        if tpl is None:
            logger.warning("[ner] Prompt 'ner_extraction' not found")
            return None

        system, user = tpl.render(
            title=item.title,
            source=item.source,
            summary=(item.summary or "")[:300],
            content=(item.content_text or "")[:800],
        )

        resp = llm_client.chat(
            task="ner_extraction",
            system=system,
            user=user,
            model=tpl.model,
            temperature=tpl.temperature,
            max_tokens=tpl.max_tokens,
            prompt_name="ner_extraction",
            prompt_version=tpl.version,
        )

        result = parse_ner_response(resp.content)
        if result is not None:
            result.model = resp.model
            result.prompt_version = tpl.version
        return result

    except Exception as e:
        logger.warning("[ner] Extraction failed for %s: %s", item.id, e)
        return None


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------


def apply_ner(
    items: list[RawItem],
    llm_client=None,
    limit: int | None = None,
) -> list[RawItem]:
    """Run NER on items, attach results to metadata.

    Parameters
    ----------
    llm_client:
        Required for LLM-based NER. When None, items are returned unchanged.
    limit:
        Max number of items to process (cost control). None = all.
    """
    logger = get_logger()

    if llm_client is None:
        logger.info("[ner] No LLM client, skipping NER")
        return items

    targets = items[:limit] if limit else items
    extracted = 0

    for item in targets:
        result = extract_entities(item, llm_client)
        if result is not None:
            item.metadata["ner"] = result.to_dict()
            extracted += 1

    logger.info(
        "[ner] Processed %d/%d items, extracted %d entities total",
        len(targets),
        len(items),
        sum(
            len(i.metadata.get("ner", {}).get("entities", []))
            for i in targets
        ),
    )

    return items
