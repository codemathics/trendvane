"""TikTok Creative Center fetcher.

TikTok's Creative Center trending endpoints used to be callable unsigned, but
they are now permission-gated: the hashtag endpoint returns code 40101
("no permission") and the sounds path 404s for unsigned requests. Matching
TikTok's request signing is a moving target that breaks frequently, so this
fetcher probes the API once and, when it's gated, returns [] and lets the
skill's Tier-2 browser fallback (Claude in Chrome on Creative Center) handle
TikTok trends. If TikTok ever opens the API back up, the probe passes and the
normal path below resumes with no code change.

When the API is available it pulls, scoped to the regions in my_niches.json:
- Trending hashtags (top 50)
- Trending sounds (top 50)
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from common import TrendCandidate, dump_candidates, get_logger, load_niches

log = get_logger("tiktok")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_REGIONS = ["US", "GB", "CA", "AU"]
HASHTAG_URL = (
    "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
)
SOUND_URL = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/song/list"
VIDEO_URL = "https://ads.tiktok.com/creative_radar_api/v1/top_ads/v2/list"


def _get(url: str, params: dict) -> dict | None:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        # Kept at debug: fetch() emits one clear line when the API is gated, so
        # we don't want a warning per region/endpoint cluttering the run log.
        log.debug(f"TikTok API call failed: {url} — {e}")
        return None


def _fetch_hashtags(region: str) -> list[TrendCandidate]:
    data = _get(
        HASHTAG_URL,
        {
            "page": 1,
            "limit": 50,
            "period": 7,
            "country_code": region,
            "sort_by": "popular",
        },
    )
    if not data or data.get("code") != 0:
        return []
    out: list[TrendCandidate] = []
    for it in (data.get("data") or {}).get("list") or []:
        name = it.get("hashtag_name") or it.get("name")
        if not name:
            continue
        out.append(
            TrendCandidate(
                source="tiktok",
                platform="TikTok",
                title=f"#{name}",
                url=f"https://www.tiktok.com/tag/{name}",
                raw_text=name,
                mention_count=int(it.get("publish_cnt") or it.get("video_cnt") or 0),
                timestamp=datetime.now(timezone.utc).isoformat(),
                extra={
                    "kind": "hashtag",
                    "region": region,
                    "rank": it.get("rank"),
                    "rank_diff": it.get("rank_diff"),
                    "trend_type": it.get("trend_type"),
                },
            )
        )
    return out


def _fetch_sounds(region: str) -> list[TrendCandidate]:
    data = _get(
        SOUND_URL,
        {
            "page": 1,
            "limit": 50,
            "period": 7,
            "country_code": region,
            "rank_type": "popular",
        },
    )
    if not data or data.get("code") != 0:
        return []
    out: list[TrendCandidate] = []
    for it in (data.get("data") or {}).get("list") or []:
        title = it.get("title") or it.get("song_name")
        author = it.get("author")
        if not title:
            continue
        clip_id = it.get("clip_id") or it.get("song_id")
        url = (
            f"https://www.tiktok.com/music/{title.replace(' ', '-')}-{clip_id}"
            if clip_id
            else "https://www.tiktok.com/music/"
        )
        out.append(
            TrendCandidate(
                source="tiktok",
                platform="TikTok",
                title=f"🎵 {title}" + (f" - {author}" if author else ""),
                url=url,
                raw_text=title,
                mention_count=int(it.get("publish_cnt") or it.get("user_cnt") or 0),
                timestamp=datetime.now(timezone.utc).isoformat(),
                extra={
                    "kind": "sound",
                    "region": region,
                    "clip_id": clip_id,
                    "author": author,
                    "duration": it.get("duration"),
                    "rank": it.get("rank"),
                    "rank_diff": it.get("rank_diff"),
                },
            )
        )
    return out


def _api_available(region: str) -> bool:
    """Probe the Creative Center API once.

    TikTok now permission-gates these endpoints for unsigned requests (the
    hashtag endpoint returns code 40101 "no permission" and the sounds path
    404s). Replicating TikTok's request signing is a moving target that breaks
    often, so rather than fail per-region we probe once and, when the API isn't
    serving us, defer TikTok trends to the Tier-2 browser fallback (the skill
    loads Creative Center in a real browser session when fewer than 3 trends
    qualify). If TikTok ever un-gates the API, this probe passes and the normal
    path resumes with no code change.
    """
    data = _get(
        HASHTAG_URL,
        {"page": 1, "limit": 1, "period": 7, "country_code": region, "sort_by": "popular"},
    )
    return bool(data) and data.get("code") == 0


def fetch() -> list[TrendCandidate]:
    cfg = load_niches()
    region_cfg = cfg.get("region", {})
    primary = region_cfg.get("primary", "US")
    secondary = region_cfg.get("secondary", ["GB", "CA", "AU"])
    regions = [primary] + [r for r in secondary if r != primary] if primary else DEFAULT_REGIONS

    if not _api_available(regions[0]):
        log.info(
            "TikTok Creative Center API is gated for unsigned requests; "
            "deferring TikTok trends to the browser fallback (Tier 2)"
        )
        return []

    all_items: list[TrendCandidate] = []
    for region in regions:
        all_items.extend(_fetch_hashtags(region))
        all_items.extend(_fetch_sounds(region))

    # Dedup by (kind, title) keeping max mention_count.
    by_key: dict[tuple[str, str], TrendCandidate] = {}
    for c in all_items:
        key = (c.extra.get("kind", ""), c.title)
        if key not in by_key or (c.mention_count or 0) > (by_key[key].mention_count or 0):
            by_key[key] = c

    out = list(by_key.values())
    log.info(f"fetched {len(out)} unique TikTok signals (hashtags + sounds)")
    return out


if __name__ == "__main__":
    items = fetch()
    p = dump_candidates("tiktok", items)
    print(f"wrote {len(items)} candidates to {p}")
