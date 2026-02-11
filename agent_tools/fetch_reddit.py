"""
Reddit posts about a stock from r/wallstreetbets, r/stocks, r/redditstock.

- Uses Reddit's public JSON API (no OAuth). Requires a descriptive User-Agent.
- Results are stored in the existing cache database (same as price, financials, etc.)
  with TTL_INTRADAY (4 hours). Real-time: pass real_time=True to skip cache and
  query Reddit; or use invalidate_cache(ticker) then run pipeline to refresh all data.
"""

import requests

from tools.cache.decorators import TTL_INTRADAY, cached
from tools.logging_utils import logger

from .tool_schemas import RedditPostsResult

# Reddit requires a descriptive User-Agent for API requests
USER_AGENT = "MarginCallAgent/1.0 (stock research; DiamondHands)"
DEFAULT_SUBREDDITS = ["wallstreetbets", "stocks", "redditstock"]
POSTS_PER_SUB = 3
# Snippet: max chars for 1-2 line excerpt of post body
SNIPPET_MAX_CHARS = 220


def _snippet_from_selftext(selftext: str) -> str:
    """First 1-2 lines of post body, plain text, truncated."""
    if not selftext or not isinstance(selftext, str):
        return ""
    # Normalize whitespace, take first 2 lines or first N chars
    text = " ".join(selftext.split())
    if len(text) <= SNIPPET_MAX_CHARS:
        return text.strip()
    return text[: SNIPPET_MAX_CHARS - 3].rstrip() + "..."


@cached(data_type="reddit", ttl_seconds=TTL_INTRADAY, ticker_param="ticker")
def fetch_reddit(
    ticker: str,
    subreddits: list[str] | None = None,
    limit_per_sub: int = POSTS_PER_SUB,
    real_time: bool = False,
) -> dict:
    """
    Fetch the top 3 most recent, actively engaged Reddit posts about a stock per subreddit.

    Uses sort=new so results are newest first; each post includes a 1-2 line excerpt (snippet).
    Results are cached in the shared cache DB with a 4-hour TTL. Use real_time=True
    to bypass cache and query Reddit (e.g. when user asks for fresh/live Reddit).

    Args:
        ticker: Stock symbol (e.g. "AAPL", "TSLA").
        subreddits: Subreddit names without "r/" (default: wallstreetbets, stocks, redditstock).
        limit_per_sub: Max posts per subreddit (default 3).
        real_time: If True, skip cache and fetch from Reddit (for user-requested fresh data).

    Returns:
        dict with status, ticker, posts (list of {subreddit, title, url, snippet}), and per_subreddit breakdown.
    """
    if subreddits is None:
        subreddits = DEFAULT_SUBREDDITS
    ticker_upper = ticker.upper()
    logger.info("--- Tool: fetch_reddit called for %s (subreddits: %s) ---", ticker_upper, subreddits)

    headers = {"User-Agent": USER_AGENT}
    all_posts: list[dict] = []
    by_sub: dict[str, list[dict]] = {}

    for sub in subreddits:
        # sort=new: most recent first. limit=3: top 3 per subreddit (recent, actively engaged)
        url = (
            "https://www.reddit.com/r/{sub}/search.json"
            "?q={ticker}&restrict_sr=on&sort=new&limit={limit}"
        ).format(sub=sub, ticker=ticker_upper, limit=max(3, min(10, limit_per_sub)))
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            logger.warning("Reddit fetch failed for r/%s: %s", sub, e)
            by_sub[f"r/{sub}"] = []
            continue
        except (ValueError, KeyError) as e:
            logger.warning("Reddit parse error for r/%s: %s", sub, e)
            by_sub[f"r/{sub}"] = []
            continue

        children = data.get("data", {}).get("children", [])
        # Top 3 most recent (sort=new already); take exactly 3
        sub_posts = []
        for child in children[:limit_per_sub]:
            post_data = child.get("data", {})
            title = post_data.get("title", "")
            permalink = post_data.get("permalink", "")
            if not permalink.startswith("/"):
                permalink = "/" + permalink
            url_str = f"https://www.reddit.com{permalink}" if permalink else ""
            if not title:
                continue
            selftext = post_data.get("selftext", "") or ""
            snippet = _snippet_from_selftext(selftext)
            entry = {
                "subreddit": f"r/{sub}",
                "title": title,
                "url": url_str,
                "snippet": snippet,
            }
            sub_posts.append(entry)
            all_posts.append(entry)
        by_sub[f"r/{sub}"] = sub_posts

    return RedditPostsResult(
        status="success",
        ticker=ticker_upper,
        posts=all_posts,
        by_subreddit=by_sub,
        subreddits_queried=[f"r/{s}" for s in subreddits],
    ).model_dump()
