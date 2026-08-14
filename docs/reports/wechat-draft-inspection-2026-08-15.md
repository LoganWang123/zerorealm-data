# WeChat draft inspection · 2026-08-15

- Inspected at: `2026-08-14T18:24:45+00:00`
- Mode: **read_only_list** (list only)
- total_count: **2**
- item_count: **2**

## Safety

- delete / overwrite / publish / mass-send: **not performed**
- LLM API: **not called**
- image generation: **not performed**

## Drafts (title / update / media status)

| # | media_id (prefix) | update_time | titles | thumb |
| --- | --- | --- | --- | --- |
| 1 | `csbrZswCx_…` | 1786731883 | 柜机缺货排查清单：先查这 7 步再补货 | yes |
| 2 | `csbrZswCx_…` | 1786729599 | 点位有销量却不赚钱？用一张周表算清单点贡献 | yes |

## Overlap with approved plan

- `media_id` prefix `csbrZswCx_…` → **w1-wechat-stockout** (hints: 缺货排查, 7 步, 再补货)
  - 柜机缺货排查清单：先查这 7 步再补货

## Policy

Never delete, overwrite, publish, or mass-send unknown drafts. Human review required before any mutation.

## Exception check (CEO plan)

If an unpublished draft overlaps `w1-wechat-five-metrics`, prioritize human WeChat publish on 2026-08-15 and defer Zhihu to 2026-08-16.
