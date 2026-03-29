import os
import json
from pathlib import Path

def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)

def write_json(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_json(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def append_jsonl(path: str, data: dict):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')

def read_jsonl(path: str) -> list:
    lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            lines.append(json.loads(line))
    return lines
