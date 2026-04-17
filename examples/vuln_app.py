"""Deliberately vulnerable Flask app — strixnoapi end-to-end target.

This file intentionally ships three textbook security bugs so you can
verify strixnoapi flags them during a scan. Do not run it against real
traffic.
"""

from __future__ import annotations

import sqlite3
import subprocess  # noqa: S404 — intentionally unsafe for demo
from pathlib import Path

from flask import Flask, redirect, request


app = Flask(__name__)
DB = Path(__file__).with_name("demo.sqlite")


@app.route("/login")
def login() -> str:
    """VULNERABLE: SQL injection via string interpolation."""
    user = request.args.get("user", "")
    pw = request.args.get("pw", "")
    query = f"SELECT * FROM users WHERE name='{user}' AND pw='{pw}'"  # noqa: S608
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(query)
    return "ok" if cur.fetchone() else "fail"


@app.route("/ping")
def ping() -> bytes:
    """VULNERABLE: command injection via shell=True + unvalidated host."""
    host = request.args.get("host", "")
    return subprocess.check_output(f"ping -c 1 {host}", shell=True)  # noqa: S602


@app.route("/go")
def go() -> object:
    """VULNERABLE: open redirect — attacker-controlled URL."""
    return redirect(request.args.get("url", "/"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
