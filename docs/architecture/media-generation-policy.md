# Media Generation Policy

- Agnes **deprecated** for image generation
- Active provider: **local** (`LocalImageGenerator` / programmatic templates)
- **No Agnes fallback**
- Chinese text on covers/OG: **programmatic overlay** (Pillow / next/og), not diffusion text
- Only **approved** media (SHA-reviewed) may enter WeChat upload / content packages
- External publish requires human approval
- Local unavailable → `dist/media-jobs/` prompt package, `pending_local_generation`
