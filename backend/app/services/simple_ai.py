from openai import AsyncOpenAI
from app.core.config import settings

async def get_ai_response(message: str, novel_title: str) -> str:
    """简化的AI响应，直接调用Kimi Coding API"""
    try:
        api_key = settings.KIMI_API_KEY
        if not api_key:
            return f"正在为《{novel_title}》创作中...请先配置KIMI_API_KEY环境变量"

        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.kimi.com/coding/"
        )

        response = await client.chat.completions.create(
            model="claude-sonnet-4-6",
            messages=[
                {"role": "system", "content": f"你是一个专业的小说创作助手，正在帮助用户创作《{novel_title}》。"},
                {"role": "user", "content": message}
            ]
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"AI服务暂时不可用: {str(e)}"
