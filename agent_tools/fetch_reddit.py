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
    text = " ".join(selftext.split())
    if len(text) <= SNIPPET_MAX_CHARS:
        return text.strip()
    return text[: SNIPPET_MAX_CHARS - 3].rstrip() + "..."


def _mentions_ticker(text: str, ticker: str) -> bool:
    """True if ticker appears in text (case-insensitive)."""
    if not text or not ticker:
        return False
    return ticker.upper() in text.upper()


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
    by_sub: dict[str, list[dict]] = {f"r/{s}": [] for s in subreddits}

    for sub in subreddits:
        # search for ticker in subreddit; sort=relevance so results match the ticker
        url = (
            "https://www.reddit.com/r/{sub}/search.json"
            "?q={ticker}&restrict_sr=on&sort=relevance&limit={limit}"
        ).format(sub=sub, ticker=ticker_upper, limit=max(5, min(15, limit_per_sub * 5)))
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
        sub_posts = []
        for child in children:
            if len(sub_posts) >= limit_per_sub:
                break
            post_data = child.get("data", {})
            title = post_data.get("title", "")
            selftext = post_data.get("selftext", "") or ""
            # Only include posts that mention the ticker in title or body
            if not _mentions_ticker(title, ticker_upper) and not _mentions_ticker(selftext, ticker_upper):
                continue
            permalink = post_data.get("permalink", "")
            if not permalink.startswith("/"):
                permalink = "/" + permalink
            url_str = f"https://www.reddit.com{permalink}" if permalink else ""
            if not title:
                continue
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

    message = "Reddit isn't showing this much love." if not all_posts else None
    return RedditPostsResult(
        status="success",
        ticker=ticker_upper,
        posts=all_posts,
        by_subreddit=by_sub,
        subreddits_queried=[f"r/{s}" for s in subreddits],
        message=message,
    ).model_dump()
