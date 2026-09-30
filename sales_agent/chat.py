from __future__ import annotations

import os
import sys
from pathlib import Path

from sales_agent.agent import respond
from sales_agent.llm import complete
from sales_agent.session import Session


def run_chat(lines, db_path: Path, complete_fn=complete) -> str:
    session = Session()
    replies: list[str] = []
    for line in lines:
        if line == "":
            break
        reply = respond(session, line, db_path, complete_fn)
        replies.append(reply)
    return "\n".join(replies)


def main() -> None:
    db_path = Path(os.environ.get("SALES_DB", "data/olist.sqlite"))
    print("Sales analytics chat. Enter a blank line to exit.")
    session = Session()
    for line in sys.stdin:
        user_message = line.rstrip("\n")
        if user_message == "":
            break
        reply = respond(session, user_message, db_path)
        print(reply)


if __name__ == "__main__":
    main()
