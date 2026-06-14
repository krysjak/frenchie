# 🐶 Frenchie (v0.1)

> **A terminal AI coding assistant that works with local models (via LM Studio/Ollama) and the Anthropic API — switchable live.**

---

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />
  <img src="https://img.shields.io/badge/Status-Alpha--v0.1-orange?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/Local%20LLMs-Supported-purple?style=for-the-badge&logo=openai&logoColor=white" alt="Local LLMs" />
</p>

---

## 🌟 Introduction

**Frenchie** is a Python-based interactive terminal AI coding assistant designed to act as an autonomous developer inside your project workspace. It ports the core orchestration logic of advanced coding agents to Python, enabling direct tool execution, bash runs, and file edits.

Unlike other tools, Frenchie is designed to be **provider-agnostic**, allowing you to seamlessly swap between **local offline models (via LM Studio, Ollama)** and **cloud engines (Anthropic API)** live in the middle of a REPL session.

---

## 🚀 Current Features (v0.1 - What Works Now)

- **Interactive TUI REPL**: Syntax-highlighted interface with command auto-complete, token cost tracking, and history suggestions.
- **Dual-Provider Architecture**: Live switch between:
  - **Local models** (LM Studio, Ollama, or any OpenAI-compatible API).
  - **Anthropic API** (Claude 3.5 Sonnet/Haiku/Opus, including extended thinking support).
- **Comprehensive Toolbelt (20+ Tools)**:
  - **File Operations**: `Read` (with MIME, PDF, image, notebook parsing), `Write`, and `Edit` (applying robust line patches).
  - **Code Navigation**: `Glob` and `Grep` (pattern searches).
  - **Shell Execution**: Interactive `Bash` and `PowerShell` runners with configurable permissions.
  - **External Inputs**: `WebFetch` to read remote resources/documentation.
- **Granular Permission Manager**: Three runtime modes (`default/ask` for safe verification, `plan` for read-only exploration, and `auto` for fully autonomous runs).
- **FastAPI Visual Server**: Basic backend server prepared to visual session tracking (`/web`).

---

## 🗺️ Project Hermes: Evolution Roadmap (Planned Custom Features)

We are actively developing **Project Hermes** — a set of advanced features to make Frenchie the most capable and context-aware coding agent:

### 1. Dynamic Multi-Agent System
Transitioning from a single-loop prompt to a collaborative multi-agent framework:
* **Frenchie-Orchestrator**: Manages token consumption and delegates sub-tasks.
* **Frenchie-Planner (Architect)**: Scans codebase structure and drafts step-by-step implementation plans (`task.md`).
* **Frenchie-Coder**: Implements edits based on the plan.
* **Frenchie-Verifier (Critic)**: Runs test suites and captures syntax/runtime errors, prompting the Coder to auto-fix them in a **Self-Healing Loop** before finishing.

### 2. Cognitive Memory System (CMS)
Four levels of active context memory:
* **Project Map (`FRENCHIE_MAP.json`)**: An automated graph of codebase architecture, modules, and schemas.
* **Memory Anchors (`.frenchie/memory_anchors.json`)**: Sticky developer notes loaded automatically when relevant files are read.
* **Episodic memory**: Logging past actions and fixes in the current session to trace bug origins.
* **Active Scratchpad**: Sub-agent shared scratchpad for compiling and temporary variables.

### 3. Dynamic Runtime Execution Probe (`ProbeExecution`)
An automatic debugging tool that copies target functions, runs them wrapped in a tracer (`sys.settrace`), and generates a **Runtime Snapshot** (variable values, types, and logic branch executions) to feed directly into the agent's context.

### 4. Git Intent & Self-Learning (Skills)
* **Git Blame Context**: Analyzing git blame and commits on modified lines to preserve the original author's design intent.
* **Skills Directory (`.frenchie/skills/`)**: Automatically saving verified coding recipes to recall and resolve future tasks faster.

### 5. Codex-Style Web UI
A premium React split-screen workspace displaying chat/agent Mermaid trees on the left, and a file tree, visual code editor, and live Git Diff on the right.

---

## 🛠️ Installation & Launch

### Prerequisites
- **Python 3.11** or higher
- **Git**

### Installation
Clone the repository and install it locally in editable mode:
```bash
git clone https://github.com/krysjak/frenchie.git
cd frenchie
pip install -e .
```

### Launching the REPL
Start the interactive session inside your project workspace:
```bash
frenchie
```

To run single queries directly:
```bash
frenchie run "review the pyproject.toml file for dependency issues"
```

To run connection diagnostics:
```bash
frenchie doctor
```

---

## 🔌 Custom Providers & Local Setup

### 💻 1. LM Studio (Local Offline)
1. Launch **LM Studio** and download a model (e.g., `qwen2.5-coder-7b-instruct` or `gemma-2-9b-it`).
2. Start the **Local Inference Server** (default port `1234`).
3. In the Frenchie REPL, switch your provider:
   - Run `/provider` ➔ select `lm-studio` (or `openai`).
   - Enter Base URL: `http://localhost:1234/v1`
   - Set the active model: `/model <your-model-name>`

### 🐋 2. Ollama Setup
1. Start Ollama locally.
2. Run `/provider` in Frenchie.
   - Enter Base URL: `http://localhost:11434/v1`
   - Enter Model: `qwen2.5-coder` or `llama3`

### ☁️ 3. Cloud APIs (Anthropic, OpenRouter, Groq)
* **Anthropic**: Run `/login` to save your `ANTHROPIC_API_KEY`, then select `anthropic` under `/provider`.
* **OpenRouter**: Set the base URL to `https://openrouter.ai/api/v1` and supply your OpenRouter token.

---

## 🎛️ Command Registry & REPL Shortcuts

| Command | Arguments | Description |
|:---|:---|:---|
| `/provider` | `[openai / anthropic / lm-studio]` | Switch LLM host live |
| `/model` | `[model-name]` | Change active model |
| `/effort` | `[low / medium / high / xhigh]` | Set thinking token budget for supporting models |
| `/init` | — | Initialize `FRENCHIE.md` memory files in active project |
| `/permissions`| `[show / mode <plan, auto, default>]` | Configure safety approval modes for tool calls |
| `/mcp` | `[list / enable / disable]` | Manage Model Context Protocol (MCP) servers |
| `/memory` | `[list / edit]` | Inspect project map or memory anchors |
| `/doctor` | — | Verify installation settings, paths, and API keys |
| `/web` | — | Start the FastAPI visual dashboard |
| `/bridge` | — | Open the WebSocket editor integration bridge |

### REPL Shortcuts
* **`Tab`** (on an empty prompt): Toggle execution modes (`Build` ➔ `Plan` ➔ `Auto`).
* **`Ctrl + L`**: Clears the console and re-renders the bulldog header.
* **`Ctrl + D`**: Safely exit the REPL.
* **`Ctrl + C`**: Interrupt a streaming model response or kill a running subprocess tool.

---

## 📂 Architecture Overview

```
claude_code_py/
  ├── cli.py             # Click-based command-line interface entry points
  ├── repl.py            # prompt_toolkit REPL with status bar & auto-suggestions
  ├── query.py           # Core agent turn-loop, stream handler, and tool caller
  ├── permissions.py     # Approval policy manager (Plan, Auto, Build permissions)
  ├── config.py          # Environment and persistent JSON configuration models
  ├── commands/          # Subdirectory for REPL slash-commands (/provider, /mcp, etc.)
  ├── tools/             # Built-in actions (Read, Edit, Glob, Bash, Probe)
  ├── services/          # Services layer (Claude Client, cost tracking, bridge, dashboard)
  ├── mcp/               # Model Context Protocol host transport and resource tools
  └── resources/         # Markdown system prompts and guides
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

