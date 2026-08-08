# Media Generation Policy

## Core architecture (Content Launch 01+)

```
ResearchBrief / Article
  → MediaJob / ImageBrief
  → Current IDE Agent (Cursor / Codex / other) generates the file
  → attach via scripts/media_job.py
  → validation + SHA review
  → approved only → upload / content package
```

### IDE Agent is NOT a production runtime provider

- Do **not** implement `CursorImageProvider` / `CodexImageProvider`
- Do **not** call Cursor/Codex APIs from Python/Node
- MediaJob is IDE-agnostic; any agent can fill the same job

### Image classes

| Class | Method |
|-------|--------|
| Infographic / data | Programmatic (SVG/Pillow/Next) — never AI text/numbers |
| Brand cover / OG | Programmatic template; optional IDE **text-free** background + overlay |
| Scene photography | IDE-native generation only |

### Agnes

- **Deprecated** for all new image generation
- **No Agnes fallback**
- Production Agnes image invocation must remain **0**

### Compatibility helpers

`LocalImageGenerator` may still render **programmatic brand covers** for WeChat dimensions.
It must **not** fabricate scene photography placeholders.
`ZEROREALM_LOCAL_IMAGE_CMD` is optional compatibility only — not the core strategy.

### Status

`pending_generation` → `generated`/`pending_review` → `approved` | `rejected`

Only `approved` may upload. Publish gate ignores `generatorAgent`.
