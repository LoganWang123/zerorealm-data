# Industry Map Data Audit (data repo)

## 发现

- 网站 `lib/industry-graph.ts` / `lib/industry-map.ts` 仍含硬编码节点与框架。
- `data/research/public-catalog.json` 有 52 家 draft 企业，0 家 approved → Bundle 企业库为空。
- 迁移工具：`scripts/migrate_industry_map_to_research.py`（默认 dry-run，写入仍为 draft）。
- 导出：`scripts/export_industry_map_dataset.py`（draft 输出标记 `FOR_REVIEW_ONLY`）。

## 结论

Industry Map 应以 Public Bundle 为优先数据源；legacy 硬编码保留作 fallback，直到企业/案例审核通过。
