#!/bin/bash
cd "$(dirname "$0")/backend"
uv run python app/cli_main.py
