The idea: Households tend to split visible chores fairly but not the invisible work, like booking the dentist, planning meals, or remembering birthdays. You tell Alexa+ what got done (“Sam booked the dentist, that was planning work”). The server keeps a weighted ledger, where invisible work counts 1.5×. It can then say who is carrying how much and suggest a specific task to hand off.

Tools (replies are short enough to be spoken):

log_task(who, task, effort, invisible) records a task.
get_balance(days) returns each person’s share and says whether the split is fair.
suggest_handoff() picks the task the busiest person does most and proposes giving it to the lightest-loaded person.
weekly_recap() gives a spoken summary of the week.

Run it:

bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python server.py            # endpoint: https://turf-riverbank-passably.ngrok-free.dev/mcp
python test_client.py       # in a second terminal


## Inspiration

Most couples and housemates split the *visible* chores reasonably well: someone cooks, someone takes out the trash. What goes unnoticed is the **invisible work**: remembering the dentist appointment, planning the week's meals, tracking whose turn it is to call the landlord. Researchers call this the "mental load", and it usually falls on one person without anyone deciding that it should.

It's hard to fix because nobody can see it, and bringing it up feels like an accusation. We wanted a neutral third party in the room: something that quietly keeps score, shows the numbers, and suggests a fair hand-off without anyone having to start an argument. A voice assistant that already lives in the kitchen was the obvious place for it.

## What it does

**Mental Load Ledger** is an Alexa+ integration built as a self-hosted MCP server. Household members tell Alexa+ what got done, in plain language:

> "Sam booked the dentist. That was planning work."

Alexa+ calls the server's tools, which keep a weighted ledger and answer in short, speakable sentences:

- `log_task` records who did what, how much effort it took (1 to 5), and whether it was invisible work.
- `get_balance` says who carried what share over the last N days, and whether the split is fair.
- `suggest_handoff` picks the task the busiest person does most often and proposes giving it to the lightest-loaded person.
- `weekly_recap` gives a short spoken summary of the week, including how much of it was invisible planning work.

Example output from our test run: *"Sam 88 percent, Alex 12 percent. Sam is carrying 76 percent more than a fair share."*

## How the scoring works

Every task earns points from its effort \\( e \in \{1,\dots,5\} \\), with a multiplier \\( w \\) for invisible work:

$$ p = e \cdot w, \qquad w = \begin{cases} 1.5 & \text{invisible (planning, remembering, scheduling)} \\ 1 & \text{visible} \end{cases} $$

For \\( n \\) people with point totals \\( P_i \\) over the chosen window, person \\( i \\)'s share is \\( s_i = P_i / \sum_j P_j \\). The household is **balanced** when nobody is more than 10% above the mean \\( \bar{P} \\):

$$ g = \frac{\max_i P_i - \bar{P}}{\bar{P}} \le 0.10 $$

When \\( g \\) exceeds the threshold, `suggest_handoff` finds the heaviest and lightest people and proposes moving the heavy person's most frequent task. In our example, \\( P = (7.5,\ 1.0) \\), so \\( \bar{P} = 4.25 \\) and \\( g \approx 0.76 \\).

## How we built it

- **MCP server** in Python using the official MCP SDK (`FastMCP`), served over the **Streamable HTTP** transport at `/mcp`, so Alexa+ can connect to it directly.
- **SQLite** for the ledger, so the server has no external dependencies. Every tool call scopes its data by a `household` id.
- **Voice-first design.** Tools return short, speakable strings plus structured data. The `spoken` field is written to sound natural read aloud, with no markdown or symbols.
- **Smoke-test client** (`test_client.py`) that connects over Streamable HTTP, lists the tools, and exercises all four of them end to end.
- **Dockerfile** for deployment to [AWS App Runner / ECS / your host].

```python
@mcp.tool()
def log_task(who: str, task: str, effort: int = 2, invisible: bool = False,
             household: str = "default") -> str:
    points = effort * (INVISIBLE_WEIGHT if invisible else 1.0)
    ...
```

## Challenges we ran into

- **SDK version drift.** The MCP Python SDK recently shipped a 2.x release that renamed `FastMCP` and changed the client APIs. Our code failed on a fresh install until we pinned `mcp>=1.23,<2` and verified against 1.30.
- **Defining "fair".** A pure task count punishes people who do a few heavy jobs, and a pure effort score ignores invisible work. The weighted score and the 10% tolerance band was our compromise. It's a starting point, not a verdict, and the weights are easy to tune.
- **Writing for the ear.** A response that reads fine on screen can sound awkward spoken aloud. We kept every reply to one or two short sentences with the key number up front.
- **Identity.** MCP sessions don't tell us which person is speaking, so the user names who did the task. Per-user voice profiles would be the natural next step.

## What we learned

- How MCP tools, schemas and docstrings shape how an assistant decides what to call and what to say.
- Why the Streamable HTTP transport suits a hosted, multi-session server.
- That the interesting design problem in a "fairness" tool is tone: the output has to be a gentle suggestion rather than a scorecard.

## What's next

- Per-person identity through Alexa+ voice profiles.
- Recurring-task templates and reminders ("it's Alex's turn to plan the week").
- [Optional, only if you build it: Amazon Bedrock to phrase hand-off suggestions kindly and adapt to household preferences.]
- A simple web dashboard for the weekly recap.
