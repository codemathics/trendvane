# trend radar - claude code skill

a claude code skill that runs every morning, fetches what's actually trending across hackernews, reddit, tiktok, youtube, product hunt, and google trends, scores each trend against your content niches, and drops 3 shootable video briefs into a notion database, complete with hooks, timestamped scripts, shot lists, captions, and hashtag stacks.

built to be cloned and configured for any creator. all the personalization lives in a handful of json and markdown files.

---

## quick start

install with one command:

```bash
npx skills add codemathics/trend-radar -g -a claude-code
```

then open claude code and type: `/trend-radar`

the first time you run it, the skill walks you through everything - python deps, notion connection, database creation, niche config, voice profile, and a test run. about 10-15 minutes start to finish. works for both technical and non-technical users. every run after that goes straight to generating your daily briefs.

`npx skills add` uses the open [skills](https://github.com/vercel-labs/skills) cli, which installs the skill files into `~/.claude/skills/`. your own config and data live separately in `~/.claude/trend-radar/`, so running `npx skills update` later never overwrites them.

**prefer to clone instead?**

```bash
git clone https://github.com/codemathics/trend-radar.git
cd trend-radar
python3 setup.py      # installs deps + the skill, then run /trend-radar
```

---

## table of contents

- [how it works](#how-it-works)
- [what you get](#what-you-get)
- [requirements](#requirements)
- [manual setup (advanced)](#manual-setup-advanced)
  - [1. clone the repo](#1-clone-the-repo)
  - [2. install python dependencies](#2-install-python-dependencies)
  - [3. configure your niches](#3-configure-your-niches)
  - [4. write your voice profile](#4-write-your-voice-profile)
  - [5. set up notion](#5-set-up-notion)
  - [6. add api keys (optional)](#6-add-api-keys-optional)
  - [7. install the skill in claude code](#7-install-the-skill-in-claude-code)
- [running the skill](#running-the-skill)
  - [daily scheduled run](#daily-scheduled-run)
  - [on-demand](#on-demand)
- [understanding the output](#understanding-the-output)
- [scoring system](#scoring-system)
- [hook rotation](#hook-rotation)
- [file structure](#file-structure)
- [customization reference](#customization-reference)
- [adding a new data source](#adding-a-new-data-source)
- [failure modes](#failure-modes)

---

## how it works

the skill runs in two stages:

**stage 1: python fetchers** (runs in your terminal)

```bash
python3 scripts/run_all.py
```

six fetchers hit their respective apis and public endpoints, normalize every item into the same shape, and write raw candidate lists to `cache/`. the scoring engine then clusters cross-platform duplicates, applies your niche weights and brand-safe filters, and picks the top 3. the picks land in `cache/picks_YYYYMMDD.json`.

**stage 2: claude generates and publishes** (runs inside claude code)

claude reads the picks file, generates a full content brief for each trend in your voice (using `memory/voice_examples.md`), self-audits for ai-tell phrases, and pushes everything to your notion database via the notion mcp tool. it also saves a local archive to `briefings/YYYY-MM-DD.md` and posts a summary to the chat.

---

## what you get

for each of the 3 daily trend picks, claude produces:

| field | what it contains |
|---|---|
| **trend** | a one-line framing of the trend |
| **hook variants** | 3 hooks from different archetypes, ranked best to worst |
| **script** | beat-by-beat 45/60/90s script with timestamps, vo lines, and visual cues |
| **shot list** | scene-by-scene visual direction assuming a solo shoot |
| **trending audio** | a direct tiktok/ig sound link in the right category |
| **captions** | platform variants for tiktok, instagram, youtube shorts, and x |
| **hashtags** | 3-tier stacks (broad / mid / niche) per platform |
| **source urls** | raw links from the fetcher cluster |
| **reference clips** | the actual viral posts driving the trend |
| **score** | 0-100 composite score from the scoring engine |
| **velocity** | rising / peaking / fading |
| **time-to-stale** | how long before the window closes |

everything lands in notion as both table properties (so your database view is filled) and as a full-length page body (so you can read it top to bottom without opening the properties panel).

---

## requirements

- **claude code:** [claude.ai/code](https://claude.ai/code) or the cli (`npm install -g @anthropic-ai/claude-code`)
- **notion mcp** configured in your claude code setup (see [step 5](#5-set-up-notion))
- **python 3.10+**
- a notion workspace with two databases: `trend radar` and `hook library` (templates below)

optional (improves results but not required):
- youtube data api v3 key
- product hunt developer token

---

## manual setup (advanced)

if you prefer to set everything up yourself without the guided flow, here are the full steps. most users should use `npx skills add codemathics/trend-radar -g -a claude-code` (or `python3 setup.py` from a clone) then `/trend-radar` instead.

### 1. clone the repo

```bash
git clone https://github.com/codemathics/trend-radar.git
cd trend-radar
```

### 2. install python dependencies

the only external dependency is `pytrends` for google trends. all other fetchers use python's standard library.

```bash
pip install -r requirements.txt
```

if you're on a system python (macos, ubuntu), add `--break-system-packages`:

```bash
pip install -r requirements.txt --break-system-packages
```

test that the fetchers can run:

```bash
python3 scripts/run_all.py
```

you should see log output ending with `N picks ready for brief generation`. if a source fails (e.g., tiktok rate-limiting), it logs a warning and continues. one dead source does not stop the run.

### 3. configure your niches

open `memory/my_niches.json`. the key fields:

```json
{
  "owner": "your-name",
  "niches": [
    {
      "id": "ai",
      "label": "ai / llms / models",
      "weight": 3.0,
      "keywords": ["ai", "llm", "claude", "agent", "..."],
      "sources_priority": ["hackernews", "reddit_ai", "youtube"],
      "subreddits": ["localllama", "chatgpt", "claudeai"]
    }
  ]
}
```

**`weight`:** how much to boost this niche's score relative to others. in the default config, ai is 3x, product design and filmmaking are 2x, and everything else is 1x. adjust to match your actual posting priorities.

**`keywords`:** the terms the scoring engine matches against trend text. be specific. "ai coding" catches more signal than just "ai".

**`subreddits`:** which subreddits the reddit fetcher hits for this niche.

**`brand_safe_exclusions`:** at the bottom of the file, a list of blocked topics (politics, alcohol, gambling) and regex patterns. add anything you'd never want to post about.

**`scoring_weights`:** the five scoring dimensions and their weights:

| dimension | default weight | what it measures |
|---|---|---|
| `niche_fit` | 0.40 | how well the trend matches your keywords and niche weights |
| `velocity` | 0.25 | how fast the trend is growing (rank movement, mention percentile) |
| `cross_platform` | 0.15 | bonus for appearing on multiple platforms simultaneously |
| `recency` | 0.10 | how fresh the content is (7-day decay) |
| `originality` | 0.10 | penalty for trends you've already covered in the last 30 days |

### 4. write your voice profile

open `memory/voice_examples.md`. this is the most important file for output quality. it tells claude how you actually write: your opening patterns, sentence rhythm, casing rules, what you never say, emoji habits, and real examples from your posts.

the template has a section-by-section guide. the more real examples you paste in (actual captions from your posts), the closer the briefs will sound like you.

claude reads this file before generating every brief and audits every line against your rules before pushing to notion.

### 5. set up notion

you need two databases in notion before the skill can write anything.

**create the trend radar database** with these properties:

| property name | type |
|---|---|
| trend | title |
| date spotted | date |
| platforms | multi-select |
| category | select (ai, product design, filmmaking, tech, how-to, lifestyle, business) |
| velocity | select (rising, peaking, fading) |
| score | number |
| time-to-stale | select (< 3 days, 1 week, 2+ weeks) |
| status | select (new, filming, posted, archived) |
| trending audio | url |
| hook variants | text |
| script | text |
| shot list | text |
| caption | text |
| hashtags | text |
| source urls | text |
| reference clips | text |
| my take | text |
| posted url | url |
| performance | text |

**create the hook library database** with these properties:

| property name | type |
|---|---|
| hook | title |
| archetype | select |
| niche | select |
| used date | date |

**connect the notion mcp** to claude code. follow the [notion mcp setup guide](https://github.com/makenotion/notion-mcp-server) to get the integration token, then add it to your claude code mcp config. the skill uses the notion mcp tool (`notion-create-pages`) to write. it does not use the notion rest api directly.

**fill in your notion config:**

```bash
cp memory/notion_config.example.json memory/notion_config.json
```

edit `memory/notion_config.json` with your workspace details:

```json
{
  "workspace_user": {
    "name": "your name",
    "email": "you@example.com",
    "user_id": "your-notion-user-id"
  },
  "parent_page": {
    "title": "trend radar",
    "url": "https://www.notion.so/your-parent-page-url",
    "id": "your-parent-page-id"
  },
  "databases": {
    "trend_radar": {
      "title": "trend radar",
      "url": "https://www.notion.so/your-trend-radar-db-url",
      "data_source_id": "your-trend-radar-data-source-id",
      "data_source_url": "collection://your-trend-radar-data-source-id"
    },
    "hook_library": {
      "title": "hook library",
      "url": "https://www.notion.so/your-hook-library-db-url",
      "data_source_id": "your-hook-library-data-source-id",
      "data_source_url": "collection://your-hook-library-data-source-id"
    }
  }
}
```

to find your database's `data_source_id`, open the database in notion, click the three-dot menu, copy the link, and extract the uuid from the url.

`notion_config.json` is gitignored. it will not be committed.

### 6. add api keys (optional)

```bash
cp memory/secrets.example.json memory/secrets.json
```

edit `memory/secrets.json`:

```json
{
  "YT_API_KEY": "AIza...",
  "PH_TOKEN": "your-product-hunt-token"
}
```

`secrets.json` is gitignored.

**without keys:** hackernews, reddit, tiktok creative center all work with zero auth. you still get solid coverage.

**with keys:**
- `YT_API_KEY`: enables the youtube data api v3 fetcher. get one at [console.cloud.google.com](https://console.cloud.google.com) under apis & services, youtube data api v3.
- `PH_TOKEN`: enables the product hunt fetcher. get one at [api.producthunt.com/v2/docs](https://api.producthunt.com/v2/docs).

you can also pass keys as environment variables. the skill checks `os.environ` before `secrets.json`.

### 7. install the skill in claude code

the easiest path is the [skills](https://github.com/vercel-labs/skills) cli, which copies the skill folder into place for you:

```bash
npx skills add codemathics/trend-radar -g -a claude-code
```

or from a clone, `python3 setup.py` does the same and also installs python deps.

to install by hand, copy the skill folder into your claude code skills directory:

```bash
cp -r skills/trend-radar ~/.claude/skills/trend-radar
```

the skill is then available in claude code. run `/trend-radar` - the first run finishes configuration (notion, niches, voice), and every run after that generates your daily briefs. you can also invoke it on a schedule (see below).

---

## running the skill

### daily scheduled run

the intended workflow is a 5:30am python fetch followed by a 6:00am claude brief.

**step 1: schedule the python fetchers** (cron or any scheduler):

```bash
# example cron entry, runs at 5:30am every day
# point it at the installed skill folder; the script resolves the data dir itself
30 5 * * * cd ~/.claude/skills/trend-radar && python3 scripts/run_all.py
```

**step 2: schedule the claude skill** using claude code's `/schedule` command or the built-in scheduled tasks feature. set it to run at 6:00am and invoke the trend-radar skill.

claude picks up the picks file from step 1, generates the briefs, and pushes to notion.

### on-demand

you can ask for briefs at any time inside a claude code session:

> "what's trending today?"

> "find me a trend on ai agents"

> "run trend radar for filmmaking only"

claude skips the schedule formatting, applies any topic constraint you give it, and still pushes to notion unless you tell it not to.

you can also re-run scoring without re-fetching (useful for testing niche config changes):

```bash
python3 scripts/run_all.py --score
```

---

## understanding the output

after a successful run, claude posts a briefing in chat:

```
trend radar, thursday, may 29

#1  cursor's agent mode is shipping real code now (score: 84, rising)
    platforms: hackernews, reddit - category: ai - time-to-stale: < 3 days
    hook: "stop prompting. cursor's agent is coding for you now."
    full brief in notion

#2  ...

#3  ...

skipped 12 other trends (mostly fading tech / politics filtered).
```

the full brief for each pick is in notion as a page. the table view has all properties filled. the page body reads top to bottom: hook, script, shot list, captions, hashtags, context, sources.

local archive files are saved to `briefings/YYYY-MM-DD.md` whether or not the notion write succeeds.

---

## scoring system

every trend candidate goes through this pipeline:

```
raw candidates
    - brand-safe filter (drop blocked topics)
    - cross-platform clustering (jaccard token similarity)
    - 5-dimension scoring
    - top 3 selection (with niche priority enforcement)
```

**scoring formula:**

```
final_score = (niche_fit      x 0.40)
            + (velocity       x 0.25)
            + (cross_platform x 0.15)
            + (recency        x 0.10)
            + (originality    x 0.10)
```

each dimension is 0-1 before weighting. the final score is multiplied by 100. only trends scoring >= 60 qualify as picks.

**niche fit** is computed by counting keyword hits in the trend's title and raw text, then multiplying by the niche's weight. a single ai-niche match outscores multiple matches in an unweighted niche.

**velocity** is approximated without time-series data:
- tiktok: rank movement in the creative center trending list
- reddit/hackernews: percentile of mention count within today's source batch
- youtube: percentile of view count within today's source batch

**cross-platform** gives a bonus for trends appearing on more than one source simultaneously. these tend to have broader longevity.

**recency** decays linearly over 7 days. content older than a week scores 0.

**originality** penalizes trends whose keywords overlap with anything you've already covered in the past 30 days (tracked in `cache/seen_trends.json`).

**selection:** the top 3 qualifying clusters are chosen. at least one slot is reserved for your highest-weighted niche when a qualifying trend exists in it. the remaining slots avoid duplicate categories unless there's no other option.

---

## hook rotation

the skill tracks which hook archetypes were used each day in `memory/used_hooks.json`. the rules:

- never use the same archetype 2 days in a row
- never use the same archetype 3 times in a 7-day window
- if a trend strongly fits one archetype (e.g., a breaking product launch fits bold claim), override rotation but log it

the 7 archetypes available, defined in `templates/hook_patterns.md`:

| archetype | best for |
|---|---|
| pattern interrupt | product design, ai, tech |
| bold claim / hot take | ai, tech, product design |
| question hook | how-to, ai, filmmaking |
| pov / cold open | lifestyle, filmmaking, how-to |
| stat shock | business, ai, tech |
| direct address / callout | product design, ai, how-to, filmmaking |
| demonstration / show-don't-tell | filmmaking, ai, product design |

every brief gets 3 variants from 3 different archetypes.

---

## file structure

the repo splits into shipped skill code and (at runtime) the user's own data dir.

**in the repo / installed skill folder** (`~/.claude/skills/trend-radar/` after install):

```
trend-radar/
├── README.md
├── setup.py                          # git-clone installer (deps + skills + data dir)
├── requirements.txt
├── .claude-plugin/
│   └── plugin.json                   # plugin manifest (skills + first-run hint)
└── skills/
    └── trend-radar/                  # the skill (installed by the cli)
        ├── SKILL.md                  # daily workflow + first-run setup routing
        ├── requirements.txt          # deps travel with the skill
        ├── references/
        │   └── setup_guide.md        # the guided onboarding flow (first run only)
        ├── scripts/
        │   ├── common.py             # shared utils + path resolution
        │   ├── run_all.py            # orchestrator: fetch then score
        │   ├── score_trends.py       # scoring + clustering engine
        │   ├── validate_setup.py     # pre-flight config check
        │   ├── fetch_*.py            # one per source (hn, reddit, tiktok, ...)
        │   └── push_to_notion.py     # notion write helpers
        ├── templates/
        │   ├── brief_template.md
        │   ├── hook_patterns.md
        │   └── script_structures.md
        └── memory/                   # SHIPPED DEFAULTS (read-only, replaced on update)
            ├── my_niches.json        # default niche config
            ├── voice_examples.md     # voice profile template
            ├── notion_config.example.json
            ├── secrets.example.json
            └── used_hooks.json
```

**user data dir** (`~/.claude/trend-radar/`, created on setup, never touched by updates):

```
~/.claude/trend-radar/
├── memory/
│   ├── my_niches.json                # your niches, weights, keywords, filters
│   ├── voice_examples.md             # your voice profile
│   ├── notion_config.json            # your notion workspace ids (private)
│   ├── secrets.json                  # api keys (private)
│   └── used_hooks.json               # last 14 days of hook archetype history
├── cache/                            # written by the fetchers
│   ├── raw_<source>_YYYYMMDD.json
│   ├── picks_YYYYMMDD.json           # the day's top 3 with scores
│   └── seen_trends.json              # 30-day dedup history
└── briefings/
    └── YYYY-MM-DD.md                 # daily brief archive
```

> when run from a clone (without installing into `~/.claude/skills/`), the data dir collapses back into the repo folder so everything stays in one place for development. set `TREND_RADAR_DATA` to override the data location explicitly.

---

## customization reference

### change your niche weights

in `memory/my_niches.json`, edit the `weight` field on any niche. a niche with weight 3.0 gets 3x the scoring bonus of a niche with weight 1.0. there is no enforced maximum, but weights above 4.0 will almost always force that niche into the top pick regardless of other signals.

### add a new niche

add a new object to the `niches` array in `memory/my_niches.json`:

```json
{
  "id": "gaming",
  "label": "gaming",
  "weight": 1.5,
  "keywords": ["gaming", "game dev", "unity", "unreal", "steam", "indie game"],
  "sources_priority": ["reddit_gaming", "youtube", "tiktok"],
  "subreddits": ["gamedev", "gaming", "indiegaming"]
}
```

the scoring engine picks it up on the next run with no code changes.

### change the scoring weights

in `memory/my_niches.json`, edit `scoring_weights`. they must sum to 1.0:

```json
"scoring_weights": {
  "niche_fit": 0.40,
  "velocity": 0.25,
  "cross_platform": 0.15,
  "recency": 0.10,
  "originality": 0.10
}
```

if velocity is most important to you (you only want fast-rising trends), bump it to 0.40 and trim `niche_fit` down.

### change the minimum score threshold

in `scripts/score_trends.py`, line 37:

```python
MIN_SCORE_FOR_PICK = 60
```

lower it to get more picks even from weaker signal days. raise it to only publish when you have strong trending content.

### change the dedup window

in `scripts/score_trends.py`, line 46:

```python
SEEN_TRENDS_WINDOW_DAYS = 30
```

lower it to allow revisiting trends sooner.

---

## adding a new data source

every fetcher in `scripts/` follows the same contract. to add a new source:

1. create `scripts/fetch_myplatform.py`
2. export a `fetch()` function that returns a list of dicts (or `TrendCandidate` objects) matching the normalized shape:

```python
from common import TrendCandidate, now_iso

def fetch() -> list[TrendCandidate]:
    items = []
    # your fetching logic goes here
    items.append(TrendCandidate(
        source="myplatform",
        platform="myplatform",
        title="trend title",
        url="https://...",
        raw_text="description or body text for keyword matching",
        mention_count=1234,     # views, upvotes, comments, anything comparable
        timestamp=now_iso(),
        extra={}                # any platform-specific fields
    ))
    return items
```

3. add it to the `fetchers` list in `scripts/run_all.py`:

```python
("myplatform", "fetch_myplatform"),
```

the scoring engine picks it up automatically. if your source needs an api key, read it with `env("MY_KEY")` from `common.py`. it checks `os.environ` then `memory/secrets.json`.

---

## failure modes

the skill is designed to degrade gracefully. these are the expected failure states and what happens:

| failure | behavior |
|---|---|
| a fetcher is blocked or rate-limited | logged as a warning, run continues with other sources |
| fewer than 3 trends score >= 60 | claude delivers what it has, flags the count in the briefing |
| claude in chrome unavailable (tier 2 escalation) | logged, skipped - tier 1 results are used |
| notion write fails | brief saved to `briefings/YYYY-MM-DD.md`, flagged as `[NOTION SYNC FAILED]` in chat |
| `voice_examples.md` is empty | claude falls back to `script_structures.md` defaults, flags it in the briefing |
| `notion_config.json` missing | claude skips the notion write, saves locally, reports the issue |

---

## credits

built by [@codemathics](https://github.com/codemathics) as a personal content workflow tool, open-sourced as a template for any creator who wants to automate their trend research and brief generation with claude code.
