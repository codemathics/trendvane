"""Reddit fetcher.

Reddit deprecated unauthenticated access to the public `.json` endpoints — they
now return HTTP 403 for non-OAuth clients regardless of user-agent. This fetcher
uses Reddit's free application-only OAuth (client-credentials grant) instead.

To enable it:
  1. Create a free "script" app at https://www.reddit.com/prefs/apps
     (type: script; redirect uri: http://localhost — it isn't used).
  2. Add the id + secret to memory/secrets.json:
       "REDDIT_CLIENT_ID": "...",
       "REDDIT_CLIENT_SECRET": "..."

With no credentials present the fetcher skips quietly and the daily run
continues on the other sources. With credentials it pulls /r/{sub}/hot for
every subreddit in my_niches.json, filtered to score >= MIN_SCORE.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from common import TrendCandidate, dump_candidates, env, get_logger, load_niches

log = get_logger("reddit")

# Reddit requires a unique, descriptive User-Agent. Generic / library UAs get
# rate-limited or 403'd hard.
USER_AGENT = "python:trend-radar:0.2 (by /u/trend-radar)"
MIN_SCORE = 200
LIMIT_PER_SUB = 25

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_BASE = "https://oauth.reddit.com"


def _get_token() -> str | None:
    """Fetch an application-only OAuth token via the client-credentials grant.

    Returns None if no credentials are configured or the handshake fails, so the
    caller can skip Reddit gracefully.
    """
    client_id = env("REDDIT_CLIENT_ID")
    client_secret = env("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {auth}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8")).get("access_token")
    except Exception as e:
        log.warning(f"reddit oauth handshake failed: {e}")
        return None


def _fetch_sub(sub: str, token: str) -> list[dict]:
    url = f"{OAUTH_BASE}/r/{sub}/hot?limit={LIMIT_PER_SUB}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"bearer {token}", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            return [child["data"] for child in data.get("data", {}).get("children", [])]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            log.warning(f"r/{sub}: rate limited, backing off")
            time.sleep(5)
        else:
            log.warning(f"r/{sub}: HTTP {e.code}")
        return []
    except Exception as e:
        log.warning(f"r/{sub}: {e}")
        return []


def fetch() -> list[TrendCandidate]:
    token = _get_token()
    if not token:
        log.info(
            "reddit skipped — set REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in "
            "secrets.json to enable (free script app at reddit.com/prefs/apps)"
        )
        return []

    niches = load_niches()
    subs: set[str] = set()
    for niche in niches.get("niches", []):
        subs.update(niche.get("subreddits", []))

    candidates: list[TrendCandidate] = []
    for sub in sorted(subs):
        posts = _fetch_sub(sub, token)
        time.sleep(1.0)  # stay well under Reddit's 60 req/min OAuth limit
        for p in posts:
            score = p.get("score", 0)
            if score < MIN_SCORE:
                continue
            if p.get("stickied") or p.get("over_18"):
                continue
            ts = datetime.fromtimestamp(
                p.get("created_utc", 0), tz=timezone.utc
            ).isoformat()
            permalink = "https://reddit.com" + p.get("permalink", "")
            candidates.append(
                TrendCandidate(
                    source="reddit",
                    platform="Reddit",
                    title=p.get("title", "").strip(),
                    url=p.get("url_overridden_by_dest") or permalink,
                    raw_text=(p.get("title", "") + "\n\n" + (p.get("selftext") or "")).strip(),
                    mention_count=score,
                    timestamp=ts,
                    extra={
                        "subreddit": sub,
                        "permalink": permalink,
                        "comments": p.get("num_comments", 0),
                        "upvote_ratio": p.get("upvote_ratio"),
                    },
                )
            )

    log.info(f"fetched {len(candidates)} posts across {len(subs)} subs (score >= {MIN_SCORE})")
    return candidates


if __name__ == "__main__":
    items = fetch()
    p = dump_candidates("reddit", items)
    print(f"wrote {len(items)} candidates to {p}")
