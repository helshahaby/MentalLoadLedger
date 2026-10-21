"""
Mental Load Ledger - an Alexa+ MCP server (Streamable HTTP).

Households split visible chores more fairly than "invisible" work (planning,
remembering, scheduling). Say it out loud to Alexa+ and this server keeps a
weighted ledger, shows the balance, and suggests a fair hand-off.

Run:  python server.py          -> MCP endpoint at http://0.0.0.0:8000/mcp
"""
import os
import sqlite3
import time
from collections import Counter
from contextlib import contextmanager

from mcp.server.fastmcp import FastMCP

DB_PATH = os.environ.get("LEDGER_DB", "ledger.db")
INVISIBLE_WEIGHT = 1.5      # planning/remembering counts extra
BALANCE_TOLERANCE = 0.10    # +/-10% of an equal share counts as balanced

mcp = FastMCP(
    "mental-load-ledger",
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "8000")),
)


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            household TEXT NOT NULL,
            who TEXT NOT NULL,
            title TEXT NOT NULL,
            points REAL NOT NULL,
            invisible INTEGER NOT NULL,
            ts REAL NOT NULL)"""
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _norm(s: str) -> str:
    return s.strip().lower()


def _totals(conn, household: str, days: int):
    since = time.time() - days * 86400
    rows = conn.execute(
        "SELECT who, title, points FROM tasks WHERE household=? AND ts>=?",
        (household, since),
    ).fetchall()
    totals: dict[str, float] = {}
    for r in rows:
        totals[r["who"]] = totals.get(r["who"], 0) + r["points"]
    return rows, totals


@mcp.tool()
def log_task(who: str, task: str, effort: int = 2, invisible: bool = False,
             household: str = "default") -> str:
    """Log a household task someone did.

    Args:
        who: Name of the person who did it, e.g. "Sam".
        task: Short description, e.g. "booked the dentist".
        effort: 1 (tiny) to 5 (exhausting).
        invisible: True for planning, remembering, scheduling or coordinating work.
        household: Household id; leave as default for a single home.
    """
    effort = max(1, min(5, effort))
    points = effort * (INVISIBLE_WEIGHT if invisible else 1.0)
    with db() as conn:
        conn.execute(
            "INSERT INTO tasks(household, who, title, points, invisible, ts) VALUES(?,?,?,?,?,?)",
            (household, _norm(who), _norm(task), points, int(invisible), time.time()),
        )
    kind = "invisible " if invisible else ""
    return f"Logged: {who.title()} did {task}, worth {points:g} {kind}points."


@mcp.tool()
def get_balance(days: int = 7, household: str = "default") -> dict:
    """Show who carried how much of the household load over the last N days."""
    with db() as conn:
        _, totals = _totals(conn, household, days)
    if not totals:
        return {"spoken": f"Nothing logged in the last {days} days.", "shares": {}}
    total = sum(totals.values())
    equal = total / len(totals)
    shares = {n.title(): round(100 * p / total) for n, p in totals.items()}
    top = max(totals, key=totals.get)
    gap = (totals[top] - equal) / equal if equal else 0
    if gap <= BALANCE_TOLERANCE:
        verdict = "You are pretty evenly balanced."
    else:
        verdict = f"{top.title()} is carrying {round(gap * 100)} percent more than a fair share."
    spoken = ", ".join(f"{n} {s} percent" for n, s in shares.items()) + ". " + verdict
    return {"spoken": spoken, "shares": shares, "points": {k.title(): v for k, v in totals.items()}}


@mcp.tool()
def suggest_handoff(days: int = 14, household: str = "default") -> dict:
    """Suggest one concrete task the busiest person could hand to the lightest-loaded person."""
    with db() as conn:
        rows, totals = _totals(conn, household, days)
    if len(totals) < 2:
        return {"spoken": "I need tasks logged for at least two people first."}
    heavy = max(totals, key=totals.get)
    light = min(totals, key=totals.get)
    equal = sum(totals.values()) / len(totals)
    if (totals[heavy] - equal) / equal <= BALANCE_TOLERANCE:
        return {"spoken": "No hand-off needed, the load looks fair."}
    counts = Counter(r["title"] for r in rows if r["who"] == heavy)
    task, n = counts.most_common(1)[0]
    return {
        "spoken": (f"{heavy.title()} has done '{task}' {n} times lately. "
                   f"How about {light.title()} takes it over next week?"),
        "from": heavy.title(), "to": light.title(), "task": task,
    }


@mcp.tool()
def weekly_recap(household: str = "default") -> str:
    """A short, voice-friendly recap of the last 7 days including invisible work."""
    since = time.time() - 7 * 86400
    with db() as conn:
        rows = conn.execute(
            "SELECT who, COUNT(*) c, SUM(invisible) inv FROM tasks "
            "WHERE household=? AND ts>=? GROUP BY who", (household, since)).fetchall()
    if not rows:
        return "No tasks logged this week."
    parts = [f"{r['who'].title()} did {r['c']} tasks, {int(r['inv'] or 0)} of them invisible planning work"
             for r in rows]
    return "This week: " + "; ".join(parts) + "."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
