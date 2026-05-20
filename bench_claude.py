#!/usr/bin/env python3
"""Temporary benchmark: compare claude -p startup latency with/without flags."""

import asyncio
import time

PROMPT = """\
Here is a conversation from a Claude Code session:

<conversation>
Session ID: abc123
Project: my-web-app
Branch: feature/auth-refactor
Started: 2026-05-10 09:14:22 UTC
Messages: 24

[USER] (09:14:22)
I want to refactor the authentication middleware to use JWT tokens instead of session cookies. Can you help me plan this out?

[ASSISTANT] (09:14:25)
Happy to help. The main steps would be: replace the session store with a JWT signing/verification layer, update the login endpoint to issue tokens, add a middleware that validates the Authorization header, and update the client to store and send the token. Want to start with the middleware?

[USER] (09:15:01)
Yes, let's start there. Here's the current middleware:
[Tool: Read(file_path=src/middleware/auth.py)]

[ASSISTANT] (09:15:04)
[Tool: Read(file_path=src/middleware/auth.py)]
I can see it's using Flask-Session with a Redis backend. The JWT replacement will be simpler — no Redis dependency needed. Here's a draft using PyJWT...

[USER] (09:22:18)
That looks good. What about token expiry and refresh tokens?

[ASSISTANT] (09:22:21)
For this use case I'd recommend short-lived access tokens (15 min) paired with a refresh token stored in an httpOnly cookie. That keeps the XSS surface small while avoiding forcing re-login every 15 minutes.

[USER] (09:35:44)
OK let's go with that approach. Can you implement it?

[ASSISTANT] (09:35:48)
[Tool: Edit(file_path=src/middleware/auth.py)]
[Tool: Edit(file_path=src/routes/auth.py)]
[Tool: Write(file_path=src/middleware/jwt_utils.py)]
Done. I've updated the middleware, the login/logout routes, and added a jwt_utils module for signing and verification. The refresh endpoint is at POST /auth/refresh.

[USER] (09:48:12)
The tests are failing — looks like the test client doesn't send the Authorization header automatically.

[ASSISTANT] (09:48:15)
[Tool: Read(file_path=tests/conftest.py)]
Right, the test client fixture needs updating. Add a helper that wraps requests with the token...
[Tool: Edit(file_path=tests/conftest.py)]
That should fix it. Re-run pytest.

[USER] (09:51:03)
Tests pass now. Let's commit and open a PR.

[ASSISTANT] (09:51:06)
[Tool: Bash(command=git add src/middleware/ src/routes/auth.py tests/conftest.py)]
[Tool: Bash(command=git commit -m "Refactor auth to use JWT with refresh tokens")]
[Tool: Bash(command=gh pr create --title "Replace session cookies with JWT auth" --body "...")]
PR created: https://github.com/org/my-web-app/pull/47
</conversation>

What were the main technical decisions made in this session and what was the final outcome?

Provide a clear, concise answer based only on the conversation content above.\
"""
RUNS = 3

VARIANTS = [
    ("baseline", ["claude", "-p", "--model", "haiku"]),
    ("strict-mcp-config", ["claude", "-p", "--model", "haiku", "--strict-mcp-config"]),
    ("strict-mcp-config + effort low", ["claude", "-p", "--model", "haiku", "--strict-mcp-config", "--effort", "low"]),
]


async def run_once(args: list[str]) -> float:
    start = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate(PROMPT.encode())
    return time.monotonic() - start


async def bench(label: str, args: list[str]) -> list[float]:
    print(f"\n{label}")
    times = []
    for i in range(1, RUNS + 1):
        t = await run_once(args)
        times.append(t)
        print(f"  run {i}: {t:.2f}s")
    avg = sum(times) / len(times)
    print(f"  avg: {avg:.2f}s  min: {min(times):.2f}s  max: {max(times):.2f}s")
    return times


async def main() -> None:
    print(f"Benchmarking claude -p latency ({RUNS} runs each)\n{'=' * 50}")
    results = {}
    for label, args in VARIANTS:
        results[label] = await bench(label, args)

    baseline = sum(results["baseline"]) / RUNS
    print(f"\n{'=' * 50}\nSummary (vs baseline {baseline:.2f}s avg)")
    for label, times in results.items():
        avg = sum(times) / len(times)
        delta = avg - baseline
        sign = "+" if delta >= 0 else ""
        print(f"  {label}: {avg:.2f}s ({sign}{delta:.2f}s)")


asyncio.run(main())
