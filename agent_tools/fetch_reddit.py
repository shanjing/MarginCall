








import html
import re
import requests
import time

from tools.cache.decorators import TTL_INTRADAY, cached
from tools.logging_utils import logger
from tools.truncate_for_llm import (
    get_tool_truncation_occurred,
    reset_tool_truncation_occurred,
    truncate_strings_for_llm,
)

from .tool_schemas import RedditPostsResult

# Reddit requires a descriptive User-Agent for API requests
USER_AGENT = "MarginCallAgent/1.0 (stock research; DiamondHands)"
DEFAULT_SUBREDDITS = ["wallstreetbets", "stocks"]
POSTS_PER_SUB = 3
# Only include posts created within this many days (Unix cutoff)
POST_MAX_AGE_DAYS = 14
# Snippet: max bytes so one post never blows up LLM context (e.g. 70K of \n)
SNIPPET_MAX_BYTES = 500
# Cap raw selftext before processing to avoid huge strings
SELFTEXT_MAX_CHARS = 10_000


def _snippet_from_selftext(selftext: str) -> str:
    """First 1-2 lines of post body, plain text, truncated by bytes. Sanitizes HTML and newlines."""
    if not selftext or not isinstance(selftext, str):
        return ""
    # Limit input size before any processing
    if len(selftext) > SELFTEXT_MAX_CHARS:
        selftext = selftext[:SELFTEXT_MAX_CHARS]
    # Decode HTML entities (e.g. &#x200B;) and collapse all whitespace to single space
    text = html.unescape(selftext)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    encoded = text.encode("utf-8")
    if len(encoded) <= SNIPPET_MAX_BYTES:
        return text
    # Truncate at byte boundary
    truncated = encoded[: SNIPPET_MAX_BYTES - 3].decode("utf-8", errors="ignore").rstrip()
    return truncated + "..."


def _mentions_ticker(text: str, ticker: str) -> bool:
    """True if ticker appears in text (case-insensitive)."""
    if not text or not ticker:
        return False
    return ticker.upper() in text.upper()


def _post_within_days(created_utc: int, max_age_days: int) -> bool:
    """True if post was created within the last max_age_days (created_utc is Unix seconds)."""
    if not created_utc:
        return False
    cutoff = int(time.time()) - (max_age_days * 24 * 60 * 60)
    return created_utc >= cutoff


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
        subreddits: Subreddit names without "r/" (default: wallstreetbets, stocks).
        limit_per_sub: Max posts per subreddit (default 3).
        real_time: If True, skip cache and fetch from Reddit (for user-requested fresh data).

    Returns:
        dict with status, ticker, posts (list of {subreddit, title, url, snippet}), and per_subreddit breakdown.
    """
    if subreddits is None:
        subreddits = DEFAULT_SUBREDDITS
    reset_tool_truncation_occurred()
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

            if not _post_within_days(post_data.get("created_utc", 0), POST_MAX_AGE_DAYS):
                continue

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
            
            # Enforce byte limits on title/url so they never blow up context
            title_enc = title.encode("utf-8")
            if len(title_enc) > SNIPPET_MAX_BYTES:
                title = title_enc[: SNIPPET_MAX_BYTES - 20].decode("utf-8", errors="ignore") + "..."
            url_enc = url_str.encode("utf-8")
            if len(url_enc) > 2000:
                url_str = url_enc[:1997].decode("utf-8", errors="ignore") + "..."

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
    out = RedditPostsResult(
        status="success",
        ticker=ticker_upper,
        posts=all_posts,
        by_subreddit=by_sub,
        subreddits_queried=[f"r/{s}" for s in subreddits],
        message=message,
    ).model_dump()
    result, any_truncated = truncate_strings_for_llm(out, tool_name="fetch_reddit")
    result["truncation_applied"] = get_tool_truncation_occurred() or any_truncated
    return result
