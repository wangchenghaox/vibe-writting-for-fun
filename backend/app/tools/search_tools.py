import httpx
from app.capability.tool_registry import tool

@tool("web_search", "搜索网络内容获取最新信息")
def web_search(query: str, max_results: int = 5) -> str:
    """
    搜索网络内容

    Args:
        query: 搜索关键词
        max_results: 最大结果数量，默认5条

    Returns:
        搜索结果摘要
    """
    try:
        # 使用DuckDuckGo的即时答案API
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            results = []

            # 添加摘要
            if data.get("AbstractText"):
                results.append(f"摘要: {data['AbstractText']}")

            # 添加相关主题
            if data.get("RelatedTopics"):
                results.append("\n相关内容:")
                for i, topic in enumerate(data["RelatedTopics"][:max_results], 1):
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append(f"{i}. {topic['Text']}")

            return "\n".join(results) if results else "未找到相关结果"

    except Exception as e:
        return f"搜索失败: {str(e)}"
