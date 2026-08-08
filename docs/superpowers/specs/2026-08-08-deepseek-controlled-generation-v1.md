# DeepSeek Controlled Generation v1

## Pipeline position

```
Discovery / Registry
→ Research
→ Human Claim Verification
→ Knowledge
→ Content Candidate
→ Allowed Facts (VERIFIED only)
→ DeepSeek V4 Flash (writer)
→ Structured Draft
→ Deterministic Audit
→ Hard Gate
→ Human Editorial Review
→ Render
→ Human Channel Review
→ Controlled Publisher
```

## Principle

**DeepSeek is a writer, not a source of truth.**

LLM output never upgrades `ClaimStatus`, never grants Editorial/Channel approval,
and never bypasses Hard Gate.

## Provider selection

- Default: `CONTENT_GENERATOR_PROVIDER=mock`
- Live: `CONTENT_GENERATOR_PROVIDER=deepseek` **and** `CONTENT_GENERATOR_ALLOW_LIVE=1`
- Presence of `LLM_API_KEY` alone does **not** enable live generation
- Unknown provider → `UNKNOWN_CONTENT_GENERATOR_PROVIDER` (no silent mock fallback)

## Models

- Default: `deepseek-v4-flash`
- Optional: `deepseek-v4-pro` (explicit only)
- Retired: `deepseek-chat`, `deepseek-reasoner` → `DEEPSEEK_LEGACY_MODEL`

Canonical secret: `LLM_API_KEY` (optional fallback `DEEPSEEK_API_KEY`).
