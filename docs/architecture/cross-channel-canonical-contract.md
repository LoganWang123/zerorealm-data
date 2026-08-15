# 跨渠道内容契约（canonical contract）

## 目标

把官网、微信公众号、知乎纳入同一套 `canonical_id` / `canonical_version` 契约，防止核心结论、证据边界与 CTA 目标漂移。

**一致 = 语义与证据契约一致，不是逐字相同。** 渠道可改标题、结构与表达。

## 架构

```text
zerorealm-data/data/content-canonical/registry.json   ← 单一事实源 (SSoT)
        │
        │  sync_website_canonical_mirror.py
        ▼
zerorealm-data/data/content-canonical/website-mirror.json  ← 可验证镜像（含 source_sha256）
zerorealm-website/data/content-canonical.json              ← 同内容镜像（兼容 records[]）
        │
        ├─ content/daily/*.mdx + content/insight/*.mdx + data/tool-canonical/*.json
        └─ npm run content:check

微信 / 知乎 content-packet-*.json
        └─ 必须引用 canonical_id/version，并由 check_canonical_contract.py 校验
```

## 强校验场景

自动化测试至少覆盖：

- 版本不一致（`VERSION_MISMATCH`）
- 核心结论漂移（`CORE_CONCLUSION_DRIFT`）
- 来源 / scope 边界漂移（`EVIDENCE_SOURCE_DRIFT` / `SCOPE_GUARD_DRIFT`）
- CTA 目标漂移（`CTA_TARGET_DRIFT`）
- 缺少渠道引用或 packet 未引用 canonical（`MISSING_CHANNEL_REF` / `MISSING_CANONICAL_REF`）
- 镜像哈希漂移（`MIRROR_HASH_DRIFT` / `WEBSITE_MIRROR_DRIFT`）

## 本地与 CI

```bash
# data
python scripts/check_canonical_contract.py
python scripts/sync_website_canonical_mirror.py --check
python -m pytest -q tests/test_canonical_contract.py

# website（兄弟目录或 ZEROREALM_WEBSITE_ROOT）
npm run content:check
```

CI：

- data：校验契约与 in-repo 哈希镜像；若能以 `contents:read` checkout 到兄弟 `zerorealm-website`（公共仓或已授权），则在 `.ci/zerorealm-website` 做镜像漂移检查；否则回退为仅校验 data 仓内 `website-mirror.json`（无秘密依赖）。
- website：`npm run content:check` 纳入 CI；镜像必须含 `mirror.source_sha256`。
- 本地完整跨仓：兄弟目录或 `ZEROREALM_WEBSITE_ROOT`。

## 渠道状态诚实性

registry 中的 `channels.*.status` 只反映仓库内可验证状态；不因存在内容包就虚构「已发布」。外部微信/知乎操作不在本契约脚本职责内。
