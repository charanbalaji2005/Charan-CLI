# CHARANCLI.md — Project Reference

## Project Overview

**CharanCLI** is a Python-based, terminal-native AI coding agent (v1.2.0). It connects to OpenAI-compatible LLM APIs (primarily OpenRouter) and provides an agentic loop that autonomously reads code, executes tools, manages sessions, and streams thinking — all inside the terminal. Created and maintained by **Charan**.

---

## Languages, Frameworks, Key Dependencies

- **Language:** Python 3.10+
- **Build system:** setuptools via `pyproject.toml`
- **Key dependencies** (from `pyproject.toml`):
  - `click>=8.0.0` — CLI framework
  - `rich>=13.0.0` — Terminal UI rendering
  - `httpx>=0.25.0` — Async HTTP client
  - `pydantic>=2.0.0` — Data validation / config models
  - `openai>=1.0.0` — OpenAI API client (also used for OpenRouter)
  - `tiktoken>=0.5.0` — Token counting
  - `toml` / `tomli-w` — Config file parsing and writing
  - `ddgs>=6.0.0` — DuckDuckGo web search
  - `fastmcp>=2.0.0` — MCP (Model Context Protocol) support
  - `platformdirs>=3.0.0` — Cross-platform config/data directories
  - `prompt_toolkit>=3.0.0` — Enhanced terminal input

---

## Build, Test, Lint, Run Commands

| Action                | Command                            |
| --------------------- | ---------------------------------- |
| **Install dev**       | `pip install -e .`                 |
| **Run interactive**   | `charancli`                         |
| **Run single prompt** | `charancli "fix the bug in app.py"` |
| **Run as module**     | `python -m charancli`               |
| **Help**              | `charancli --help`                  |
| **Build package**     | `python -m build`                  |
| **Publish**           | `twine upload dist/*`              |
| **Check schemas**     | `python scripts/check_schemas.py`  |
| **Test tool**         | `python scripts/test_tool.py`      |

No formal test suite or linting configuration exists in the repo.

---

## Architecture

### Entry Points

- `main.py` — CLI entry point using Click; contains `CharanCLI` class and `main()` function
- `__main__.py` — Allows `python -m charancli` invocation; delegates to `main.main()`

### Core Components

```
main.py (CharanCLI + main())
  └── Agent (agent/agent.py)
        └── Session (agent/session.py)
              ├── LLMClient (client/llm_client.py)
              ├── ContextManager (context/manager.py)
              ├── ToolRegistry (tools/registry.py)
              │     ├── Builtin Tools (tools/builtin/*.py)
              │     └── Subagent Tools (tools/subagent.py)
              ├── MCPManager (tools/mcp/mcp_manager.py)
              ├── ApprovalManager (safety/approval.py)
              ├── HookSystem (hooks/hook_system.py)
              ├── LoopDetector (context/loop_detector.py)
              └── ChatCompressor (context/compaction.py)
```

### Data Flow

1. User input → `CharanCLI._process_message()`
2. Agent runs agentic loop (`agent/agent.py:_agentic_loop`)
3. For each turn: build messages → call LLM client → stream events
4. LLM may request tool calls → executed via ToolRegistry
5. Tool results added to context → loop continues until no more tool calls
6. Events streamed to TUI for display

### Event System

- `AgentEvent` / `AgentEventType` (`agent/events.py`) — event-driven architecture
- Event types: `AGENT_START`, `AGENT_END`, `AGENT_ERROR`, `TEXT_DELTA`, `TEXT_COMPLETE`, `THINKING_DELTA`, `THINKING_COMPLETE`, `TOOL_CALL_START`, `TOOL_CALL_COMPLETE`, `LOOP_DETECTED`

### Tool System

- Base class: `Tool` (`tools/base.py`) — abstract base with `execute()`, `validate_params()`, `to_openai_schema()`
- Registry: `ToolRegistry` (`tools/registry.py`) — manages builtin + MCP + subagent tools
- Discovery: `ToolDiscoveryManager` (`tools/discovery.py`) — loads custom tools from `.charancli/tools/` directory
- Tool kinds: `READ`, `WRITE`, `SHELL`, `NETWORK`, `MEMORY`, `MCP`

### Builtin Tools (11 + 5 default subagents)

**Regular tools** (`tools/builtin/`):
| File | Tool Name | Kind |
|---|---|---|
| `read_file.py` | `read_file` | READ |
| `write_file.py` | `write_file` | WRITE |
| `edit_file.py` | `edit_file` | WRITE |
| `shell.py` | `shell` | SHELL |
| `list_dir.py` | `list_dir` | READ |
| `glob.py` | `glob` | READ |
| `grep.py` | `grep` | READ |
| `web_search.py` | `web_search` | NETWORK |
| `web_fetch.py` | `web_fetch` | NETWORK |
| `todo.py` | `todos` | MEMORY |
| `memory.py` | `memory` | MEMORY |

**Default subagents** (`tools/subagent.py`):

- `subagent_codebase_investigator`, `subagent_code_reviewer`, `subagent_test_generator`, `subagent_bug_fixer`, `subagent_refactorer`
- Additional specialized subagents defined but not registered by default (security_auditor, performance_analyzer, ci_cd_integrator, etc.)

### Configuration System

- `Config` model (`config/config.py`) — Pydantic BaseModel with all settings
- `load_config()` (`config/loader.py`) — loads from:
  1. Global: `~/.charancli/config.toml`
  2. Project: `<cwd>/.charancli/config.toml` (overrides global)
  3. `AGENT.MD` file in project root → injected as `developer_instructions`
- First-run prompts for API credentials interactively
- Data directory via `platformdirs` (`~/.local/share/charancli` or Windows equivalent)

### Session Management

- `Session` (`agent/session.py`) — encapsulates LLM client, context manager, tool registry, loop detector, MCP manager
- `StateManager` / `SessionSnapshot` (`agent/state.py`) — save/resume sessions, checkpoints to disk
- User memory loaded from `user_memory.json` in data directory

### TUI (Terminal UI)

- `TUI` class (`ui/tui.py`) — Rich-based terminal interface
- Features: streaming text display, thinking display (grey italic), tool call formatting, working spinner, session stats

---

## Code Conventions

### Naming

- **Classes:** PascalCase (e.g., `ToolRegistry`, `ContextManager`, `AgentEvent`)
- **Functions/methods:** snake_case (e.g., `add_user_message`, `get_system_prompt`)
- **Constants:** UPPER_SNAKE_CASE (e.g., `DEFAULT_API_BASE_URL`, `PRUNE_PROTECT_TOKENS`)
- **Files:** snake_case (e.g., `llm_client.py`, `tool_registry.py`)

### Import Style

- Standard library → third-party → local imports (separated by blank lines)
- Local imports use absolute paths from project root (e.g., `from agent.events import AgentEvent`)
- Some lazy imports inside functions to avoid circular dependencies (e.g., `from agent.agent import Agent` inside `subagent.py`)

### Error Handling

- `ToolResult.error_result()` for tool errors
- `AgentEvent.agent_error()` for agent-level errors
- `ConfigError` (`utils/errors.py`) for configuration errors
- Retry with exponential backoff for API rate limits (3 retries)

### Async Patterns

- `asyncio.gather` for parallel tool execution when multiple tool calls in one turn
- `async for` streaming for both LLM responses and agent events
- `async with Agent(config) as agent:` context manager pattern

### Data Models

- Pydantic `BaseModel` for config and tool schemas
- `@dataclass` for internal data structures (e.g., `SessionSnapshot`, `MessageItem`, `ToolResult`)
- Enum for fixed sets (e.g., `ApprovalPolicy`, `ToolKind`, `AgentEventType`)

---

## Key Files and Directories

| Path                        | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `main.py`                   | CLI entry point, `CharanCLI` class with command handlers      |
| `agent/agent.py`            | Core `Agent` class with agentic loop                         |
| `agent/session.py`          | `Session` — encapsulates all agent state                     |
| `agent/events.py`           | Event types and `AgentEvent` dataclass                       |
| `agent/state.py`            | Session persistence (`StateManager`, `SessionSnapshot`)      |
| `client/llm_client.py`      | `LLMClient` — OpenAI API integration with streaming          |
| `client/response.py`        | Response types (`StreamEvent`, `TokenUsage`, `ToolCall`)     |
| `config/config.py`          | `Config` and related Pydantic models                         |
| `config/loader.py`          | Config loading, saving, credential prompts                   |
| `context/manager.py`        | `ContextManager` — message history management                |
| `context/compaction.py`     | `ChatCompressor` — context compression when near limit       |
| `context/loop_detector.py`  | `LoopDetector` — detects repetitive behavior                 |
| `tools/base.py`             | `Tool` abstract base class, `ToolResult`, `ToolKind`         |
| `tools/registry.py`         | `ToolRegistry`, `create_default_registry()`                  |
| `tools/discovery.py`        | Custom tool loading from `.charancli/tools/`                  |
| `tools/subagent.py`         | Subagent definitions and `SubagentTool` class                |
| `tools/builtin/`            | 11 builtin tool implementations                              |
| `tools/mcp/`                | MCP client, manager, and tool wrapper                        |
| `prompts/system.py`         | System prompt generation (identity, environment, guidelines) |
| `safety/approval.py`        | `ApprovalManager` — configurable approval policies           |
| `hooks/hook_system.py`      | Lifecycle hooks (before/after agent, before/after tool)      |
| `ui/tui.py`                 | Rich-based terminal UI                                       |
| `utils/errors.py`           | `ConfigError` exception                                      |
| `utils/text.py`             | Token counting utilities                                     |
| `utils/file_attachments.py` | `@filename` attachment parsing                               |
| `utils/paths.py`            | Path utility functions                                       |
| `scripts/check_schemas.py`  | Debug script for tool schema inspection                      |
| `scripts/test_tool.py`      | Debug script for testing individual tools                    |

---

## Interactive Commands

Available in REPL mode (prefix with `/`):

| Command              | Action                                               |
| -------------------- | ---------------------------------------------------- |
| `/help`              | Show all commands                                    |
| `/exit` or `/quit`   | Exit                                                 |
| `/clear`             | Clear conversation history                           |
| `/model <name>`      | Switch LLM model                                     |
| `/approval <policy>` | Change approval policy                               |
| `/config`            | Show current config                                  |
| `/credentials`       | View/update API key and base URL                     |
| `/tools`             | List available tools                                 |
| `/mcp`               | Show MCP server status                               |
| `/stats`             | Show session statistics                              |
| `/save`              | Save session to disk                                 |
| `/sessions`          | List saved sessions                                  |
| `/resume <id>`       | Resume a session                                     |
| `/checkpoint`        | Create checkpoint                                    |
| `/restore <id>`      | Restore checkpoint                                   |
| `/undo`              | Undo last file edit                                  |
| `/init`              | Analyze project and generate AGENTS.md / CHARANCLI.md |

---

## Configuration File Format (TOML)

Global config: `~/.charancli/config.toml`
Project config: `<project>/.charancli/config.toml`

Key sections:

```toml
[model]
name = "openrouter/free"
temperature = 1.0

api_key = "sk-..."
api_base_url = "https://openrouter.ai/api/v1"

max_turns = 72
max_tool_output_tokens = 50000
supports_vision = false       # true if model can process images (GPT-4o, Claude-3, etc.)
approval = "on_request"
hooks_enabled = true
developer_instructions = "..."
user_instructions = "..."

[shell_environment]
exclude_patterns = ["*KEY*", "*TOKEN*", "*SECRET*"]

[[hooks]]
name = "format_on_write"
trigger = "after_tool"
command = "black {file}"
enabled = true

[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/path"]

[mcp_servers.sequential_thinking]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-sequentialthinking"]
enabled = true

[mcp_servers.memory]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-memory"]
enabled = true
# Optional: pin where the knowledge graph file lives on disk
# env = { MEMORY_FILE_PATH = "D:/mine/CharanCLI/.charancli/memory.json" }

[mcp_servers.fetch]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-fetch"]
enabled = true
# Optional tuning:
# env = {
#   FETCH_MAX_RESPONSE_SIZE = "512000",   # bytes, default 5MB — trim for speed
#   FETCH_TIMEOUT_MS = "10000"            # 10s timeout per request
# }
```

---

## Custom Tool Development

Place a `.py` file in `<project>/.charancli/tools/`:

```python
from tools.base import Tool, ToolResult, ToolInvocation, ToolKind
from pydantic import BaseModel, Field

class MyTool(Tool):
    name = "my_tool"
    description = "Does something useful"
    kind = ToolKind.READ  # or WRITE, SHELL, NETWORK, MEMORY

    class Schema(BaseModel):
        message: str = Field(description="Input message")

    schema = Schema

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        return ToolResult.success_result(f"Got: {invocation.params['message']}")
```

---

## Development Workflow Notes

1. **No test suite** — project has no pytest/unittest configuration; test manually via `charancli`
2. **Scripts directory** — `scripts/check_schemas.py` and `scripts/test_tool.py` available for debugging
3. **Undo support** — the agent tracks file diffs in `_undo_stack` for `/undo` command
4. **Loop detection** — `LoopDetector` monitors for repetitive tool calls and injects a loop-breaker prompt
5. **Context compression** — when context exceeds 80% of window, `ChatCompressor` summarizes history
6. **Truncation recovery** — handles `finish_reason: "length"` by asking model to continue
7. **Parallel tool execution** — multiple tool calls in one turn run concurrently via `asyncio.gather`
8. **Tool output truncation** — oversized outputs truncated to `max_tool_output_tokens * 4` chars
9. **Approval flow** — mutating tools (WRITE, SHELL, NETWORK) require approval based on policy
10. **MCP tools** — registered separately in `_mcp_tools` dict; discovered at session initialization

---

## Project-Specific Rules

- **Entry point is `main:main`** — defined in `pyproject.toml` as `charancli = "main:main"`
- **Packages must be listed in `pyproject.toml`** under `[tool.setuptools] packages = [...]`
- **Config uses `platformdirs`** — cross-platform paths via `user_config_dir("charancli")` and `user_data_dir("charancli")`
- **Windows compatibility** — `os.chmod` calls are skipped on Windows; shell info reports `PowerShell/cmd.exe`
- **API credentials** — stored in TOML config or env vars (`API_KEY`, `API_BASE_URL`); masked in display
- **Tool schemas cleaned** — Pydantic artifacts (`$defs`, `anyOf`, `title`, `default`) stripped for LLM compatibility
- **Thinking/reasoning tokens** — captured from `reasoning_content` or `reasoning` fields in streamed responses
