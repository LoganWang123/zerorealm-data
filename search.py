"""ZeroRealm AI Search — CLI entry point.

Usage:
    python search.py "友宝最近有什么动态"
    python search.py "智能柜" --type company
    python search.py "无人零售融资" --top 5
    python search.py --stats

Environment:
    LLM_API_KEY      - API key (required for AI answer synthesis)
    LLM_BASE_URL     - API base URL
    EMBEDDING_MODEL  - Embedding model name
"""

import argparse
import json
import os
import sys

from utils.logger import setup_logger, get_logger
from utils.helpers import generate_run_id


def format_context(hits: list) -> str:
    """Format search hits as context for LLM answer synthesis."""
    lines = []
    for i, hit in enumerate(hits, 1):
        obj = hit.object
        line = f"{i}. [{obj.entity_type}] {obj.canonical_name}"
        if obj.aliases:
            line += f"（别名：{', '.join(obj.aliases[:3])}）"
        if obj.industry_role:
            line += f" | 角色：{obj.industry_role}"
        line += f" | 提及{obj.mention_count}次"
        line += f" | 相关度：{hit.score:.2f}（{hit.match_type}）"
        lines.append(line)
    return "\n".join(lines)


def synthesize_answer(query: str, hits: list) -> str | None:
    """Use LLM to synthesize an answer from search results."""
    if not hits:
        return None

    if not os.environ.get("LLM_API_KEY"):
        return None

    from ai_runtime.client import LLMClient
    from ai_runtime.prompt_registry import PromptRegistry

    registry = PromptRegistry()
    tpl = registry.get("search_answer")
    if tpl is None:
        return None

    context = format_context(hits)
    system, user = tpl.render(query=query, context=context)

    client = LLMClient()
    resp = client.chat(
        task="search_answer",
        system=system,
        user=user,
        model=tpl.model,
        temperature=tpl.temperature,
        max_tokens=tpl.max_tokens,
        prompt_name="search_answer",
        prompt_version=tpl.version,
    )
    return resp.content


def cmd_search(args):
    """Execute search."""
    from knowledge.store import KnowledgeStore
    from knowledge.search import SearchEngine
    from storage.vectors import VectorStore

    kb = KnowledgeStore()
    vs = VectorStore()
    engine = SearchEngine(kb=kb, vs=vs)

    # Get query embedding if API available
    query_embedding = None
    if os.environ.get("LLM_API_KEY"):
        try:
            from ai_runtime.embedding import EmbeddingClient
            emb_client = EmbeddingClient()
            query_embedding = emb_client.embed(args.query)
        except Exception as e:
            logger = get_logger()
            logger.debug("Embedding unavailable, keyword-only search: %s", e)

    # Execute search
    response = engine.search(
        query=args.query,
        top_k=args.top,
        entity_type=args.type,
        query_embedding=query_embedding,
    )

    # Output
    if args.json:
        print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
        return

    # Human-readable output
    print(f"\n🔍 查询：{args.query}")
    print(f"   结果：{response.total} 条 | 耗时：{response.latency_ms}ms")
    print("-" * 60)

    if not response.hits:
        print("   未找到相关知识。")
        return

    for i, hit in enumerate(response.hits, 1):
        obj = hit.object
        icon = {"company": "🏢", "product": "📦", "technology": "🔧",
                "person": "👤", "location": "📍"}.get(obj.entity_type, "•")
        print(f"  {i}. {icon} {obj.canonical_name} ({obj.entity_type})")
        if obj.aliases:
            print(f"     别名：{', '.join(obj.aliases[:4])}")
        if obj.industry_role:
            print(f"     角色：{obj.industry_role} | 提及：{obj.mention_count}次")
        print(f"     相关度：{hit.score:.3f} [{hit.match_type}]")
        print()

    # AI answer synthesis
    if not args.no_ai:
        answer = synthesize_answer(args.query, response.hits)
        if answer:
            print("=" * 60)
            print("🤖 AI 回答：")
            print(answer)
            print()


def cmd_stats(args):
    """Show KB and vector store statistics."""
    from knowledge.store import KnowledgeStore
    from storage.vectors import VectorStore

    kb = KnowledgeStore()
    vs = VectorStore()

    kb_stats = kb.stats()
    vs_stats = vs.stats()

    print("\n📊 ZeroRealm AI Knowledge Base")
    print("=" * 40)
    print(f"  知识对象：{kb_stats['total_objects']}")
    print(f"  关系数量：{kb_stats['total_relations']}")
    print(f"  别名索引：{kb_stats['total_aliases']}")
    print(f"  向量数量：{vs_stats['total_vectors']}")
    print()

    if kb_stats.get("by_type"):
        print("  按类型：")
        for t, count in sorted(kb_stats["by_type"].items(), key=lambda x: -x[1]):
            print(f"    {t}: {count}")

    if kb_stats.get("by_role"):
        print("  按角色：")
        for r, count in sorted(kb_stats["by_role"].items(), key=lambda x: -x[1]):
            print(f"    {r}: {count}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="ZeroRealm AI Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="?", help="搜索关键词")
    parser.add_argument("--type", "-t", help="实体类型过滤 (company/product/technology)")
    parser.add_argument("--top", "-k", type=int, default=10, help="返回结果数 (default: 10)")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--no-ai", action="store_true", help="跳过 AI 回答合成")
    parser.add_argument("--stats", action="store_true", help="显示知识库统计")
    parser.add_argument("--debug", action="store_true", help="DEBUG 日志")

    args = parser.parse_args()

    # Init logger
    run_id = generate_run_id()
    level = "DEBUG" if args.debug else "INFO"
    setup_logger(run_id, "logs", level)

    if args.stats:
        cmd_stats(args)
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    cmd_search(args)


if __name__ == "__main__":
    main()
