import argparse
from pathlib import Path

from app.cli.app import CLI

def main(argv=None):
    parser = argparse.ArgumentParser(description="AI 小说创作 CLI")
    memory_group = parser.add_mutually_exclusive_group()
    memory_group.add_argument(
        "--memory",
        action="store_true",
        dest="memory_enabled",
        default=None,
        help="开启记忆沉淀和读取",
    )
    memory_group.add_argument(
        "--no-memory",
        action="store_false",
        dest="memory_enabled",
        help="关闭记忆沉淀和读取",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="当前工作 sandbox 目录，Agent 文件操作只能发生在该目录内",
    )
    args = parser.parse_args(argv)

    cli = CLI(memory_enabled=args.memory_enabled, workdir=args.workdir)
    cli.run()

if __name__ == "__main__":
    main()
