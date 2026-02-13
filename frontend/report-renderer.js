/* ── StockReport Card Renderer ────────────────────────────────── */
"use strict";

/**
 * Render a StockReport JSON object into a DOM element (dashboard card).
 * Called from app.js after detecting stock_report in session state.
 *
 * @param {Object} r - StockReport object matching agent_tools/schemas.py
 * @returns {HTMLElement}
 */
function renderStockReport(r) {
  const card = el("div", "report-card");

  // ── Header + Rating ───────────────────────────────────────────
  const header = el("div", "report-header");

  const left = el("div");
  left.appendChild(elText("div", r.title || "Stock Ticker", "title"));
  left.appendChild(elText("div",
    `${r.date || ""}  |  ${r.analyst || ""}  |  ${r.firm || ""}`, "meta"));
  header.appendChild(left);

  if (r.rating) {
    const rec = (r.rating.recommendation || "").toLowerCase();
    const badge = el("div", `rating-badge rating-${rec}`);
    badge.appendChild(elText("span", r.rating.recommendation || ""));
    badge.appendChild(elText("span",
      `${r.rating.confidence_percent ?? "?"}% confidence`, "confidence"));
    header.appendChild(badge);
  }
  card.appendChild(header);

  // ── Company ───────────────────────────────────────────────────
  if (r.company_intro) card.appendChild(section("Company", r.company_intro));

  // ── Price ─────────────────────────────────────────────────────
  if (r.price_summary) card.appendChild(section("Price", r.price_summary));

  // ── Financials ────────────────────────────────────────────────
  const finSec = el("div", "report-section");
  finSec.appendChild(elText("h3", "Financials"));
  if (r.financials_summary) finSec.appendChild(elText("p", r.financials_summary));

  if (r.financials) {
    const grid = el("div", "financials-grid");
    const f = r.financials;
    const items = [
      ["P/E (Trailing)", fmtNum(f.trailing_pe)],
      ["P/E (Forward)",  fmtNum(f.forward_pe)],
      ["Revenue (TTM)",  fmtMoney(f.total_revenue)],
      ["Net Income",     fmtMoney(f.net_income)],
      ["Free Cash Flow", fmtMoney(f.free_cash_flow)],
      ["Op. Cash Flow",  fmtMoney(f.operating_cash_flow)],
      ["Market Cap",     fmtMoney(f.market_cap)],
    ];
    if (f.latest_quarter_end) {
      items.push(["Latest Qtr (" + f.latest_quarter_end + ")", ""]);
      items.push(["Qtr Revenue",    fmtMoney(f.latest_quarter_revenue)]);
      items.push(["Qtr Net Income", fmtMoney(f.latest_quarter_net_income)]);
    }
    for (const [label, value] of items) {
      if (!value && value !== 0) continue;
      const item = el("div", "fin-item");
      item.appendChild(elText("span", label, "label"));
      item.appendChild(elText("span", value, "value"));
      grid.appendChild(item);
    }
    finSec.appendChild(grid);
  }
  card.appendChild(finSec);

  // ── Technicals ────────────────────────────────────────────────
  if (r.technicals_summary) card.appendChild(section("Technicals", r.technicals_summary));

  // ── Charts (inline images from session state) ──────────────────
  if (r.chart_images && Object.keys(r.chart_images).length > 0) {
    const chartSec = el("div", "report-section charts-section");
    chartSec.appendChild(elText("h3", "Charts"));
    const grid = el("div", "charts-grid");
    const order = ["1y", "3mo"];
    for (const key of order) {
      const item = r.chart_images[key];
      if (!item || !item.src) continue;
      const wrap = el("div", "chart-item");
      wrap.appendChild(elText("div", item.label || key, "chart-label"));
      const img = document.createElement("img");
      img.src = item.src;
      img.alt = item.label || "Chart";
      img.loading = "lazy";
      wrap.appendChild(img);
      grid.appendChild(wrap);
    }
    if (grid.children.length) {
      chartSec.appendChild(grid);
      card.appendChild(chartSec);
    }
  }

  // ── Sentiment ─────────────────────────────────────────────────
  if (r.sentiment) {
    const sec = el("div", "report-section");
    sec.appendChild(elText("h3", "Market Sentiment"));
    if (r.sentiment.sentiment_summary) {
      sec.appendChild(elText("p", r.sentiment.sentiment_summary));
    }

    const grid = el("div", "sentiment-grid");
    const s = r.sentiment;

    grid.appendChild(sentimentItem("CNN Fear & Greed",
      s.cnn_fear_greed_score, s.cnn_fear_greed_rating));
    grid.appendChild(sentimentItem("VIX",
      fmtNum(s.vix_value), s.vix_signal));
    grid.appendChild(sentimentItem("StockTwits",
      fmtNum(s.stocktwits_ratio), s.stocktwits_signal));
    grid.appendChild(sentimentItem("Put/Call Ratio",
      fmtNum(s.pcr_volume), s.pcr_signal));

    const overall = el("div", "sentiment-overall " + signalClass(s.overall_market_sentiment));
    overall.textContent = "Overall: " + (s.overall_market_sentiment || "N/A");
    grid.appendChild(overall);

    sec.appendChild(grid);
    card.appendChild(sec);
  }

  // ── Options Analysis ──────────────────────────────────────────
  if (r.options_analysis) {
    const sec = el("div", "report-section");
    sec.appendChild(elText("h3", "Options (Short-term Volatility)"));

    const grid = el("div", "options-grid");
    const o = r.options_analysis;

    grid.appendChild(optionItem("PCR (Volume)",   fmtNum(o.pcr_volume)));
    grid.appendChild(optionItem("PCR (OI)",       fmtNum(o.pcr_open_interest)));
    grid.appendChild(optionItem("PCR Signal",     o.pcr_signal || "N/A"));
    grid.appendChild(optionItem("Max Pain",       "$" + fmtNum(o.max_pain_strike)));
    grid.appendChild(optionItem("Distance %",     fmtNum(o.max_pain_distance_pct) + "%"));
    grid.appendChild(optionItem("IV Mean",        fmtNum(o.iv_mean) + "%"));
    grid.appendChild(optionItem("HV30",           fmtNum(o.hv30) + "%"));
    grid.appendChild(optionItem("IV Rank",        fmtNum(o.iv_rank)));
    grid.appendChild(optionItem("IV vs HV",       o.iv_vs_hv || "N/A"));
    grid.appendChild(optionItem("Unusual Trades", String(o.unusual_activity_count ?? 0)));

    if (o.unusual_activity_summary) {
      grid.appendChild(elText("div", o.unusual_activity_summary, "options-summary"));
    }
    if (o.options_summary) {
      grid.appendChild(elText("div", o.options_summary, "options-summary"));
    }

    sec.appendChild(grid);
    card.appendChild(sec);
  }

  // ── News ──────────────────────────────────────────────────────
  if (r.news_articles && r.news_articles.length) {
    const sec = el("div", "report-section");
    sec.appendChild(elText("h3", "News"));
    if (r.news_summary) sec.appendChild(elText("p", r.news_summary));

    const list = el("ul", "article-list");
    for (const a of r.news_articles) {
      const li = el("li");
      const link = document.createElement("a");
      link.className = "article-title";
      link.href = a.url || "#";
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = a.title || "Untitled";
      li.appendChild(link);
      if (a.date) li.appendChild(elText("div", a.date, "article-meta"));
      if (a.snippet) li.appendChild(elText("div", a.snippet, "article-snippet"));
      list.appendChild(li);
    }
    sec.appendChild(list);
    card.appendChild(sec);
  }

  // ── Reddit ────────────────────────────────────────────────────
  const hasRedditPosts = r.reddit_posts && r.reddit_posts.length;
  const redditNote = r.reddit_note && r.reddit_note.trim();
  if (hasRedditPosts || redditNote) {
    const sec = el("div", "report-section");
    sec.appendChild(elText("h3", "Reddit"));
    if (hasRedditPosts) {
      const list = el("ul", "reddit-list");
      for (const p of r.reddit_posts) {
        const li = el("li");
        if (p.subreddit) {
          li.appendChild(elText("span", p.subreddit, "subreddit-badge"));
        }
        const link = document.createElement("a");
        link.className = "post-title";
        link.href = p.url || "#";
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = p.title || "Untitled";
        li.appendChild(link);
        if (p.snippet) li.appendChild(elText("div", p.snippet, "post-snippet"));
        list.appendChild(li);
      }
      sec.appendChild(list);
    } else if (redditNote) {
      sec.appendChild(elText("p", redditNote, "reddit-note"));
    }
    card.appendChild(sec);
  }

  // ── Earnings ──────────────────────────────────────────────────
  if (r.next_earnings_date) {
    const sec = el("div", "report-section");
    sec.appendChild(elText("h3", "Earnings"));
    const info = el("div", "earnings-info");
    info.appendChild(elText("span", r.next_earnings_date, "date"));
    if (r.days_until_earnings != null) {
      info.appendChild(elText("span",
        `(${r.days_until_earnings} days away)`, "days"));
    }
    sec.appendChild(info);
    card.appendChild(sec);
  }

  // ── Conclusion ────────────────────────────────────────────────
  if (r.conclusion || (r.rating && r.rating.rationale)) {
    const sec = el("div", "report-section");
    sec.appendChild(elText("h3", "Conclusion"));
    if (r.conclusion) sec.appendChild(elText("p", r.conclusion, "report-conclusion"));
    if (r.rating && r.rating.rationale) {
      sec.appendChild(elText("p", r.rating.rationale, "report-rationale"));
    }
    card.appendChild(sec);
  }

  // ── Movie quote (from agent when present, else fallback) ─────────
  const quoteLine = r.movie_quote_line && r.movie_quote_line.trim();
  const quoteAttribution = r.movie_quote_attribution && r.movie_quote_attribution.trim();
  const fallbackQuotes = [
    { who: "Sam Rogers (Margin Call)", line: "We're all just one trade away from humility." },
    { who: "Frank Underwood (House of Cards)", line: "Power is a lot like real estate. It's all about location, location, location." },
    { who: "Jordan Belfort (Wolf of Wall Street)", line: "The only thing standing between you and your goal is the story you keep telling yourself." },
    { who: "Mark Baum (The Big Short)", line: "I have a feeling in a few years people are going to be doing what they always do when the economy tanks. They will be blaming it on immigrants and poor people." },
  ];
  const quote = quoteLine
    ? { line: quoteLine, who: quoteAttribution || "—" }
    : fallbackQuotes[Math.floor(Math.random() * fallbackQuotes.length)];
  const quoteSec = el("div", "report-section report-quote");
  quoteSec.appendChild(elText("h3", "Quote"));
  const quoteBlock = el("div", "quote-block");
  quoteBlock.appendChild(elText("p", "\u201C" + quote.line + "\u201D", "quote-line"));
  quoteBlock.appendChild(elText("div", quote.who ? "\u2014 " + quote.who : "", "quote-attribution"));
  quoteSec.appendChild(quoteBlock);
  card.appendChild(quoteSec);

  return card;
}

/* ── DOM helpers ─────────────────────────────────────────────── */

function el(tag, className) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  return e;
}

function elText(tag, text, className) {
  const e = el(tag, className);
  e.textContent = text || "";
  return e;
}

function section(title, body) {
  const sec = el("div", "report-section");
  sec.appendChild(elText("h3", title));
  sec.appendChild(elText("p", body));
  return sec;
}

function sentimentItem(name, value, signal) {
  const item = el("div", "sentiment-item");
  item.appendChild(elText("div", name, "name"));
  item.appendChild(elText("div", String(value ?? "N/A"), "value"));
  const sigEl = elText("div", signal || "", "signal " + signalClass(signal));
  item.appendChild(sigEl);
  return item;
}

function optionItem(label, value) {
  const item = el("div", "option-item");
  item.appendChild(elText("div", label, "label"));
  item.appendChild(elText("div", value || "N/A", "value"));
  return item;
}

function signalClass(signal) {
  if (!signal) return "";
  const s = signal.toLowerCase();
  if (s.includes("bullish") || s === "buy" || s === "greed") return "signal-bullish";
  if (s.includes("bearish") || s === "sell" || s === "fear")  return "signal-bearish";
  if (s.includes("neutral") || s === "hold" || s === "mixed") return "signal-neutral";
  if (s.includes("cautious")) return "signal-cautious";
  return "";
}

function fmtNum(val) {
  if (val == null) return "N/A";
  if (typeof val === "number") return val.toFixed(2);
  return String(val);
}
