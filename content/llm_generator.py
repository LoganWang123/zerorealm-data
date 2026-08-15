"""LLM-backed controlled content generator (DeepSeek V4 via LLMClient)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

import yaml

from ai_runtime.client import LLMClient, LLMResponse
from content.allowed_facts import AllowedFactsContext
from content.generator import (
    ContentGenerator,
    DraftSection,
    DraftStatement,
    StructuredDraft,
    make_draft_id,
)
from content.llm_models import (
    DEFAULT_DEEPSEEK_MODEL,
    LLMConfigError,
    assert_supported_model,
    normalize_deepseek_base_url,
    resolve_llm_api_key,
)
from content.models import ContentCandidate
from utils.helpers import now_iso

ALLOWED_STATEMENT_TYPES = frozenset(
    {"FACT", "INFERENCE", "HYPOTHESIS", "EXPERIMENT_PARAMETER"}
)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "config" / "prompts" / "controlled_content_generation.yaml"
PROMPT_PATH_V2 = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "prompts"
    / "controlled_content_generation_v2.yaml"
)


class GenerationError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or code
        super().__init__(f"{self.code}: {self.message}")


def load_generation_prompt(path: Path | None = None, *, version: int | None = None) -> dict:
    if path is not None:
        p = path
    elif version == 2 or str(os.getenv("CONTENT_GENERATOR_PROMPT_VERSION") or "") == "2":
        p = PROMPT_PATH_V2
    else:
        # Historic default remains v1 unless CONTENT_GENERATOR_PROMPT_VERSION=2.
        p = PROMPT_PATH
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data


def prompt_hash(prompt: dict) -> str:
    raw = json.dumps(
        {
            "name": prompt.get("name"),
            "version": prompt.get("version"),
            "system": prompt.get("system"),
            "schema_instructions": prompt.get("schema_instructions"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _budget_int(name: str, default: int, env: dict[str, str] | None = None) -> int:
    source = env if env is not None else os.environ
    raw = source.get(name)
    if raw is None or raw == "":
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def build_user_payload(context: AllowedFactsContext) -> str:
    payload = {
        "content_candidate_id": context.content_candidate_id,
        "content_type": context.content_type,
        "working_title": context.working_title,
        "primary_signal": context.primary_signal,
        "research_question": context.research_question,
        "allowed_claims": [c.to_dict() for c in context.allowed_claims],
        "allowed_numeric_claims": [c.to_dict() for c in context.allowed_numeric_claims],
        "allowed_sources": [s.to_dict() for s in context.allowed_sources],
        "fact_inference_boundaries": context.fact_inference_boundaries,
        "evidence_gaps": context.evidence_gaps,
        "prohibited_claims": context.prohibited_claims,
        "experiment_parameters": context.experiment_parameters,
        "content_requirements": context.content_requirements,
        "allowed_entities": context.allowed_entities,
        "allowed_numbers": context.allowed_numbers,
    }
    return (
        "Write a StructuredDraft JSON object using ONLY the Allowed Facts below.\n"
        "Return JSON only.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _extract_json_object(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise GenerationError("GENERATOR_SCHEMA_INVALID", "Empty model response")
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise GenerationError("GENERATOR_SCHEMA_INVALID", "No JSON object in response")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise GenerationError("GENERATOR_SCHEMA_INVALID", f"JSON parse failed: {exc}") from exc
    if not isinstance(data, dict):
        raise GenerationError("GENERATOR_SCHEMA_INVALID", "JSON root must be object")
    return data


def validate_structured_payload(data: dict) -> dict:
    if not isinstance(data.get("title"), str) or not data.get("title"):
        raise GenerationError("GENERATOR_SCHEMA_INVALID", "title required")
    if not isinstance(data.get("summary"), str):
        raise GenerationError("GENERATOR_SCHEMA_INVALID", "summary required")
    sections = data.get("sections")
    statements = data.get("statements")
    if not isinstance(sections, list):
        raise GenerationError("GENERATOR_SCHEMA_INVALID", "sections must be list")
    if not isinstance(statements, list) or not statements:
        raise GenerationError("GENERATOR_SCHEMA_INVALID", "statements must be non-empty list")
    for i, stmt in enumerate(statements):
        if not isinstance(stmt, dict):
            raise GenerationError("GENERATOR_SCHEMA_INVALID", f"statement[{i}] not object")
        stype = str(stmt.get("statement_type") or "").upper()
        if stype not in ALLOWED_STATEMENT_TYPES:
            raise GenerationError(
                "GENERATOR_SCHEMA_INVALID",
                f"statement[{i}] invalid statement_type={stmt.get('statement_type')}",
            )
        if not str(stmt.get("text") or "").strip():
            raise GenerationError("GENERATOR_SCHEMA_INVALID", f"statement[{i}] text required")
    return data


def payload_to_draft(
    data: dict,
    *,
    context: AllowedFactsContext,
    candidate: ContentCandidate | None,
    provider: str,
    metadata: dict,
) -> StructuredDraft:
    content_id = (candidate.content_id if candidate else "") or f"ct-{context.content_candidate_id}"
    slug = (candidate.slug if candidate else "") or "draft-slug"
    sections = [DraftSection.from_dict(s if isinstance(s, dict) else {}) for s in data.get("sections") or []]
    statements = [
        DraftStatement.from_dict(s if isinstance(s, dict) else {}) for s in data.get("statements") or []
    ]
    return StructuredDraft(
        draft_id=make_draft_id(content_id),
        content_id=content_id,
        content_type=context.content_type,
        title=str(data.get("title") or context.working_title),
        summary=str(data.get("summary") or context.research_question),
        sections=sections,
        statements=statements,
        slug=slug,
        status="DRAFT",
        generated_at=now_iso(),
        generator_provider=provider,
        metadata=metadata,
    )


class LLMContentGenerator(ContentGenerator):
    """OpenAI-compatible LLM generator. DeepSeek is the production provider."""

    name = "llm"

    def __init__(
        self,
        *,
        provider: str = "deepseek",
        model: str | None = None,
        client: LLMClient | None = None,
        client_factory: Callable[..., LLMClient] | None = None,
        prompt: dict | None = None,
        require_live_flag: bool = True,
        env: dict[str, str] | None = None,
    ) -> None:
        self.provider = (provider or "deepseek").lower()
        self.env = env if env is not None else os.environ
        self.require_live_flag = require_live_flag
        self.prompt = prompt or load_generation_prompt()
        self.model = assert_supported_model(
            model
            or self.env.get("CONTENT_GENERATOR_MODEL")
            or self.prompt.get("model")
            or self.env.get("LLM_MODEL")
            or DEFAULT_DEEPSEEK_MODEL
        )
        self._client = client
        self._client_factory = client_factory
        self.name = self.provider
        self._calls = 0
        self.max_calls = _budget_int("CONTENT_GENERATOR_MAX_CALLS_PER_RUN", 4, dict(self.env))
        self.max_input_tokens = _budget_int("CONTENT_GENERATOR_MAX_INPUT_TOKENS", 8000, dict(self.env))
        self.max_output_tokens = _budget_int(
            "CONTENT_GENERATOR_MAX_OUTPUT_TOKENS",
            int(self.prompt.get("max_tokens") or 2000),
            dict(self.env),
        )

    def _ensure_live_allowed(self) -> None:
        if not self.require_live_flag:
            return
        if str(self.env.get("CONTENT_GENERATOR_ALLOW_LIVE", "0")).strip() != "1":
            raise GenerationError(
                "LIVE_GENERATOR_DISABLED",
                "Set CONTENT_GENERATOR_ALLOW_LIVE=1 to enable live generation",
            )
        key = resolve_llm_api_key(dict(self.env))
        if not key:
            raise GenerationError(
                "LLM_API_KEY_MISSING",
                "LLM_API_KEY is required (canonical). DEEPSEEK_API_KEY is fallback only.",
            )

    def _get_client(self) -> LLMClient:
        if self._client is not None:
            return self._client
        key = resolve_llm_api_key(dict(self.env))
        base = normalize_deepseek_base_url(
            self.env.get("LLM_BASE_URL") or "https://api.deepseek.com"
        )
        factory = self._client_factory or LLMClient
        self._client = factory(api_key=key, base_url=base, model=self.model)
        return self._client

    def _consume_call(self) -> None:
        if self._calls >= self.max_calls:
            raise GenerationError(
                "LLM_GENERATION_BUDGET_EXCEEDED",
                f"max calls per run exceeded ({self.max_calls})",
            )
        self._calls += 1

    def _chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        task: str,
    ) -> LLMResponse:
        self._consume_call()
        client = self._get_client()
        return client.chat(
            task=task,
            system=system,
            user=user,
            model=self.model,
            temperature=temperature,
            max_tokens=self.max_output_tokens,
            prompt_name=str(self.prompt.get("name") or "controlled_content_generation"),
            prompt_version=int(self.prompt.get("version") or 1),
            response_format={"type": "json_object"},
        )

    def generate(
        self,
        context: AllowedFactsContext,
        *,
        candidate: ContentCandidate | None = None,
    ) -> StructuredDraft:
        self._ensure_live_allowed()
        if not context.live_verified_store:
            raise GenerationError(
                "LIVE_GENERATOR_REQUIRES_VERIFIED_ATOM_STORE",
                "Live DeepSeek generation requires ResearchAtomStore-backed Allowed Facts",
            )
        if not context.allowed_claims:
            raise GenerationError(
                "LIVE_GENERATOR_REQUIRES_VERIFIED_ATOM_STORE",
                "No VERIFIED allowed claims available for live generation",
            )

        system = str(self.prompt.get("system") or "")
        schema_instructions = str(self.prompt.get("schema_instructions") or "")
        system_full = f"{system}\n\n{schema_instructions}".strip()
        user = build_user_payload(context)
        temperature = float(self.prompt.get("temperature") or 0.3)

        lineage_calls: list[dict] = []
        schema_repair_attempts = 0
        resp = self._chat(
            system=system_full,
            user=user,
            temperature=temperature,
            task="controlled_content_generation",
        )
        lineage_calls.append(resp.lineage())

        try:
            payload = validate_structured_payload(_extract_json_object(resp.content))
        except GenerationError:
            schema_repair_attempts = 1
            repair_system = (
                system_full
                + "\n\nSCHEMA REPAIR ONLY: fix JSON structure/enums/types. "
                "Do NOT add facts, numbers, entities, sources, or claims."
            )
            repair_user = (
                "The previous response failed schema validation. "
                "Return a corrected StructuredDraft JSON only.\n\n"
                f"Previous response:\n{resp.content[:6000]}"
            )
            resp = self._chat(
                system=repair_system,
                user=repair_user,
                temperature=0.0,
                task="controlled_content_generation_schema_repair",
            )
            lineage_calls.append(resp.lineage())
            try:
                payload = validate_structured_payload(_extract_json_object(resp.content))
            except GenerationError as exc:
                raise GenerationError("GENERATOR_SCHEMA_INVALID", exc.message) from exc

        ph = prompt_hash(self.prompt)
        metadata = {
            "generator_provider": self.provider,
            "generator_model": self.model,
            "prompt_name": self.prompt.get("name"),
            "prompt_version": self.prompt.get("version"),
            "prompt_hash": ph,
            "llm_lineage": {
                "operator": "model",
                "provider": self.provider,
                "model": self.model,
                "task": "controlled_content_generation",
                "prompt_name": self.prompt.get("name"),
                "prompt_version": self.prompt.get("version"),
                "prompt_hash": ph,
                "calls": lineage_calls,
                "schema_repair_attempts": schema_repair_attempts,
                "content_repair_attempts": 0,
                "prompt_tokens": sum(c.get("prompt_tokens", 0) for c in lineage_calls),
                "completion_tokens": sum(c.get("completion_tokens", 0) for c in lineage_calls),
                "latency_ms": sum(c.get("latency_ms", 0) for c in lineage_calls),
                "estimated_cost_cny": round(sum(float(c.get("cost_cny") or 0) for c in lineage_calls), 6),
                "estimated": True,
            },
            "allowed_claim_ids": [c.claim_id for c in context.allowed_claims],
            "allowed_source_ids": [s.source_document_id for s in context.allowed_sources],
            "generated_at": now_iso(),
            "schema_repair_attempts": schema_repair_attempts,
        }
        return payload_to_draft(
            payload,
            context=context,
            candidate=candidate,
            provider=self.provider,
            metadata=metadata,
        )


# Alias requested by product naming
DeepSeekContentGenerator = LLMContentGenerator
