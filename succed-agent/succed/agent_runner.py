"""Headless runs with the Claude Agent SDK (scheduled jobs, CI, back-office).

Uses the SAME subagents (.claude/agents), slash commands and MCP server as interactive Claude Code.
Example:
    python -m succed.agent_runner "/pilot-scorecard altos-andes"
    python -m succed.agent_runner "Screen every PDF in data/inbox and score the companies"

Requires: `pip install claude-agent-sdk` and Claude Code CLI available, ANTHROPIC_API_KEY set.
Unattended runs cannot use Bash and cannot approve drafts (approval is a CLI-only human action).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED = ["Read", "Glob", "Grep", "WebSearch", "WebFetch", "Task", "mcp__succed"]
DISALLOWED = ["Bash", "Write", "Edit"]


async def run(prompt: str, model: str | None = None, max_turns: int = 40) -> int:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

    opts = ClaudeAgentOptions(
        cwd=str(ROOT),
        setting_sources=["project"],          # loads CLAUDE.md, .claude/agents, .claude/commands, skills
        mcp_servers=ROOT / ".mcp.json",
        allowed_tools=ALLOWED,
        disallowed_tools=DISALLOWED,
        permission_mode="default",
        max_turns=max_turns,
        model=model,
    )
    code = 0
    async for msg in query(prompt=prompt, options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    print(b.text, flush=True)
        elif isinstance(msg, ResultMessage):
            if msg.is_error:
                code = 1
            print(f"\n[done] turns={msg.num_turns} cost_usd={getattr(msg, 'total_cost_usd', None)}", file=sys.stderr)
    return code


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    return asyncio.run(run(" ".join(sys.argv[1:])))


if __name__ == "__main__":
    sys.exit(main())
