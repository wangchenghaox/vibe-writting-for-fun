import argparse

from app.cli.app import CLI

def main(argv=None):
    parser = argparse.ArgumentParser(description="AI 小说创作 CLI")
    parser.parse_args(argv)

    cli = CLI()
    cli.run()

if __name__ == "__main__":
    main()
