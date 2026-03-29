#!/usr/bin/env python3
"""直接测试提示词"""

import uuid
from src.llm.config import create_provider
from src.agent.core import AgentCore
from src.agent.session import Session

def main():
    session_id = str(uuid.uuid4())
    session = Session(session_id)
    provider = create_provider()
    agent = AgentCore(provider, session)

    prompt = """克苏鲁风格的故事，大学生主角来到偏远山区支教，渐渐地发现这个村子并没有表面那么简单，好奇心驱使着他展开调查；文风尽量写实，强调日常的真实感；需要结合中国传统的民俗元素，参考作品《黑太岁》；虽然包含超自然元素，但是主角没有超能力；需要突出克苏鲁未知的恐惧，和平淡日常中隐藏的诡异;整体 10章左右"""

    print("发送提示词...")
    print(f"提示词: {prompt}\n")

    try:
        response = agent.chat(prompt)
        print(f"\n回复:\n{response[:1000]}...")
        print("\n✓ 测试成功！")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
