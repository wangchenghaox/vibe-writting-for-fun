#!/bin/bash
cd "$(dirname "$0")/backend"
uv run python -m app.cli_main "$@"
