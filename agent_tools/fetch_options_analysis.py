"""
Options analytics tool — Put/Call ratio, max pain, unusual activity, IV/HV.

Fetches the full options chain from yfinance for the nearest 3 expirations
and computes short-term volatility metrics in a single call.
"""

import logging
import math
from datetime import datetime

import numpy as np
import yfinance as yf
from tools.cache.decorators import TTL_INTRADAY, cached
from tools.truncate_for_llm import truncate_strings_for_llm

from .tool_schemas import OptionsAnalysisResult

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────
MAX_EXPIRATIONS = 3  # Only analyze nearest N expirations
UNUSUAL_VOLUME_THRESHOLD = 3  # Volume/OI ratio that flags unusual activity
TOP_UNUSUAL_CONTRACTS = 5  # Max unusual contracts to return
HV_WINDOW = 30  # Days for historical volatility calculation
TRADING_DAYS_YEAR = 252  # Annualization factor


def _compute_put_call_ratio(calls_df, puts_df) -> dict:
    """Compute put/call ratios by open interest and volume."""
    total_call_oi = int(calls_df["openInterest"].fillna(0).sum())
    total_put_oi = int(puts_df["openInterest"].fillna(0).sum())
    total_call_vol = int(calls_df["volume"].fillna(0).sum())
    total_put_vol = int(puts_df["volume"].fillna(0).sum())

    pcr_oi = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else None
    pcr_vol = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else None

    # Determine signal from volume ratio (more responsive than OI)
    ratio = pcr_vol if pcr_vol is not None else pcr_oi
    if ratio is None:
        signal = "NO_DATA"
    elif ratio < 0.7:
        signal = "BULLISH"
    elif ratio <= 1.0:
        signal = "NEUTRAL"
    elif ratio <= 1.3:
        signal = "CAUTIOUS"
    else:
        signal = "BEARISH"

    return {
        "pcr_open_interest": pcr_oi,
        "pcr_volume": pcr_vol,
        "signal": signal,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "total_call_volume": total_call_vol,
        "total_put_volume": total_put_vol,
    }


def _compute_max_pain(calls_df, puts_df, current_price: float) -> dict:
    """
    Max pain = strike where total loss for option *writers* is minimized.
    Equivalent to the strike where total *intrinsic value* of all outstanding
    options is lowest.
    """
    # Merge unique strikes from both sides
    all_strikes = sorted(
        set(calls_df["strike"].tolist()) | set(puts_df["strike"].tolist())
    )
    if not all_strikes:
        return {"strike": None, "current_price": current_price, "distance_pct": None}

    # Build OI lookup by strike
    call_oi = dict(zip(calls_df["strike"], calls_df["openInterest"].fillna(0)))
    put_oi = dict(zip(puts_df["strike"], puts_df["openInterest"].fillna(0)))

    min_pain = float("inf")
    max_pain_strike = all_strikes[0]

    for strike in all_strikes:
        # For each candidate settlement price (strike), compute total pain
        total_pain = 0.0
        for s in all_strikes:
            c_oi = call_oi.get(s, 0)
            p_oi = put_oi.get(s, 0)
            # Call writers lose when settlement > strike
            if strike > s:
                total_pain += c_oi * (strike - s)
            # Put writers lose when settlement < strike
            if strike < s:
                total_pain += p_oi * (s - strike)

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = strike

    distance_pct = (
        round((current_price - max_pain_strike) / max_pain_strike * 100, 2)
        if max_pain_strike
        else None
    )

    return {
        "strike": max_pain_strike,
        "current_price": round(current_price, 2),
        "distance_pct": distance_pct,
    }


def _detect_unusual_activity(calls_df, puts_df) -> dict:
    """Flag contracts where today's volume >> open interest."""
    unusual = []

    for side, df in [("call", calls_df), ("put", puts_df)]:
        for _, row in df.iterrows():
            vol = row.get("volume", 0) or 0
            oi = row.get("openInterest", 0) or 0
            if oi > 0 and vol / oi >= UNUSUAL_VOLUME_THRESHOLD and vol >= 100:
                unusual.append(
                    {
                        "strike": float(row["strike"]),
                        "expiry": str(row.get("expiry", "")),
                        "side": side,
                        "volume": int(vol),
                        "open_interest": int(oi),
                        "vol_oi_ratio": round(vol / oi, 1),
                    }
                )

    # Sort by ratio descending, take top N
    unusual.sort(key=lambda x: x["vol_oi_ratio"], reverse=True)
    top = unusual[:TOP_UNUSUAL_CONTRACTS]

    # Build summary
    if not top:
        summary = "No unusual options activity detected."
    else:
        call_count = sum(1 for c in top if c["side"] == "call")
        put_count = sum(1 for c in top if c["side"] == "put")
        max_ratio = top[0]["vol_oi_ratio"]
        summary = (
            f"{len(unusual)} contracts with {UNUSUAL_VOLUME_THRESHOLD}x+ volume/OI. "
            f"Top {len(top)}: {call_count} calls, {put_count} puts "
            f"(highest ratio: {max_ratio}x)."
        )

    return {
        "count": len(unusual),
        "top_contracts": top,
        "summary": summary,
    }


def _compute_iv_metrics(calls_df, puts_df, stock) -> dict:
    """
    Compute aggregate implied volatility and compare with historical volatility.
    IV = volume-weighted average of impliedVolatility from near-term chain.
    HV30 = 30-day historical volatility from stock price returns.
    IV Rank ≈ where current IV sits vs the 1-year HV range.
    """
    # ── Aggregate IV (volume-weighted) ──────────────────────────────────
    iv_data = []
    for df in [calls_df, puts_df]:
        if "impliedVolatility" in df.columns and "volume" in df.columns:
            valid = df[df["impliedVolatility"].notna() & (df["volume"].fillna(0) > 0)]
            for _, row in valid.iterrows():
                iv_data.append((row["impliedVolatility"], row["volume"] or 1))

    if iv_data:
        ivs, vols = zip(*iv_data)
        ivs = np.array(ivs)
        vols = np.array(vols, dtype=float)
        iv_mean = float(round(np.average(ivs, weights=vols) * 100, 2))
    else:
        iv_mean = None

    # ── Historical Volatility (30-day) ──────────────────────────────────
    try:
        hist = stock.history(period="1y", interval="1d")
        if hist is not None and len(hist) > HV_WINDOW:
            log_returns = np.log(hist["Close"] / hist["Close"].shift(1)).dropna()
            # Rolling 30-day HV, annualized
            rolling_hv = log_returns.rolling(window=HV_WINDOW).std() * math.sqrt(
                TRADING_DAYS_YEAR
            )
            rolling_hv = rolling_hv.dropna()
            hv30 = float(round(rolling_hv.iloc[-1] * 100, 2))

            # IV Rank approximation: where current IV sits vs HV range
            hv_min = float(rolling_hv.min() * 100)
            hv_max = float(rolling_hv.max() * 100)
            if iv_mean is not None and hv_max > hv_min:
                iv_rank = int(round((iv_mean - hv_min) / (hv_max - hv_min) * 100))
                iv_rank = max(0, min(100, iv_rank))  # Clamp 0-100
            else:
                iv_rank = None
        else:
            hv30 = None
            iv_rank = None
    except Exception as e:
        logger.warning("Could not compute HV30: %s", e)
        hv30 = None
        iv_rank = None

    # ── IV vs HV comparison ─────────────────────────────────────────────
    if iv_mean is not None and hv30 is not None:
        diff = iv_mean - hv30
        if diff > 5:
            iv_vs_hv = "OVERPRICED"
        elif diff < -5:
            iv_vs_hv = "UNDERPRICED"
        else:
            iv_vs_hv = "FAIR"
        interpretation = f"IV ({iv_mean:.1f}%) vs HV30 ({hv30:.1f}%) — options are {iv_vs_hv.lower()}"
    else:
        iv_vs_hv = "UNKNOWN"
        interpretation = "Insufficient data to compare IV vs HV."

    return {
        "iv_mean": iv_mean,
        "hv30": hv30,
        "iv_rank": iv_rank,
        "iv_vs_hv": iv_vs_hv,
        "interpretation": interpretation,
    }


@cached(data_type="options_analysis", ttl_seconds=TTL_INTRADAY, ticker_param="ticker")
def fetch_options_analysis(ticker: str) -> dict:
    """
    Fetch comprehensive options analytics for a stock ticker.

    Computes: put/call ratio, max pain, unusual activity, IV, HV30, IV rank.
    Analyzes the nearest 3 expiration dates for relevance.

    Args:
        ticker: Stock symbol (e.g., "AAPL", "TSLA").

    Returns:
        dict with put_call_ratio, max_pain, unusual_activity, implied_volatility,
        and an overall interpretation.
    """
    logger.info("--- Tool: fetch_options_analysis called for %s ---", ticker)

    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options

        if not expirations:
            return {
                "status": "error",
                "ticker": ticker.upper(),
                "error_message": f"No options data available for {ticker.upper()}",
            }

        # Use nearest N expirations
        near_expirations = list(expirations[:MAX_EXPIRATIONS])
        logger.info(
            "Analyzing %d expirations: %s", len(near_expirations), near_expirations
        )

        # Collect all calls and puts across expirations
        all_calls = []
        all_puts = []

        for expiry in near_expirations:
            try:
                chain = stock.option_chain(expiry)
                calls = chain.calls.copy()
                puts = chain.puts.copy()
                calls["expiry"] = expiry
                puts["expiry"] = expiry
                all_calls.append(calls)
                all_puts.append(puts)
            except Exception as e:
                logger.warning(
                    "Failed to fetch chain for %s expiry %s: %s", ticker, expiry, e
                )
                continue

        if not all_calls or not all_puts:
            return {
                "status": "error",
                "ticker": ticker.upper(),
                "error_message": f"Could not fetch options chains for {ticker.upper()}",
            }

        import pandas as pd

        calls_df = pd.concat(all_calls, ignore_index=True)
        puts_df = pd.concat(all_puts, ignore_index=True)

        # Get current price for max pain calculation
        info = stock.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)

        # ── Compute all metrics ─────────────────────────────────────────
        pcr = _compute_put_call_ratio(calls_df, puts_df)
        max_pain = _compute_max_pain(calls_df, puts_df, current_price)
        unusual = _detect_unusual_activity(calls_df, puts_df)
        iv_metrics = _compute_iv_metrics(calls_df, puts_df, stock)

        # ── Build interpretation summary ────────────────────────────────
        parts = []
        if pcr["pcr_volume"] is not None:
            parts.append(f"PCR(Vol)={pcr['pcr_volume']} ({pcr['signal'].lower()})")
        if max_pain["strike"] is not None:
            parts.append(f"Max pain ${max_pain['strike']}")
        if iv_metrics["iv_mean"] is not None:
            parts.append(f"IV {iv_metrics['iv_mean']:.1f}%")
        if iv_metrics["iv_vs_hv"] != "UNKNOWN":
            parts.append(f"options {iv_metrics['iv_vs_hv'].lower()}")
        if unusual["count"] > 0:
            parts.append(f"{unusual['count']} unusual contracts")
        interpretation = (
            ". ".join(parts) + "." if parts else "Insufficient options data."
        )

        out = OptionsAnalysisResult(
            ticker=ticker.upper(),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            expirations_analyzed=near_expirations,
            put_call_ratio=pcr,
            max_pain=max_pain,
            unusual_activity=unusual,
            implied_volatility=iv_metrics,
            interpretation=interpretation,
        ).model_dump()
        result, _ = truncate_strings_for_llm(out, tool_name="fetch_options_analysis")
        return result

    except Exception as e:
        logger.exception("Error in fetch_options_analysis for %s", ticker)
        return {
            "status": "error",
            "ticker": ticker.upper(),
            "error_message": str(e),
        }
