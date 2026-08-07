# Content Package E2E

## Flow exercised

```
ResearchBrief (safe test title)
  → MediaJob create (ide-native)
  → Cursor GenerateImage (scene, no text/logos)
  → resize 1280x720
  → media_job attach → pending_review
  → export_content_package (website/wechat/zhihu/sources/media)
```

## Results

- Agnes used: **false**
- External publish: **false**
- MediaJob: `mj-df0b5985655b`
- Status: `pending_review`（未 auto-approve）
- Package: `dist/content-package/content-launch-01-e2e/`
- Sensitive fields: none intentionally exported

## Notes

Content package may include generated asset path under media/ for operator review; publish gate still requires `approved`.
