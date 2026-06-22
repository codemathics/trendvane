#!/usr/bin/env python3
"""
trend-radar local installer (git-clone path).

most people should just run:

    npx skills add codemathics/trend-radar -g -a claude-code

...which installs the skill files for them. this script is the equivalent for
people who cloned the repo and don't want to use the skills cli. it:

  1. installs python dependencies
  2. copies the skill into ~/.claude/skills/
  3. creates the user data dir (~/.claude/trend-radar) so config survives updates

after it runs, open claude code and type /trend-radar.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILLS_SRC = REPO_ROOT / "skills"
CLAUDE_SKILLS = Path.home() / ".claude" / "skills"
DATA_DIR = Path.home() / ".claude" / "trend-radar"

SEP = "=" * 54


def step(label: str) -> None:
    print(f"\n{SEP}\n  {label}\n{SEP}")


def ok(msg: str) -> None:
    print(f"  ok   {msg}")


def warn(msg: str) -> None:
    print(f"  !    {msg}")


# ---------------------------------------------------------------------------
# 1. python version
# ---------------------------------------------------------------------------
step("checking python")
if sys.version_info < (3, 10):
    print(f"\n  python {sys.version.split()[0]} found, but trend-radar needs 3.10+")
    print("  download: https://www.python.org/downloads/\n")
    sys.exit(1)
ok(f"python {sys.version.split()[0]}")


# ---------------------------------------------------------------------------
# 2. install python dependencies
# ---------------------------------------------------------------------------
step("installing dependencies")
req = REPO_ROOT / "requirements.txt"
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", str(req), "--quiet"],
    capture_output=True, text=True,
)
if result.returncode != 0:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req), "--break-system-packages", "--quiet"],
        capture_output=True, text=True,
    )
if result.returncode == 0:
    ok("pytrends and dependencies installed")
else:
    warn("pip install had errors - run it manually:")
    warn(f"pip install -r {req}")


# ---------------------------------------------------------------------------
# 3. install the skills
# ---------------------------------------------------------------------------
step("installing claude code skills")
CLAUDE_SKILLS.mkdir(parents=True, exist_ok=True)

for name in ("trend-radar",):
    src = SKILLS_SRC / name
    dst = CLAUDE_SKILLS / name
    if not (src / "SKILL.md").exists():
        warn(f"skipping {name}: no SKILL.md at {src}")
        continue
    try:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            src, dst,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "cache", "briefings",
                # never carry a developer's private config into an install
                "notion_config.json", "secrets.json",
            ),
        )
        ok(f"installed {name}")
    except Exception as e:
        warn(f"could not install {name}: {e}")


# ---------------------------------------------------------------------------
# 4. create the user data dir (survives skill updates)
# ---------------------------------------------------------------------------
step("creating user data dir")
(DATA_DIR / "memory").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "briefings").mkdir(parents=True, exist_ok=True)
ok(f"data dir ready at {DATA_DIR}")

# seed the data dir with the shipped templates so the setup agent has
# something to edit (without clobbering anything the user already has).
seed_src = SKILLS_SRC / "trend-radar" / "memory"
for fname in ("my_niches.json", "voice_examples.md", "used_hooks.json",
              "notion_config.example.json", "secrets.example.json"):
    s = seed_src / fname
    d = DATA_DIR / "memory" / fname
    if s.exists() and not d.exists():
        shutil.copy2(s, d)
ok("seeded default config into data dir")


# ---------------------------------------------------------------------------
# 5. done
# ---------------------------------------------------------------------------
print(f"\n{SEP}\n  ready\n{SEP}\n")
print("  open claude code and type:\n")
print("      /trend-radar\n")
print("  on the first run it walks you through notion, your niches,")
print("  your voice, and a test run. about 10-15 minutes.\n")
