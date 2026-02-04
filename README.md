# codemap 🗺️

**Intelligent Codebase Map for AI Agents** — the 20% context that gives 80% understanding.

Unlike repomix/code2prompt (which dump every file), codemap generates a structured INDEX: project tree, public API signatures, dependency graph, and key files — ranked by importance. Fits in ~750 tokens instead of 100k+.

Zero dependencies. Pure Python.

## Why?

When feeding a codebase to an AI agent (Claude Code, Cursor, ChatGPT), you have two bad options:
1. **Dump everything** — repomix packs 100k+ tokens of raw code, most of which the AI doesn't need
2. **Pick files manually** — slow, error-prone, misses important connections

codemap gives you a third option: **a structured map** that tells the AI what exists, what matters, and where to look. The AI reads the map first, then dives into specific files as needed.

## Install

```bash
curl -O https://raw.githubusercontent.com/kriskimmerle/codemap/main/codemap.py
chmod +x codemap.py

# Or pip
pip install codemap
```

**Requirements:** Python 3.9+

## Usage

```bash
# Map current directory
codemap

# Map specific project
codemap /path/to/project

# JSON output (for programmatic use)
codemap --format json

# Limit tree depth
codemap --depth 3

# Include _private functions
codemap --include-private

# Fit within token budget
codemap --token-budget 4000
```

## What It Generates

### 1. Project Overview
```
Files: 12 | Lines: 3,456 | Languages: Python, YAML, Markdown
Entrypoints: main.py, cli.py
```

### 2. Annotated File Tree
```
├── LICENSE
├── README.md  — My awesome tool
├── ★ main.py  — Main entry point for the application.
├── src/
│   ├── engine.py  — Core processing engine.
│   ├── models.py  — Data models and validation.
│   └── utils.py  — Utility functions.
├── tests/
│   └── test_engine.py
└── pyproject.toml
```
Stars (★) mark entrypoints. Descriptions come from file docstrings.

### 3. Public API Index
```python
### src/engine.py
*Core processing engine.*
  def process(data: dict, config: Config) → Result  # Process input data.
  async def fetch(url: str, timeout: int = 30) → bytes  # Fetch remote data.
  class Engine
    __init__(config: Config, cache_dir: Path = Path(".cache"))
    def run(input: str) → Output  # Run the processing pipeline.
    async def stream(input: str) → AsyncIterator[Chunk]

### src/models.py
  class Config  # Configuration for the engine.
    __init__(model: str, temperature: float = 0.7)
  class Result(BaseModel)
```

### 4. Dependencies
```
  requests (used by 2 modules)
  pydantic (used by 1 module)
```

### 5. Key Files (ranked by importance)
```
- **main.py** ★ (234 lines) — Main entry point for the application.
- **src/engine.py** (456 lines) — Core processing engine.
- **src/models.py** (189 lines) — Data models and validation.
```

## How Importance Is Scored

Files are ranked by a composite importance score:

| Signal | Weight | Why |
|--------|--------|-----|
| Entrypoint (main.py, app.py, etc.) | +30% | These are where execution starts |
| Source code language | +20% | Code > config > docs |
| File size (lines) | +20% | Larger files have more API surface |
| Git churn (last 90 days) | +20% | Recently changed = actively important |
| Root-level file | +10% | Project-level files matter more |
| Has docstring | +5% | Documented = intentionally public |

## Token Efficiency

| Project Size | repomix/code2prompt | codemap |
|-------------|---------------------|---------|
| Small (5 files) | ~5,000 tokens | ~500 tokens |
| Medium (50 files) | ~50,000 tokens | ~3,000 tokens |
| Large (500 files) | ~500,000 tokens | ~8,000 tokens |

codemap is designed to fit in ANY context window, leaving room for the actual work.

## JSON Output

```bash
codemap --format json | jq '.api[:2]'
```

Structured JSON with file tree, API signatures, imports, and importance scores — perfect for building tools on top of codemap.

## Workflow

```
1. codemap > CODEMAP.md          # Generate map
2. Cat CODEMAP.md into AI prompt  # AI understands the project
3. AI reads specific files         # Targeted, not wasteful
```

Or pipe directly:
```bash
codemap | pbcopy  # Copy to clipboard for ChatGPT/Claude
```

## License

MIT
