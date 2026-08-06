# Public Bundle 运行手册

## 本地导出

```bash
python scripts/bootstrap_research_assets.py
python scripts/audit_public_sources.py --input data/research/public-catalog.json
python scripts/export_public_bundle.py \
  --input data/research/public-catalog.json \
  --output dist/public-v1 \
  --generated-at 2026-08-06T16:00:00+08:00
```

## CI

`daily-crawl.yaml` 导出 Bundle，并在 `SYNC_PUBLIC_BUNDLE=true` 时同步到
`website/data/public-v1`，同时可保留 `SYNC_LEGACY_DAILY_MDX=true`。

## 回滚

- 数据仓：`git checkout research-phaseN-complete`
- 网站仓：`git checkout zerorealm-website-public-bundle-v1`
