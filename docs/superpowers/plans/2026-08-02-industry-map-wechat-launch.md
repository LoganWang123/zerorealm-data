# 产业图谱 V0.1 公众号草稿 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一篇产业图谱推广专稿并通过微信公众号 API 创建草稿，供用户在 2026-08-03 09:00 手动发布。

**Architecture:** 新增独立专稿生成脚本，直接复用 `WechatClient` 的凭据、素材上传和 `draft/add` 能力，不修改现有日报解析器与渲染器。文章 HTML、封面与两张合格插图由专稿脚本组装；草稿创建后通过 `draft/get` 回读标题验证。

**Tech Stack:** Python 3.12、requests、微信公众号素材与草稿 API、pytest。

## Global Constraints

- 只能创建公众号草稿，不得调用自由发表或群发通知接口。
- 主 CTA 为 `https://zerorealm.tech/research/industry-map`。
- 文末固定使用“公开案例征集｜资料纠错｜行业合作”、`hi@zerorealm.tech` 和 `https://zerorealm.tech`。
- 不使用存在裁断文字和重复标签的 `插图1.png`。
- 不虚构企业节点、市场规模、访谈材料或合作关系。

---

### Task 1: 专稿 HTML 与安全草稿客户端

**Files:**
- Create: `publishing/wechat/industry_map_launch.py`
- Create: `tests/test_industry_map_launch.py`

**Interfaces:**
- Consumes: `publishing.wechat.client.WechatClient`
- Produces: `build_industry_map_article(image_urls: list[str]) -> dict`、`create_verified_draft(client, article: dict) -> str`

- [ ] **Step 1: 写失败测试**

验证标题、官网 CTA、标准品牌尾注、两张正文图片、无“运营商访谈”，并用 FakeClient 证明只调用素材上传、`create_draft` 和 `get_draft`。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_industry_map_launch.py -q`
Expected: FAIL，模块尚不存在。

- [ ] **Step 3: 实现最小专稿模块**

生成微信兼容的内联 HTML，上传正文图与封面，调用 `create_draft` 后回读标题。若回读标题不一致，抛出错误；模块不得引用发表或群发方法。

- [ ] **Step 4: 运行专项测试**

Run: `pytest tests/test_industry_map_launch.py -q`
Expected: PASS。

- [ ] **Step 5: 提交代码**

```bash
git add publishing/wechat/industry_map_launch.py tests/test_industry_map_launch.py
git commit -m "feat: add industry map WeChat launch draft"
```

### Task 2: 创建并回读公众号草稿

**Files:**
- Use: `publishing/wechat/industry_map_launch.py`
- Use: `D:/soft/AI/ZeroRealmAI/Gemini-img/知识图谱/1.0/公众号封面.png`
- Use: `D:/soft/AI/ZeroRealmAI/Gemini-img/知识图谱/1.0/插图2.png`
- Use: `D:/soft/AI/ZeroRealmAI/Gemini-img/知识图谱/1.0/插图3.png`

**Interfaces:**
- Consumes: `.env` 中的 `WECHAT_APPID` 和 `WECHAT_SECRET`
- Produces: 一个经过回读验证的公众号草稿 `media_id`

- [ ] **Step 1: 运行完整回归测试**

Run: `pytest -q`
Expected: 全部通过。

- [ ] **Step 2: 执行专稿脚本**

Run: `python -m publishing.wechat.industry_map_launch`
Expected: 上传三张素材、调用一次 `draft/add`，输出草稿 `media_id`。

- [ ] **Step 3: 回读验证**

脚本调用 `draft/get`，验证标题等于《中国无人零售产业图谱 V0.1：从设备交易走向经营系统》，并确认正文包含官网 CTA、邮箱和两个微信 CDN 图片地址。

- [ ] **Step 4: 报告草稿结果**

向用户提供标题、草稿状态、草稿 `media_id`、建议发布时间 2026-08-03 09:00，以及发布前的三项人工检查；不得代表用户点击发布。
