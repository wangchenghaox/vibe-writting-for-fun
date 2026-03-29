#!/usr/bin/env python3
"""启动 Web 服务"""

import uvicorn
import os

# 切换到正确的工作目录
os.chdir(os.path.dirname(os.path.dirname(__file__)))

if __name__ == "__main__":
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=8000, reload=True)
