#!/usr/bin/env python3
"""
update_market.py — fetch current prices for every stock in STOCKS dict,
compute hit/miss vs the stance recorded at first mention, write rankings
to _market_auto.json so the web app can render ⭐ Top 5 命中 + ⚠️ 失準項
without manual updates.

Schedule: daily 17:30 Asia/Taipei (after TWSE 13:30 close + buffer).

Workflow:
  index.html (STOCKS dict regex extract) ─┐
  _episodes_auto.json (EPISODES dates) ───┤─► first-mention close
                                          │   yfinance current close
                                          │   = % return + verdict
                                          └─► _market_auto.json (rankings)
                                              git commit + push
"""

from __future__ import annotations
import argparse, json, os, re, subprocess, sys, warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
INDEX_HTML = ROOT / "index.html"
EPS_AUTO = ROOT / "_episodes_auto.json"
OUT_FILE = ROOT / "_market_auto.json"
ENV_FILE = ROOT / ".env"


def load_dotenv() -> None:
    if not ENV_FILE.exists(): return
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and k not in os.environ: os.environ[k] = v


def extract_stocks_from_html(path: Path) -> dict:
    """Pull the STOCKS = { ... } block out of index.html and parse each entry.
    Robust enough for the project's formatting (one entry per line)."""
    text = path.read_text()
    m = re.search(r"const STOCKS = \{(.*?)\n\};", text, re.DOTALL)
    if not m:
        raise SystemExit("[error] could not locate STOCKS dict in index.html")
    body = m.group(1)
    stocks: dict = {}
    line_re = re.compile(r"^\s*'([^']+)':\s*\{(.+)\},?\s*$")
    for line in body.splitlines():
        m2 = line_re.match(line)
        if not m2: continue
        code, raw = m2.group(1), m2.group(2)
        entry = {"code": code}
        # name
        n = re.search(r"name\s*:\s*'([^']+)'", raw); entry["name"] = n.group(1) if n else code
        # mkt
        mk = re.search(r"mkt\s*:\s*'([^']+)'", raw); entry["mkt"] = mk.group(1) if mk else ""
        # stance
        st = re.search(r"stance\s*:\s*'([^']+)'", raw); entry["stance"] = st.group(1) if st else ""
        # eps array
        ep = re.search(r"eps\s*:\s*\[([^\]]*)\]", raw)
        eps = [int(x) for x in re.findall(r"\d+", ep.group(1))] if ep else []
        entry["eps"] = eps
        stocks[code] = entry
    return stocks


def load_episodes_dates() -> dict:
    """Map ep -> date (YYYY-MM-DD), preferring _episodes_auto.json then HTML inline."""
    dates: dict = {}
    if EPS_AUTO.exists():
        try:
            d = json.loads(EPS_AUTO.read_text())
            for k, v in (d.get("episodes") or {}).items():
                if v.get("ep") and v.get("date"):
                    dates[int(v["ep"])] = v["date"]
        except Exception: pass
    # also parse inline EPISODES dict in index.html
    html = INDEX_HTML.read_text()
    for m in re.finditer(r"\s(\d{3,4}):\{date:'(\d{4}-\d{2}-\d{2})'", html):
        ep, d = int(m.group(1)), m.group(2)
        dates.setdefault(ep, d)
    return dates


def yf_symbol(code: str, mkt: str) -> str:
    if mkt == "tw" and code.isdigit():
        return f"{code}.TW"
    return code


def fetch_perf(symbol: str, start_date: str) -> dict | None:
    """Return {price, start_close, end_close, change_pct} or None if data unavailable."""
    import yfinance as yf
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        return None
    # add 1-month lookback for OTC stocks that may have sparse data
    fetch_start = (start_dt - timedelta(days=4)).strftime("%Y-%m-%d")
    try:
        hist = yf.Ticker(symbol).history(start=fetch_start, period="6mo", auto_adjust=False)
    except Exception as e:
        print(f"  [{symbol}] yf error: {e}", file=sys.stderr)
        return None
    if hist is None or hist.empty:
        return None
    closes = hist["Close"].dropna()
    if closes.empty: return None
    # First close at-or-after start_dt
    on_or_after = closes[closes.index.date >= start_dt.date()]
    start_close = float(on_or_after.iloc[0]) if not on_or_after.empty else float(closes.iloc[0])
    end_close = float(closes.iloc[-1])
    return {
        "symbol": symbol,
        "start_date": str(on_or_after.index[0].date()) if not on_or_after.empty else str(closes.index[0].date()),
        "start_close": round(start_close, 2),
        "end_date": str(closes.index[-1].date()),
        "end_close": round(end_close, 2),
        "change_pct": round((end_close / start_close - 1) * 100, 2),
    }


def verdict_from(stance: str, change_pct: float) -> str:
    pos_stances = ("看好", "啟動", "受惠", "轉強", "抗 AI", "中性", "CPU 大客戶",
                   "CPU+ASIC", "底氣足", "近期屌噴", "被動元件主角", "Power 鏈延伸")
    neg_stances = ("預期打滿", "減碼", "看淡", "估值打壓", "退出")
    is_pos = any(p in stance for p in pos_stances)
    is_neg = any(n in stance for n in neg_stances)
    if change_pct >= 15:
        return "hit" if is_pos else ("miss" if is_neg else "partial")
    if change_pct >= 5:
        return "partial" if is_pos else ("partial" if is_neg else "pending")
    if change_pct <= -10:
        return "miss" if is_pos else ("hit" if is_neg else "partial")
    if -5 <= change_pct <= 5:
        return "pending"
    return "partial"


def rank_top_and_misses(perf_map: dict, stocks: dict) -> dict:
    """Rank stocks for ⭐ Top 5 命中 and ⚠️ 失準項."""
    rows = []
    for code, perf in perf_map.items():
        if not perf: continue
        s = stocks.get(code, {})
        rows.append({
            "code": code, "name": s.get("name", code), "mkt": s.get("mkt", ""),
            "stance": s.get("stance", ""), "first_ep": min(s.get("eps") or [0]),
            "change_pct": perf["change_pct"], "verdict": perf.get("verdict", "pending"),
            "start_date": perf.get("start_date"), "end_date": perf.get("end_date"),
            "end_close": perf.get("end_close"),
        })

    pos_stance = lambda s: any(p in s for p in ("看好", "啟動", "受惠", "轉強", "抗 AI", "底氣足", "新進", "被動元件"))
    top_hits = sorted(
        [r for r in rows if pos_stance(r["stance"]) and r["change_pct"] is not None],
        key=lambda r: r["change_pct"], reverse=True,
    )[:5]
    misses = sorted(
        [r for r in rows if pos_stance(r["stance"]) and r["change_pct"] is not None and r["change_pct"] < -3],
        key=lambda r: r["change_pct"],
    )[:5]
    flat_warnings = [r for r in rows if abs(r["change_pct"] or 0) < 2][:8]
    return {"top_hits": top_hits, "misses": misses, "flat": flat_warnings}


def synthesize_actions(rankings: dict, eps_data: dict, api_key: str) -> list | None:
    """Use Claude to write 3-5 actionable cards based on the latest episodes + rankings."""
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=api_key)
    latest = sorted(eps_data.get("episodes", {}).values(), key=lambda v: v.get("ep") or 0, reverse=True)[:3]
    ctx_eps = "\n\n".join(
        f"EP{v.get('ep')} ({v.get('date')}): {v.get('title','')}\n"
        f"summary: {(v.get('summary') or '')[:600]}"
        for v in latest
    )
    top_str = ", ".join(f"{r['name']}({r['code']}) {r['change_pct']:+.1f}%" for r in rankings["top_hits"][:5])
    miss_str = ", ".join(f"{r['name']}({r['code']}) {r['change_pct']:+.1f}%" for r in rankings["misses"][:5])
    prompt = f"""你是股癌追蹤站的策略編輯。根據最新 3 集摘要 + 即時股價排名，產出 3-5 個 actionable 卡片（繁中）。

最新集數摘要：
{ctx_eps}

⭐ Top 5 命中（自動算）：{top_str}
⚠️ 失準項：{miss_str}

請輸出嚴格 JSON array（不要 markdown 包覆）：
[
  {{
    "title": "卡片標題 12 字內",
    "stance": "建議動作 8 字內，例: 加碼/減碼/觀察/避開",
    "depends": "依據：EP{{N}}+EP{{N}}...（要引用實際集數，10-50 字）",
    "checklist": "□ 動作 1<br>□ 動作 2<br>□ 動作 3（10-100 字）",
    "risk": "失準風險：... （10-60 字）",
    "tier": "redline|caution|opportunity"
  }}
]

tier 涵義：redline=已失準須立即處理；caution=需提高警覺；opportunity=新進場機會。
卡片數量 3-5 張，混合 tier。"""
    try:
        resp = client.messages.create(
            model="claude-opus-4-7", max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.content[0].text if resp.content else "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        cards = json.loads(text)
        if isinstance(cards, list) and 1 <= len(cards) <= 6:
            return cards
    except Exception as e:
        print(f"  [claude actions] failed: {e}", file=sys.stderr)
    return None


def git_commit_push(file: Path, msg: str) -> None:
    try:
        if not file.exists(): return
        status = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", str(file.relative_to(ROOT))],
                                capture_output=True, text=True)
        if not status.stdout.strip():
            print("  [git] no changes")
            return
        subprocess.run(["git", "-C", str(ROOT), "add", str(file.relative_to(ROOT))], check=True)
        subprocess.run(["git", "-C", str(ROOT), "commit", "-m", msg], check=True)
        push = subprocess.run(["git", "-C", str(ROOT), "push"], capture_output=True, text=True)
        if push.returncode != 0:
            print(f"  [git] push failed: {push.stderr[-300:]}")
        else:
            print("  [git] pushed.")
    except subprocess.CalledProcessError as e:
        print(f"  [git] error: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--no-actions", action="store_true",
                    help="skip Claude API action-card synthesis")
    ap.add_argument("--limit", type=int, default=None, help="only price-check first N stocks")
    args = ap.parse_args()
    load_dotenv()

    stocks = extract_stocks_from_html(INDEX_HTML)
    eps_dates = load_episodes_dates()
    print(f"[market] {len(stocks)} stocks, {len(eps_dates)} known episode dates")

    perf_map: dict = {}
    codes = list(stocks.items())
    if args.limit:
        codes = codes[:args.limit]
    for code, meta in codes:
        first_ep = min(meta["eps"]) if meta["eps"] else None
        start_date = eps_dates.get(first_ep) if first_ep else None
        if not start_date:
            print(f"  [{code}] no first-mention date — skipping")
            continue
        symbol = yf_symbol(code, meta["mkt"])
        perf = fetch_perf(symbol, start_date)
        if perf is None:
            print(f"  [{code}] no price data ({symbol} since {start_date})")
            continue
        perf["verdict"] = verdict_from(meta["stance"], perf["change_pct"])
        perf_map[code] = perf
        print(f"  [{code}] {symbol} since {start_date}: "
              f"{perf['start_close']} → {perf['end_close']} = {perf['change_pct']:+.2f}% [{perf['verdict']}]")

    rankings = rank_top_and_misses(perf_map, stocks)
    eps_data = json.loads(EPS_AUTO.read_text()) if EPS_AUTO.exists() else {"episodes": {}}

    actions = None
    if not args.no_actions and os.environ.get("ANTHROPIC_API_KEY"):
        actions = synthesize_actions(rankings, eps_data, os.environ["ANTHROPIC_API_KEY"])
        if actions: print(f"  [actions] {len(actions)} cards synthesized")

    out = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "perf": perf_map,
        "rankings": rankings,
        "actions": actions,
    }
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(f"[done] wrote {OUT_FILE.name}: {len(perf_map)} prices, "
          f"{len(rankings['top_hits'])} hits, {len(rankings['misses'])} misses, "
          f"{len(actions) if actions else 0} actions")

    if args.push:
        git_commit_push(OUT_FILE, "auto: refresh market data + rankings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
