from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
from pathlib import Path
import uuid
from ..llm.config import create_provider
from ..agent.core import AgentCore
from ..agent.session import Session

app = FastAPI(title="AI Novel Generator")

# 确保工作目录正确
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent.parent
NOVELS_DIR = BASE_DIR / "data" / "novels"

# 存储活跃的会话
active_sessions = {}

class ChatMessage(BaseModel):
    message: str
    novel_id: str = None

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI 小说生成器</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .novel-list { display: grid; gap: 20px; }
            .novel-card { border: 1px solid #ddd; padding: 15px; border-radius: 8px; }
            .novel-card h3 { margin-top: 0; }
            .chapter-list { margin-top: 10px; }
            .chapter-item { padding: 5px; cursor: pointer; }
            .chapter-item:hover { background: #f0f0f0; }
        </style>
    </head>
    <body>
        <h1>📚 AI 小说生成器</h1>
        <div id="novels" class="novel-list"></div>

        <script>
            fetch('/api/novels')
                .then(r => r.json())
                .then(novels => {
                    const container = document.getElementById('novels');
                    novels.forEach(novel => {
                        const card = document.createElement('div');
                        card.className = 'novel-card';
                        card.innerHTML = `
                            <h3>${novel.title}</h3>
                            <p>${novel.description}</p>
                            <p><small>创建时间: ${new Date(novel.created_at).toLocaleString()}</small></p>
                            <a href="/novel/${novel.id}">查看详情 →</a>
                        `;
                        container.appendChild(card);
                    });
                });
        </script>
    </body>
    </html>
    """

@app.get("/api/novels")
async def list_novels():
    novels = []
    if NOVELS_DIR.exists():
        for novel_dir in NOVELS_DIR.iterdir():
            if novel_dir.is_dir():
                meta_file = novel_dir / "meta.json"
                if meta_file.exists():
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        novels.append(json.load(f))
    return novels

@app.get("/api/novels/{novel_id}")
async def get_novel(novel_id: str):
    novel_dir = NOVELS_DIR / novel_id
    if not novel_dir.exists():
        raise HTTPException(404, "Novel not found")

    meta_file = novel_dir / "meta.json"
    with open(meta_file, 'r', encoding='utf-8') as f:
        novel = json.load(f)

    # 获取章节列表
    chapters_dir = novel_dir / "chapters"
    chapters = []
    if chapters_dir.exists():
        for chapter_file in sorted(chapters_dir.glob("*.json")):
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapters.append(json.load(f))

    novel['chapters'] = chapters
    return novel

@app.get("/api/novels/{novel_id}/outline")
async def get_outline(novel_id: str):
    outlines_dir = NOVELS_DIR / novel_id / "outlines"
    if not outlines_dir.exists():
        return {"outlines": []}

    outlines = []
    for outline_file in sorted(outlines_dir.glob("*.json")):
        with open(outline_file, 'r', encoding='utf-8') as f:
            outlines.append(json.load(f))
    return {"outlines": outlines}

@app.get("/api/novels/{novel_id}/stats")
async def get_stats(novel_id: str):
    novel_dir = NOVELS_DIR / novel_id
    if not novel_dir.exists():
        raise HTTPException(404, "Novel not found")

    chapters_dir = novel_dir / "chapters"
    total_chapters = 0
    total_words = 0

    if chapters_dir.exists():
        for chapter_file in chapters_dir.glob("*.json"):
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapter = json.load(f)
                total_chapters += 1
                total_words += len(chapter.get('content', ''))

    return {
        "total_chapters": total_chapters,
        "total_words": total_words,
        "avg_words_per_chapter": total_words // total_chapters if total_chapters > 0 else 0
    }

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    session_id = str(uuid.uuid4())

    if msg.novel_id:
        os.environ['CURRENT_NOVEL_ID'] = msg.novel_id

    provider = create_provider()
    session = Session(session_id)
    agent = AgentCore(provider, session)

    response = agent.chat(msg.message)
    return {"response": response}

@app.get("/novel/{novel_id}", response_class=HTMLResponse)
async def novel_detail(novel_id: str):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>小说详情</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; }}
            .container {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }}
            .main {{ }}
            .sidebar {{ position: sticky; top: 20px; height: fit-content; }}
            .header {{ border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 20px; }}
            .stats {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            .stats-item {{ margin: 10px 0; }}
            .chapter {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; cursor: pointer; }}
            .chapter:hover {{ background: #f9f9f9; }}
            .content {{ white-space: pre-wrap; line-height: 1.8; }}
            .chat-box {{ border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
            .chat-input {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }}
            .chat-btn {{ width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px; }}
            .chat-btn:hover {{ background: #0056b3; }}
            .outline {{ background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 20px; white-space: pre-wrap; }}
            .back {{ display: inline-block; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <a href="/" class="back">← 返回列表</a>
        <div class="container">
            <div class="main">
                <div id="novel"></div>
            </div>
            <div class="sidebar">
                <div class="stats" id="stats">
                    <h3>📊 创作统计</h3>
                    <div class="stats-item">加载中...</div>
                </div>
                <div class="chat-box">
                    <h3>💬 AI 对话</h3>
                    <textarea class="chat-input" id="chatInput" rows="4" placeholder="输入消息，例如：继续写第三章"></textarea>
                    <button class="chat-btn" onclick="sendMessage()">发送</button>
                    <div id="chatResponse" style="margin-top: 10px; color: #666;"></div>
                </div>
                <div class="outline" id="outline">
                    <h3>📝 大纲</h3>
                    <div>加载中...</div>
                </div>
            </div>
        </div>

        <script>
            const novelId = '{novel_id}';

            // 加载小说信息
            fetch(`/api/novels/${{novelId}}`)
                .then(r => r.json())
                .then(novel => {{
                    document.getElementById('novel').innerHTML = `
                        <div class="header">
                            <h1>${{novel.title}}</h1>
                            <p>${{novel.description}}</p>
                        </div>
                        <h2>章节列表 (${{novel.chapters.length}})</h2>
                        <div id="chapters"></div>
                    `;

                    const chaptersDiv = document.getElementById('chapters');
                    novel.chapters.forEach(chapter => {{
                        const div = document.createElement('div');
                        div.className = 'chapter';
                        div.innerHTML = `<h3>${{chapter.title}}</h3>`;
                        div.onclick = () => {{
                            div.innerHTML = `<h3>${{chapter.title}}</h3><div class="content">${{chapter.content}}</div>`;
                        }};
                        chaptersDiv.appendChild(div);
                    }});
                }});

            // 加载统计
            fetch(`/api/novels/${{novelId}}/stats`)
                .then(r => r.json())
                .then(stats => {{
                    document.getElementById('stats').innerHTML = `
                        <h3>📊 创作统计</h3>
                        <div class="stats-item">总章节数: ${{stats.total_chapters}}</div>
                        <div class="stats-item">总字数: ${{stats.total_words}}</div>
                        <div class="stats-item">平均每章: ${{stats.avg_words_per_chapter}} 字</div>
                    `;
                }});

            // 加载大纲
            fetch(`/api/novels/${{novelId}}/outline`)
                .then(r => r.json())
                .then(data => {{
                    const outlineDiv = document.getElementById('outline');
                    if (data.outlines.length > 0) {{
                        outlineDiv.innerHTML = '<h3>📝 大纲</h3>' + data.outlines.map(o => o.content).join('\\n\\n');
                    }} else {{
                        outlineDiv.innerHTML = '<h3>📝 大纲</h3><div>暂无大纲</div>';
                    }}
                }});

            // 发送消息
            function sendMessage() {{
                const input = document.getElementById('chatInput');
                const responseDiv = document.getElementById('chatResponse');
                const message = input.value.trim();

                if (!message) return;

                responseDiv.innerHTML = '思考中...';

                fetch('/api/chat', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{message, novel_id: novelId}})
                }})
                .then(r => r.json())
                .then(data => {{
                    responseDiv.innerHTML = data.response;
                    input.value = '';
                    // 刷新页面数据
                    location.reload();
                }})
                .catch(err => {{
                    responseDiv.innerHTML = '错误: ' + err.message;
                }});
            }}
        </script>
    </body>
    </html>
    """
