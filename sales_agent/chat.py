from __future__ import annotations

import os
import sys
from pathlib import Path

from sales_agent.agent import respond
from sales_agent.envfile import load_local_env
from sales_agent.llm import complete
from sales_agent.session import Session


def run_chat(lines, db_path: Path, complete_fn=None, echo=None) -> str:
    if complete_fn is None:
        complete_fn = complete
    session = Session()
    replies: list[str] = []
    for line in lines:
        user_message = line.rstrip("\n")
        if user_message == "":
            break
        reply = respond(session, user_message, db_path, complete_fn)
        replies.append(reply)
        if echo is not None:
            echo(reply)
    return "\n".join(replies)


def main() -> None:
    load_local_env()
    db_path = Path(os.environ.get("SALES_DB", "data/olist.sqlite"))
    print("Sales analytics chat. Enter a blank line to exit.")
    run_chat(sys.stdin, db_path, echo=print)


if __name__ == "__main__":
    main()
