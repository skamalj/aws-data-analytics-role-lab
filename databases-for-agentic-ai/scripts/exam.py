"""
Mock exam for the Databases for Agentic AI kit.

    ./scripts/exam.sh start [official|all|D1,D6,...]   deploy base + the challenges, shuffle them, start the clock
    ./scripts/exam.sh status                           time left and the challenge list
    ./scripts/exam.sh grade                            run every challenge's scenarios/check.py and score it
    ./scripts/exam.sh end                              destroy the challenge stacks (keeps base; ./scripts/destroy.sh base)

"official" = the seven challenges that map to the exam objectives (D1, D2, D3, D4, D6, D7, D8), 140 minutes.
The briefing (exam/briefing.md) contains each challenge's situation and objectives - no hints, no toolkit.
"""
import json
import os
import random
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAM = os.path.join(ROOT, "exam")
STATE = os.path.join(EXAM, "state.json")
OFFICIAL = ["D1", "D2", "D3", "D4", "D6", "D7", "D8"]
MINUTES = 140
PREP = {  # environment preparation that is part of the setup, not of the challenge
    "D7": ["python3", "missions/D7-dynamodb-mcp-state-inspection/scenarios/seed_conversations.py"],
}


def mission_dir(mid):
    return next(os.path.join(ROOT, "missions", d) for d in sorted(os.listdir(os.path.join(ROOT, "missions")))
                if d.startswith(mid + "-"))


def section(text, title):
    m = re.search(rf"^## {title}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def briefing(order):
    out = [f"# Mock exam: Databases for Agentic AI ({MINUTES} minutes)\n",
           "Challenges are independent and listed in random order. Read each one fully before you act.",
           "Grade yourself any time with `./scripts/exam.sh grade`. Hints and solutions are off-limits until you finish.\n"]
    for n, mid in enumerate(order, 1):
        text = open(os.path.join(mission_dir(mid), "README.md")).read()
        title = text.splitlines()[0].lstrip("# ").split(":", 1)[-1].strip()
        obj = re.search(r"\*\*Exam objective:\*\* \*(.+?)\*", text)
        out.append(f"## Challenge {n}: {title}" + (f"  \n*Objective: {obj.group(1)}*" if obj else ""))
        out.append(f"Folder: `{os.path.relpath(mission_dir(mid), ROOT)}`\n")
        for sec in ("Situation", "Objectives", "Done when"):
            body = section(text, sec)
            if body:
                out.append(f"### {sec}\n\n{body}\n")
    return "\n".join(out)


def run(cmd, **kw):
    print("$ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, **kw).returncode


def start(selection):
    ids = OFFICIAL if selection == "official" else (
        sorted({d.split("-")[0] for d in os.listdir(os.path.join(ROOT, "missions"))}, key=lambda x: int(x[1:]))
        if selection == "all" else [s.strip().upper() for s in selection.split(",")])
    os.makedirs(EXAM, exist_ok=True)
    env = {**os.environ, "AUTO_APPROVE": "1"}
    if not os.path.exists(os.path.join(ROOT, "base/terraform/terraform.tfstate")):
        if run(["./scripts/deploy.sh", "base"], env=env):
            sys.exit("base deployment failed")
    for mid in ids:
        if run(["./scripts/deploy.sh", mid], env=env):
            print(f"!! {mid} deployment reported an error (some challenges are broken at deploy time on purpose) - continuing")
        if mid in PREP:
            run(PREP[mid])
    order = ids[:]
    random.shuffle(order)
    open(os.path.join(EXAM, "briefing.md"), "w").write(briefing(order))
    json.dump({"order": order, "started": time.time(), "minutes": MINUTES}, open(STATE, "w"))
    print(f"\n>> Exam started: {len(order)} challenges, {MINUTES} minutes. Read exam/briefing.md")


def state():
    if not os.path.exists(STATE):
        sys.exit("no exam in progress: ./scripts/exam.sh start")
    return json.load(open(STATE))


def status():
    s = state()
    left = s["minutes"] * 60 - (time.time() - s["started"])
    print(f"time left: {max(0, left) // 60:.0f} min {max(0, left) % 60:.0f} s" + ("  (TIME IS UP)" if left <= 0 else ""))
    for n, mid in enumerate(s["order"], 1):
        print(f"  Challenge {n}: {os.path.basename(mission_dir(mid))}")


def grade():
    s = state()
    results = []
    for n, mid in enumerate(s["order"], 1):
        print(f"\n================ Challenge {n} ({mid}) ================", flush=True)
        ok = run(["python3", os.path.join(os.path.relpath(mission_dir(mid), ROOT), "scenarios", "check.py")]) == 0
        results.append((n, mid, ok))
    elapsed = (time.time() - s["started"]) / 60
    print("\n================ SCORE ================")
    for n, mid, ok in results:
        print(f"  Challenge {n} ({mid}): {'PASS' if ok else 'FAIL'}")
    passed = sum(ok for *_, ok in results)
    print(f"  {passed}/{len(results)} challenges passed after {elapsed:.0f} of {s['minutes']} minutes"
          + ("  (over time)" if elapsed > s["minutes"] else ""))


def end():
    s = state()
    env = {**os.environ, "AUTO_APPROVE": "1"}
    for mid in s["order"]:
        run(["./scripts/destroy.sh", mid], env=env)
    os.remove(STATE)
    print(">> challenge stacks destroyed. The shared database is still running: ./scripts/destroy.sh base")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"start": lambda: start(sys.argv[2] if len(sys.argv) > 2 else "official"),
     "status": status, "grade": grade, "end": end}[cmd]()
