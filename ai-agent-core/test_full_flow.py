#!/usr/bin/env python3
"""测试完整的小说创作流程"""

import uuid
from src.llm.config import create_provider
from src.agent.core import AgentCore
from src.agent.session import Session

def main():
    session_id = str(uuid.uuid4())
    session = Session(session_id)
    provider = create_provider()
    agent = AgentCore(provider, session)

    # 步骤1: 创建作品
    print("=" * 60)
    print("步骤1: 创建新作品")
    print("=" * 60)

    create_prompt = """请创建一个新的小说项目：
novel_id: mountain_horror
title: 山深
description: 克苏鲁风格的支教恐怖故事"""

    try:
        response = agent.chat(create_prompt)
        print(f"\n回复: {response}\n")
    except Exception as e:
        print(f"错误: {e}\n")
        return

    # 步骤2: 生成大纲
    print("=" * 60)
    print("步骤2: 生成故事大纲")
    print("=" * 60)

    outline_prompt = """基于以下要求为小说"山深"(novel_id: mountain_horror)创建大纲：

克苏鲁风格的故事，大学生主角来到偏远山区支教，渐渐地发现这个村子并没有表面那么简单，好奇心驱使着他展开调查；文风尽量写实，强调日常的真实感；需要结合中国传统的民俗元素，参考作品《黑太岁》；虽然包含超自然元素，但是主角没有超能力；需要突出克苏鲁未知的恐惧，和平淡日常中隐藏的诡异

请保存大纲到 outline_id: main_outline"""

    try:
        response = agent.chat(outline_prompt)
        print(f"\n回复: {response[:500]}...\n")
    except Exception as e:
        print(f"错误: {e}\n")
        return

    # 步骤3: 生成第一章
    print("=" * 60)
    print("步骤3: 生成第一章")
    print("=" * 60)

    chapter_prompt = """根据大纲，为小说"山深"(novel_id: mountain_horror)创作第一章：

chapter_id: chapter_01
title: 青木崖

要求：
- 主角陈默抵达偏远山村
- 描写村子的诡异氛围
- 埋下悬念
- 字数3000字左右"""

    try:
        response = agent.chat(chapter_prompt)
        print(f"\n回复: {response[:500]}...\n")
        print("✓ 完整流程测试成功！")
    except Exception as e:
        print(f"错误: {e}\n")

if __name__ == "__main__":
    main()
