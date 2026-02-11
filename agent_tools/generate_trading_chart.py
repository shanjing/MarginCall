"""Generate TradingView-style interactive chart (OHLC, volume, RSI, MACD, SMAs) for a stock."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import yfinance as yf

from tools.logging_utils import logger

try:
    import pandas_ta as ta
except ImportError:
    try:
        import pandas_ta_classic as ta  # fork with same .ta accessor
    except ImportError:
        ta = None

try:
    from google.adk.tools import ToolContext
    from google.genai import types
except ImportError:
    ToolContext = None
    types = None


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns to single level (yfinance multi-ticker case)."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


async def generate_trading_chart(
    ticker: str,
    timeframe: str = "1y",
    tool_context: ToolContext | None = None,
) -> str:
    """
    Fetch chart data for a stock and generate a TradingView-style interactive Plotly chart.

    Produces candlesticks, volume, SMAs (50, 200), RSI, and MACD. Saves the chart as an
    HTML artifact when run via ADK (tool_context provided).

    Args:
        ticker: Stock symbol (e.g. 'AAPL').
        timeframe: Period of data (e.g. '3mo', '1y', '2y'). Used as yfinance 'period'.
        All charts use daily bars (interval='1d').
        tool_context: ADK ToolContext; when provided, saves the chart as an artifact.

    Returns:
        Status message including artifact filename when saved.
    """
    logger.info(
        "--- Tool: generate_trading_chart called for %s, period=%s ---",
        ticker,
        timeframe,
    )

    if ta is None:
        return (
            "Chart generation requires pandas_ta. "
            "Install with: pip install pandas-ta-classic"
        )

    try:
        stock = yf.Ticker(ticker)
        # Explicit daily bars (1d); do not use weekly for any timeframe
        hist = stock.history(period=timeframe, interval="1d")
        hist = _flatten_columns(hist)

        if hist is None or hist.empty or len(hist) < 20:
            return (
                f"Insufficient history for {ticker} (need at least 20 trading days). "
                f"Try a longer timeframe (e.g. '3mo', '1y')."
            )

        df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"volume": "Volume"})

        # Indicators (pandas_ta appends columns)
        # Use SMA_20 for short timeframes, SMA_50/200 for longer ones
        num_days = len(df)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.sma(length=20, append=True)
        if num_days >= 60:
            df.ta.sma(length=50, append=True)
        if num_days >= 210:
            df.ta.sma(length=200, append=True)

        # Column names
        rsi_col = "RSI_14"
        macd_line = "MACD_12_26_9"
        macd_signal = "MACDs_12_26_9"
        macd_hist = "MACDh_12_26_9"
        sma_20_col = "SMA_20"
        sma_50_col = "SMA_50" if "SMA_50" in df.columns else None
        sma_200_col = "SMA_200" if "SMA_200" in df.columns else None

        # Only require RSI for warmup (14 days) — SMAs/MACD render
        # partial lines where available, Plotly skips NaN gracefully
        plot_df = df.dropna(subset=[rsi_col]).copy()

        if plot_df.empty:
            return (
                f"Not enough data to compute indicators for {ticker}. "
                f"Use a longer timeframe (e.g. '1y' or '2y')."
            )

        # TradingView-style layout: Price (+ SMAs) | Volume | RSI | MACD
        fig = make_subplots(
            rows=4,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.50, 0.12, 0.19, 0.19],
            subplot_titles=(
                f"{ticker} – Price ({timeframe})",
                "Volume",
                "RSI (14)",
                "MACD (12, 26, 9)",
            ),
        )

        # Row 1: Candlesticks + SMAs (adaptive to timeframe)
        fig.add_trace(
            go.Candlestick(
                x=plot_df.index,
                open=plot_df["open"],
                high=plot_df["high"],
                low=plot_df["low"],
                close=plot_df["close"],
                name="Price",
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
            ),
            row=1,
            col=1,
        )
        # SMA 20 (always available, 20-day warmup)
        fig.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df[sma_20_col],
                name="SMA 20",
                line=dict(color="#42a5f5", width=1.5),
            ),
            row=1,
            col=1,
        )
        # SMA 50 (available when >= 60 days of data)
        if (
            sma_50_col
            and sma_50_col in plot_df.columns
            and plot_df[sma_50_col].notna().any()
        ):
            fig.add_trace(
                go.Scatter(
                    x=plot_df.index,
                    y=plot_df[sma_50_col],
                    name="SMA 50",
                    line=dict(color="#ff9800", width=1.5),
                ),
                row=1,
                col=1,
            )
        # SMA 200 (available when >= 210 days of data)
        if (
            sma_200_col
            and sma_200_col in plot_df.columns
            and plot_df[sma_200_col].notna().any()
        ):
            fig.add_trace(
                go.Scatter(
                    x=plot_df.index,
                    y=plot_df[sma_200_col],
                    name="SMA 200",
                    line=dict(color="#9c27b0", width=1.5),
                ),
                row=1,
                col=1,
            )

        # Row 2: Volume
        colors = [
            "#26a69a" if c >= o else "#ef5350"
            for o, c in zip(plot_df["open"], plot_df["close"])
        ]
        fig.add_trace(
            go.Bar(
                x=plot_df.index,
                y=plot_df["Volume"],
                name="Volume",
                marker_color=colors,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        # Row 3: RSI
        fig.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df[rsi_col],
                name="RSI",
                line=dict(color="#7e57c2", width=1.5),
            ),
            row=3,
            col=1,
        )
        fig.add_hline(
            y=70, line_dash="dot", line_color="rgba(255,152,0,0.6)", row=3, col=1
        )
        fig.add_hline(
            y=30, line_dash="dot", line_color="rgba(255,152,0,0.6)", row=3, col=1
        )

        # Row 4: MACD line, signal, histogram
        fig.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df[macd_line],
                name="MACD",
                line=dict(color="#2196f3", width=1.5),
            ),
            row=4,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df[macd_signal],
                name="Signal",
                line=dict(color="#ff9800", width=1),
            ),
            row=4,
            col=1,
        )
        hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in plot_df[macd_hist]]
        fig.add_trace(
            go.Bar(
                x=plot_df.index,
                y=plot_df[macd_hist],
                name="Histogram",
                marker_color=hist_colors,
                showlegend=False,
            ),
            row=4,
            col=1,
        )

        fig.update_layout(
            template="plotly_dark",
            height=900,
            title=dict(
                text=f"{ticker} – Technical Analysis ({timeframe})",
                x=0.5,
                xanchor="center",
            ),
            xaxis_rangeslider_visible=False,
            font=dict(size=11),
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
        fig.update_yaxes(range=[0, 100], row=3, col=1)

        html_filename = f"{ticker}_chart_{timeframe}.html"
        png_filename = f"{ticker}_chart_{timeframe}.png"
        chart_html = fig.to_html(include_plotlyjs="cdn", full_html=True)

        # Disk fallback dir: only used when artifact service is unavailable (e.g. CLI).
        # When running in UI, ADK stores artifacts via save_artifact() in its artifact area.
        _margin_call_dir = Path(__file__).resolve().parent.parent
        _chart_dir = _margin_call_dir / ".tmp"
        _chart_dir.mkdir(parents=True, exist_ok=True)

        # if tool_context is provided, save the chart as an artifact
        if (
            tool_context is not None
            and getattr(tool_context, "save_artifact", None)
            and types is not None
        ):
            logger.info("Saving chart as artifact: %s", html_filename)
            # .save_artifact is a function provided by the tool_context
            save_artifact = tool_context.save_artifact
            # ADK expects (filename, Part) with Part.inline_data = Blob(mime_type, data=bytes)
            html_part = types.Part(
                inline_data=types.Blob(
                    mime_type="text/html", data=chart_html.encode("utf-8")
                ),
            )
            try:
                await save_artifact(html_filename, html_part)
            except ValueError as e:
                if "Artifact service is not initialized" in str(e):
                    html_path = _chart_dir / html_filename
                    html_path.write_text(chart_html, encoding="utf-8")
                    logger.info(
                        "Artifact service isn't running (likely running from CLI); "
                        "chart HTML is stored at %s",
                        html_path.resolve(),
                    )
                    return (
                        f"TradingView-style chart saved to **{html_filename}** in .tmp. "
                        f"Full path: {html_path.resolve()}"
                    )
                raise

            # Save PNG for inline display in ADK UI
            try:
                png_bytes = fig.to_image(format="png", width=1200, height=900, scale=2)
                png_part = types.Part(
                    inline_data=types.Blob(mime_type="image/png", data=png_bytes),
                )
                await save_artifact(png_filename, png_part)
                return (
                    f"TradingView-style chart generated for {ticker}.\n"
                    f"- **Inline image**: {png_filename}\n"
                    f"- **Interactive chart**: {html_filename} (in Artifacts panel)"
                )
            except Exception as img_err:
                logger.warning("Could not generate PNG (install kaleido): %s", img_err)
                return (
                    f"TradingView-style chart generated. View artifact: **{html_filename}**\n"
                    f"(PNG export failed - install `kaleido` for inline images)"
                )

        # Fallback: write to .tmp when not run via ADK (no tool_context / CLI)
        html_path = _chart_dir / html_filename
        html_path.write_text(chart_html, encoding="utf-8")
        return (
            f"TradingView-style chart saved to **{html_filename}** in .tmp. "
            f"Full path: {html_path.resolve()}"
        )

    except Exception as e:
        logger.exception("Error generating chart for %s", ticker)
        return f"Error generating chart for {ticker}: {e!s}"
