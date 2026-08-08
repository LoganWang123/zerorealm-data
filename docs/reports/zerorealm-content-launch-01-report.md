# ZeroRealm Content Launch 01 Report (Data)

## SECURITY

见 `security-secret-review-final.md`。Agnes 生图生产路径 = 0。

## Release readiness

CONDITIONAL PASS — 可 push/PR，需人工审核内容与密钥。

## Metrics quality

15 approved + `metric-briefs.json` 精品字段。

## Company review queue

10 家推荐，全部 draft；`dist/review/company/*/review.md`。

## Case candidates

3（云拿公开案例，均 draft，含“无量化结果”声明）。

## Signal candidates

6（官网公开定位/产品页，verification_status=reviewing）。

## Industry Map

`dist/industry-map-v1/` FOR_REVIEW_ONLY（--include-draft）。

## Content Network / SEO / Search / Content Package

网络健康报告已写；SEO/Search 在网站仓；E2E 包已生成。

## MediaJob architecture

IDE-native MediaJob；无 Cursor/Codex runtime provider；无 Agnes fallback。

## Current IDE image capability

available=true；已生成 1 张场景图并 attach → pending_review。

## Tests

365 passed + ruff clean（本轮验证时点）。

## Known limitations

- 企业/案例/信号未 approved，官网 Bundle 仍空态为主
- MediaJob 图片未人工批准
- 未 push

## Manual actions

见 release manual-checklist。
