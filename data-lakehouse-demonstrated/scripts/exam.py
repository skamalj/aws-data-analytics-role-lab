"""
Mock exam for the Data Lakehouse Demonstrated kit.

    ./scripts/exam.sh start [official|all|C1,C4,...]   deploy base + the challenges, shuffle them, start the clock
    ./scripts/exam.sh status                           time left and the challenge list
    ./scripts/exam.sh grade                            run every challenge's scenarios/check.py and score it
    ./scripts/exam.sh end                              destroy the challenge stacks (keeps base; ./scripts/destroy.sh base)

"official" = C1-C7, one per exam objective, 110 minutes.
The briefing (exam/briefing.md) contains each challenge's brief with the hints removed.
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
OFFICIAL = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
MINUTES = 110
PREP = {}  # environment preparation that is part of the setup, not of the challenge (deploy.sh already runs setup/post_deploy)


def mission_dir(mid):
    return next(os.path.join(ROOT, "missions", d) for d in sorted(os.listdir(os.path.join(ROOT, "missions")))
                if d.startswith(mid + "-"))


def section(text, title):
    m = re.search(rf"^## {title}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def briefing(order):
    out = [f"# Mock exam: AWS Data Lakehouse Demonstrated ({MINUTES} minutes)\n",
           "Challenges are independent and listed in random order. Read each one fully before you act.",
           "Grade yourself any time with `./scripts/exam.sh grade`. Hints and solutions are off-limits until you finish.\n"]
    for n, mid in enumerate(order, 1):
        text = open(os.path.join(mission_dir(mid), "README.md")).read()
        title = text.splitlines()[0].lstrip("# ").split(":", 1)[-1].strip()
        obj = re.search(r"\*\*Exam objective:\*\* \*(.+?)\*", text)
        out.append(f"## Challenge {n}: {title}" + (f"  \n*Objective: {obj.group(1)}*" if obj else ""))
        out.append(f"Folder: `{os.path.relpath(mission_dir(mid), ROOT)}`\n")
        body = text[text.index("## Situation"):] if "## Situation" in text else text
        body = re.sub(r"^<details>.*$\n?", "", body, flags=re.M)          # no hints in exam mode
        body = re.sub(r"^## ", "### ", body, flags=re.M)
        rel = os.path.relpath(mission_dir(mid), ROOT)
        body = re.sub(r"\]\((?!https?:|#|/)", f"](../{rel}/", body)        # exam/briefing.md lives one level down
        out.append(body.strip() + "\n")
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
    print(">> challenge stacks destroyed. Shared buckets/catalog remain: ./scripts/destroy.sh base")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"start": lambda: start(sys.argv[2] if len(sys.argv) > 2 else "official"),
     "status": status, "grade": grade, "end": end}[cmd]()
