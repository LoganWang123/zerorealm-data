# 首批企业审核优先级（人工）

生成自 `scripts/audit_company_profiles.py`，**不会自动 approved**。

依据（仅现有公开 catalog 字段）：

- 名称代表性（智能柜核心玩家优先）
- 产业角色：operator / hardware / software
- 摘要是否仍为 bootstrap 引导语
- 缺失字段数量

## 推荐首批（约 10 家）

见 `data/research/review-queue-companies.json`。

当前队列头部通常包括：丰e足食、友宝、嗨便利 等 operator/hardware 角色企业。

全部条目 `readiness=NOT_READY`：缺可核验公开来源与 verifiedAt，摘要仍需改写。

## 人工动作

1. 为每家补充官方/高可信公开来源
2. 重写 summary（去掉“公开图谱收录”模板句）
3. 填写 verifiedAt
4. 人工改为 `approved` 后方可进入 Public Bundle
