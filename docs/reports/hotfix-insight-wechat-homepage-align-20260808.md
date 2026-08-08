# Hotfix: Align homepage with WeChat Insight 2026-08-08

## Problem
WeChat published Insight《智能柜运营，真正该盯的，不只是GMV：5个过程指标看清终端经营质量》today.
Website Insight body/media already matched `article.md`, but homepage featured Daily《东鹏饮料…》as “today”, causing cross-channel mismatch.

## Fix
- Homepage Hero CTA → latest Insight
- New `LatestInsight` section above Daily list
- Insight MDX lead quote aligned with WeChat digest
- Content package metadata marked website-aligned

## Follow-up
- Daily 2026-08-08《东鹏饮料…》已按用户要求撤回：`visibility: private` + `gate_status: rejected`
- No WeChat re-publish
