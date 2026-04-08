# AdForge — creative automation pipeline
# Install just: https://github.com/casey/just#installation

# Default: show available commands
default:
    @just --list

# Install dependencies (uses uv if available, falls back to pip)
install:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv &> /dev/null; then
        echo "→ Using uv"
        uv sync
    else
        echo "→ Using pip"
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    fi
    echo "✓ Ready"

# Run the CLI pipeline with mock images (no API keys needed)
demo brief="sample_briefs/beach_house_campaign.yaml":
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv &> /dev/null; then
        uv run python -m src.cli generate {{brief}} --mock
    elif [ -f venv/bin/activate ]; then
        source venv/bin/activate
        python -m src.cli generate {{brief}} --mock
    else
        echo "Run 'just install' first" && exit 1
    fi

# Start the Streamlit web UI
start-app:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv &> /dev/null; then
        uv run streamlit run src/app.py
    elif [ -f venv/bin/activate ]; then
        source venv/bin/activate
        streamlit run src/app.py
    else
        echo "Run 'just install' first" && exit 1
    fi

# Restart the Streamlit web UI (kill existing + relaunch)
restart-app:
    #!/usr/bin/env bash
    set -euo pipefail
    pkill -f "streamlit run src/app.py" 2>/dev/null || true
    sleep 1
    just start-app

# Stop the Streamlit web UI
stop-app:
    pkill -f "streamlit run src/app.py" 2>/dev/null || echo "Not running"

# Run the test suite
test:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv &> /dev/null; then
        uv run python -m pytest tests/ -v
    elif [ -f venv/bin/activate ]; then
        source venv/bin/activate
        python -m pytest tests/ -v
    else
        echo "Run 'just install' first" && exit 1
    fi

# Analyze a campaign brief
analyze brief="sample_briefs/beach_house_campaign.yaml":
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv &> /dev/null; then
        uv run python -m src.cli analyze {{brief}}
    elif [ -f venv/bin/activate ]; then
        source venv/bin/activate
        python -m src.cli analyze {{brief}}
    else
        echo "Run 'just install' first" && exit 1
    fi

# Generate with a real provider (gemini, dalle, firefly)
generate brief="sample_briefs/beach_house_campaign.yaml" provider="gemini":
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv &> /dev/null; then
        uv run python -m src.cli generate {{brief}} -p {{provider}}
    elif [ -f venv/bin/activate ]; then
        source venv/bin/activate
        python -m src.cli generate {{brief}} -p {{provider}}
    else
        echo "Run 'just install' first" && exit 1
    fi
