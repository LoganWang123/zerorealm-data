# Local Media Pipeline

```
Content / ResearchBrief / Daily Article
  → ImageBrief (internal)
  → LocalImageGenerator | programmatic template
  → output/media/generated/<slug>/  or assets/generated/<date>/
  → asset_checks (mime/size/sha)
  → pending_review → review_media.py (SHA bind)
  → output/media/approved/  (policy) / existing upload path
  → WeChat draft / website / Zhihu package
```

If local generation unavailable:

```
ImageBrief → dist/media-jobs/<slug>/ prompt package
status = pending_local_generation
other non-image tasks continue
publish requiring images stays incomplete
```

Never: local fail → Agnes.
