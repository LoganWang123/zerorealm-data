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

瘦身后的 `daily-crawl.yaml` **不再**导出或同步 Bundle（采集-only）。

运行时保护：`GITHUB_ACTIONS=true` 时 `main.py` 会把 `SYNC_PUBLIC_BUNDLE` /
`SYNC_LEGACY_DAILY_MDX` 写入 `GITHUB_ENV` 为 `false`，并清空 `WEBSITE_REPO_TOKEN`。
本机手动导出不受影响。

## 回滚

- 数据仓：`git checkout research-phaseN-complete`
- 网站仓：`git checkout zerorealm-website-public-bundle-v1`
