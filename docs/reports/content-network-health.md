# Content Network Health

生成自 catalog + `research.relations.build_relation_index`。

## Counts（Launch 01 后）

| Entity | Approx |
|--------|--------|
| companies | 52 (draft) |
| metrics | 15 (approved) |
| cases | 3 (draft) |
| signals | 6 (reviewing/draft gate) |
| sources | 7+ official URLs |

## Relations

- 多数企业仍为孤立节点（无 case/signal 链接）——**故意不造假关系**
- Signal → Source 已绑定官网 URL
- Case 候选暂未强绑 company_ids（待人工对齐 slug）

## Orphans / broken refs

- draft companies：无 verified sources
- metrics related_case_ids 为空
- 无 approved company→signal 公开边

## Verdict

网络健康度：**早期可接受**。优先人工审核企业与案例，再补真实关系，禁止为密度制造关联。
