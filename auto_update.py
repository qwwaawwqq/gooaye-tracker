#!/usr/bin/env python3
"""
auto_update.py — detect new 股癌 episodes, transcribe the audio with Whisper,
and produce a deep-summary JSON the web app can merge into its EPISODES dict.

Pipeline:
  RSS  ─►  state diff (last_seen_ep)  ─►  for each new episode:
       download mp3  ─►  whisper transcript  ─►  Claude API structurer
                                                  │
                                                  └─► _episodes_auto.json

  If whisper / Claude API are unavailable, we fall back gracefully:
    - no whisper        → placeholder entry, marked "audio-pending"
    - whisper ok, no LLM → entry carries raw transcript chunked into <ul><li>

Run:
  python3 auto_update.py                  # detect + transcribe + write
  python3 auto_update.py --dry-run        # detect only
  python3 auto_update.py --force-ep 661   # re-process a specific episode
  python3 auto_update.py --model small    # whisper model: tiny|base|small|medium|large
"""

from __future__ import annotations
import argparse, html, json, os, re, shutil, subprocess, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "_state.json"
OUT_FILE = ROOT / "_episodes_auto.json"
CACHE_DIR = ROOT / ".cache_audio"
ENV_FILE = ROOT / ".env"
RSS_URL = "https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3.xml"


def load_dotenv() -> None:
    """Minimal .env loader — KEY=value lines, # comments. Cron runs without
    a shell rc, so env vars set in ~/.zshrc are not visible. .env fixes that."""
    if not ENV_FILE.exists():
        return
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def git_commit_and_push(files: list[Path], message: str) -> bool:
    """Stage given files, commit if there's a diff, push to origin.
    Returns True if a push happened, False otherwise."""
    try:
        rel = [str(p.relative_to(ROOT)) for p in files if p.exists()]
        if not rel:
            return False
        # Check for staged + unstaged changes against HEAD
        status = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--"] + rel,
                                capture_output=True, text=True)
        if not status.stdout.strip():
            print("  [git] no changes to commit")
            return False
        subprocess.run(["git", "-C", str(ROOT), "add", "--"] + rel, check=True)
        subprocess.run(["git", "-C", str(ROOT), "commit", "-m", message], check=True)
        push = subprocess.run(["git", "-C", str(ROOT), "push"], capture_output=True, text=True)
        if push.returncode != 0:
            print(f"  [git] push failed: {push.stderr[-400:]}")
            return False
        print("  [git] pushed.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [git] error: {e}")
        return False

SPONSOR_MARKERS = (
    "本集由", "贊助", "letsharu", "結帳輸入", "傳送門", "linktr.ee/gooaye",
    "Hosting provided by", "SoundOn",
)


def fetch_rss(url: str = RSS_URL) -> ET.Element:
    req = urllib.request.Request(url, headers={"User-Agent": "gooaye-auto-update/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return ET.parse(resp).getroot()


def parse_ep_num(title: str) -> int | None:
    m = re.search(r"EP\s*(\d+)", title, re.IGNORECASE)
    return int(m.group(1)) if m else None


def parse_pubdate(raw: str) -> str:
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:16]


def strip_sponsor(text: str) -> str:
    """Remove obvious sponsor / housekeeping lines so we can judge content density."""
    lines = [ln.strip() for ln in text.splitlines()]
    kept = []
    for ln in lines:
        if not ln:
            continue
        if any(mk in ln for mk in SPONSOR_MARKERS):
            continue
        kept.append(ln)
    return "\n".join(kept)


def html_to_text(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"</p>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)


def classify_notes(notes_text: str) -> str:
    """Return 'content' if notes have real investment substance, else 'sponsor'."""
    cleaned = strip_sponsor(notes_text)
    # Heuristic: if >300 chars of non-sponsor text and contains finance vocabulary
    finance_terms = ("股", "盤", "EPS", "AI", "晶片", "聯發科", "台積", "FED", "降息",
                     "ETF", "AMD", "Intel", "Nvidia", "美元", "央行", "通膨")
    hits = sum(1 for t in finance_terms if t in cleaned)
    return "content" if (len(cleaned) > 300 and hits >= 2) else "sponsor"


def get_audio_url(item: ET.Element) -> str | None:
    enc = item.find("enclosure")
    if enc is None:
        return None
    return enc.get("url")


def download_audio(ep: int, url: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    dest = CACHE_DIR / f"EP{ep}.mp3"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"  [audio] cache hit: {dest.name} ({dest.stat().st_size//1024} KB)")
        return dest
    print(f"  [audio] downloading {url[:80]}…")
    req = urllib.request.Request(url, headers={"User-Agent": "gooaye-auto-update/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    print(f"  [audio] saved {dest.name} ({dest.stat().st_size//1024} KB)")
    return dest


def transcribe(ep: int, audio_path: Path, model: str = "small") -> Path | None:
    """Run whisper CLI; returns path to .txt transcript or None on failure."""
    txt_path = CACHE_DIR / f"EP{ep}.txt"
    if txt_path.exists() and txt_path.stat().st_size > 500:
        print(f"  [whisper] cache hit: {txt_path.name}")
        return txt_path
    if shutil.which("whisper") is None:
        print("  [whisper] CLI not found — install openai-whisper or use --no-audio")
        return None
    print(f"  [whisper] transcribing EP{ep} with model={model} (this can take a while)…")
    cmd = [
        "whisper", str(audio_path),
        "--model", model,
        "--language", "Chinese",
        "--task", "transcribe",
        "--output_dir", str(CACHE_DIR),
        "--output_format", "txt",
        "--fp16", "False",
        "--verbose", "False",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    except subprocess.TimeoutExpired:
        print("  [whisper] timed out")
        return None
    if proc.returncode != 0:
        print(f"  [whisper] failed rc={proc.returncode}: {proc.stderr[-500:]}")
        return None
    if not txt_path.exists():
        print(f"  [whisper] expected {txt_path} not produced")
        return None
    print(f"  [whisper] done → {txt_path.name} ({txt_path.stat().st_size//1024} KB)")
    return txt_path


def call_claude_for_transcript(ep: int, title: str, date: str, transcript: str,
                                api_key: str) -> dict | None:
    """Send transcript to Claude → return dict with summary/tags/stocks/deep."""
    try:
        import anthropic  # type: ignore
    except ImportError:
        print("  [claude] anthropic SDK not installed (pip install anthropic)")
        return None
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""你是股癌 podcast 深度摘要編輯。閱讀以下完整逐字稿，輸出 JSON。

EP: {ep}    Title: {title}    Date: {date}

逐字稿（whisper 自動轉錄，可能有錯字）：
\"\"\"
{transcript[:60000]}
\"\"\"

請輸出嚴格 JSON（不要 markdown 包覆、不要解釋），schema：
{{
  "tags": ["3-6 個關鍵詞，繁中"],
  "summary": "100-180 字繁中摘要 HTML（可用 <b>）",
  "stocks": [["TW"|"US", "代號或 ticker"]],
  "duration_minutes": 數字（如逐字稿能推估，否則 null）,
  "deep_html": "深度摘要 HTML 區塊：用 <h4>主軸 N：...</h4><ul><li>...</li></ul> 分段，金句用 <p style=\\"color:#fde047\\"><b>「...」</b></p>，結尾加 <h4>資料狀態</h4><p style=\\"color:#fbbf24\\">本摘要由 Claude API 自 whisper 逐字稿生成，可能有口誤/轉錄錯誤。</p>",
  "calls": [
    {{"t": "主軸短標(8字內)", "c": "call 內容(60字內，可用<b>)", "a": "後續動作或剛發布字樣", "v": "pending|hit|partial|miss"}}
  ],
  "stock_meta": {{
    "TW/2327": {{"name": "國巨", "stance": "啟動|看好|觀察|減碼 等(8字內)", "note": "本集脈絡(40字內，可用<b>)"}},
    "US/NVDA": {{"name": "NVIDIA", "stance": "...", "note": "..."}}
  }},
  "stocks_groups": [
    {{
      "tier": "primary|adjacent|defensive|overseas",
      "title": "分組標題(12字內，可帶 emoji)",
      "stocks": [
        {{"code": "2327", "mkt": "TW", "name": "國巨", "reason": "為什麼提到，對應哪個主軸，1 句 30-60 字，可用 <b>"}}
      ]
    }}
  ]
}}

calls 至少 3 條、至多 7 條；每條對應一個主軸的具體 call。
stock_meta 對應 stocks 陣列中每檔出現的標的；name 用繁中正式名稱、若 whisper 拼錯就修正。
stocks_groups: 把提及個股按主題分 3-5 組（如「被動元件主軸」「散熱事件」「防守換手」「海外觀察」），每組內每檔股票配一行 reason。
剛發布的新集 v 通常都 "pending"。"""
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = (resp.content[0].text if resp.content else "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [claude] JSON parse failed: {e}; first 300 chars: {text[:300]}")
        return None


def build_audio_entry(ep: int, title: str, date: str, link: str, audio_url: str,
                      model: str, no_audio: bool) -> dict:
    """Audio-first entry. Falls back to placeholder if whisper missing."""
    if no_audio or shutil.which("whisper") is None:
        entry = build_placeholder_entry(ep, title, date, link)
        entry["auto_status"] = "audio-pending"
        entry["audio_url"] = audio_url
        return entry

    audio_path = download_audio(ep, audio_url)
    txt_path = transcribe(ep, audio_path, model=model)
    if txt_path is None:
        entry = build_placeholder_entry(ep, title, date, link)
        entry["auto_status"] = "transcribe-failed"
        entry["audio_url"] = audio_url
        return entry

    transcript = txt_path.read_text()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    structured = call_claude_for_transcript(ep, title, date, transcript, api_key) if api_key else None

    if structured:
        raw_stocks = structured.get("stocks", []) or []
        clean_stocks: list[list[str]] = []
        for pair in raw_stocks:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2: continue
            m, c = pair[0], str(pair[1]).strip()
            if m == "TW" and re.fullmatch(r"\d{4,5}", c):
                clean_stocks.append(["TW", c])
            elif m == "US" and re.fullmatch(r"[A-Z][A-Z\.\-]{0,7}", c):
                clean_stocks.append(["US", c])

        raw_calls = structured.get("calls", []) or []
        clean_calls: list[dict] = []
        for call in raw_calls:
            if not isinstance(call, dict): continue
            t = str(call.get("t", "")).strip()
            c = str(call.get("c", "")).strip()
            if not t or not c: continue
            v = call.get("v", "pending")
            if v not in ("hit", "partial", "miss", "pending"): v = "pending"
            clean_calls.append({
                "ep": ep, "t": t[:24], "c": c[:240],
                "a": str(call.get("a", "")).strip()[:160] or "剛發布",
                "v": v,
            })

        raw_meta = structured.get("stock_meta", {}) or {}
        clean_meta: dict = {}
        for key, val in raw_meta.items():
            if not isinstance(val, dict): continue
            m_match = re.fullmatch(r"(TW|US)/([A-Za-z0-9\.\-]{1,8})", str(key))
            if not m_match: continue
            mk = f"{m_match.group(1)}/{m_match.group(2).upper() if m_match.group(1)=='US' else m_match.group(2)}"
            clean_meta[mk] = {
                "name": str(val.get("name", "")).strip()[:24],
                "stance": str(val.get("stance", "")).strip()[:24],
                "note": str(val.get("note", "")).strip()[:200],
                "ep": ep,
            }

        raw_groups = structured.get("stocks_groups", []) or []
        clean_groups: list[dict] = []
        TIER_STYLE = {
            "primary":   ("rgba(74,222,128,0.04)", "#4ade80"),
            "adjacent":  ("rgba(251,191,36,0.04)", "#fbbf24"),
            "defensive": ("rgba(96,165,250,0.04)", "#60a5fa"),
            "overseas":  ("rgba(167,139,250,0.04)", "#a78bfa"),
        }
        groups_html_parts: list[str] = []
        for g in raw_groups:
            if not isinstance(g, dict): continue
            tier = g.get("tier", "primary")
            bg, accent = TIER_STYLE.get(tier, TIER_STYLE["primary"])
            stocks_list = g.get("stocks", []) or []
            valid_lines = []
            for s in stocks_list:
                if not isinstance(s, dict): continue
                code = str(s.get("code", "")).strip()
                mkt = str(s.get("mkt", "")).strip().upper()
                if mkt == "TW" and not re.fullmatch(r"\d{4,5}", code): continue
                if mkt == "US" and not re.fullmatch(r"[A-Z][A-Z\.\-]{0,7}", code): continue
                if not mkt: continue
                name = str(s.get("name", "")).strip()[:24] or code
                reason = str(s.get("reason", "")).strip()[:200]
                valid_lines.append({"code": code, "mkt": mkt, "name": name, "reason": reason})
            if not valid_lines: continue
            clean_groups.append({
                "tier": tier, "title": str(g.get("title", ""))[:24],
                "stocks": valid_lines,
            })
            lines_html = "".join(
                f"<b>{s['code']} {s['name']}</b>　{s['reason']}<br>" for s in valid_lines
            ).rstrip("<br>")
            groups_html_parts.append(
                f'<div style="background:{bg};border-left:2px solid {accent};'
                f'padding:6px 10px;border-radius:4px"><b>{g.get("title","")}</b><br>{lines_html}</div>'
            )

        deep_html = structured.get("deep_html", "")
        if groups_html_parts:
            total = sum(len(g["stocks"]) for g in clean_groups)
            groups_block = (
                f'<h4>📊 提及個股（{total} 檔）</h4>'
                '<p style="color:#8ea3c0;font-size:11px;margin-bottom:8px">由 Claude API 自逐字稿分類；whisper 對公司名 homophone 錯誤多，個股代號以模型還原為準，必要時人工二校。</p>'
                '<div style="display:grid;grid-template-columns:1fr;gap:6px;font-size:12px;line-height:1.55">'
                + "".join(groups_html_parts) + '</div>'
            )
            # insert before 資料狀態 footer if present, else append
            footer_marker = '<h4>資料狀態</h4>'
            if footer_marker in deep_html:
                deep_html = deep_html.replace(footer_marker, groups_block + footer_marker)
            else:
                deep_html = deep_html + groups_block

        return {
            "ep": ep,
            "date": date,
            "title": title.strip(),
            "dur": f"{structured.get('duration_minutes') or '—'}分",
            "v": "pending",
            "tags": structured.get("tags", ["新集上線"]),
            "summary": structured.get("summary", ""),
            "stocks": clean_stocks,
            "deep": deep_html,
            "calls": clean_calls,
            "stock_meta": clean_meta,
            "stocks_groups": clean_groups,
            "auto_status": "audio+llm",
            "auto_generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "transcript_chars": len(transcript),
        }

    # No LLM available — embed raw transcript chunked
    paragraphs = [p.strip() for p in re.split(r"\n\n+|(?<=[。！？])\s+", transcript) if p.strip()]
    chunks = [paragraphs[i:i+8] for i in range(0, len(paragraphs), 8)]
    deep_parts = ["<h4>逐字稿（whisper 自動轉錄）</h4>"]
    for i, chunk in enumerate(chunks[:6], 1):
        deep_parts.append(f"<h4>段落 {i}</h4><ul>")
        deep_parts.extend(f"<li>{html.escape(p)}</li>" for p in chunk)
        deep_parts.append("</ul>")
    deep_parts.append(
        "<h4>資料狀態</h4><p style=\"color:#fbbf24\">"
        "已透過 whisper 轉錄音檔，但 Claude API 未啟用，未做結構化主軸切分。"
        "設定 ANTHROPIC_API_KEY 後重跑即可自動生成深度摘要。</p>"
    )
    return {
        "ep": ep,
        "date": date,
        "title": title.strip(),
        "dur": "—",
        "v": "pending",
        "tags": ["新集上線", "transcript-only"],
        "summary": (transcript[:280] + "…") if len(transcript) > 280 else transcript,
        "stocks": [],
        "deep": "".join(deep_parts),
        "auto_status": "audio-only",
        "auto_generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "transcript_chars": len(transcript),
    }


def build_placeholder_entry(ep: int, title: str, date: str, link: str) -> dict:
    emoji = ""
    m = re.search(r"EP\d+\s*\|\s*(\S+)", title)
    if m:
        emoji = m.group(1)
    return {
        "ep": ep,
        "date": date,
        "title": title.strip(),
        "dur": "—",
        "v": "pending",
        "tags": ["新集上線", "深度摘要待補"],
        "summary": (
            f"<b>EP{ep} 已上線（{date}）</b>。"
            "Show notes 為贊助/開場內容，<b>vocus 社群整理約 1-2 天後上線</b>，"
            "屆時本卡片會自動補上深度摘要與個股清單。"
        ),
        "stocks": [],
        "deep": (
            f"<h4>狀態</h4><p style=\"color:#fbbf24\">"
            f"EP{ep} 於 {date} 發布，目前僅 RSS show notes（贊助/開場），"
            "尚未取得 vocus 社群整理或逐字稿。<br>"
            "下次 auto_update 跑到時若 vocus 已發佈會自動補齊。</p>"
            f"<h4>RSS Link</h4><p><a href=\"{html.escape(link)}\" target=\"_blank\" "
            "style=\"color:#7dd3fc\">SoundOn 收聽</a></p>"
        ),
        "auto_status": "placeholder",
        "auto_generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def build_content_entry(ep: int, title: str, date: str, link: str, notes_text: str) -> dict:
    """When show notes contain real content, render them as a basic deep block.
    Optionally call Claude API to structure into the project's <h4>/<ul> idiom."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    cleaned = strip_sponsor(notes_text).strip()

    structured_html = None
    if api_key:
        try:
            structured_html = call_claude_structurer(ep, title, cleaned, api_key)
        except Exception as e:  # pragma: no cover
            print(f"[warn] Claude API failed for EP{ep}: {e}", file=sys.stderr)

    if not structured_html:
        # Fallback: raw notes as a single block, marked draft
        bullets = "".join(f"<li>{html.escape(ln)}</li>" for ln in cleaned.splitlines() if ln.strip())
        structured_html = (
            "<h4>Show notes（自動擷取，未經人工結構化）</h4>"
            f"<ul>{bullets}</ul>"
            "<p style=\"color:#fbbf24\">深度結構化版本待 Claude API 啟用或 vocus 整理發布。</p>"
        )

    return {
        "ep": ep,
        "date": date,
        "title": title.strip(),
        "dur": "—",
        "v": "pending",
        "tags": ["新集上線", "auto-summary"],
        "summary": (cleaned[:280] + "…") if len(cleaned) > 280 else cleaned,
        "stocks": [],
        "deep": structured_html,
        "auto_status": "content" if api_key else "draft",
        "auto_generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def call_claude_structurer(ep: int, title: str, notes: str, api_key: str) -> str | None:
    """Call Anthropic API to produce a deep:HTML block matching the project idiom."""
    try:
        import anthropic  # type: ignore
    except ImportError:
        print("[info] anthropic SDK not installed; skipping LLM structuring", file=sys.stderr)
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""你是股癌 podcast 深度摘要編輯。把以下 show notes 轉成繁體中文深度摘要 HTML 區塊。

格式要求（必須遵守）：
- 用 <h4>主軸 N：...</h4> 切段，每段下用 <ul><li>...</li></ul>
- 關鍵詞、股票代號、漲跌幅用 <b>...</b>
- 金句用 <p style="color:#fde047"><b>「...」</b></p>
- 若 notes 不足以涵蓋 5 個主軸，就只寫實際存在的部分
- 結尾加 <h4>資料狀態</h4><p style="color:#fbbf24">本摘要由 Claude API 從 RSS show notes 自動生成，vocus 社群整理上線後會被覆蓋。</p>
- 直接輸出 HTML，不要 markdown code fence、不要解釋

EP: {ep}
Title: {title}
Show notes:
{notes[:6000]}
"""
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text if resp.content else ""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text or None


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_seen_ep": 0, "initialized_by": "auto_update"}


def prune_audio_cache(keep: int = 8) -> None:
    """Keep only the most recent N EP*.mp3 and EP*.txt files to avoid disk fill."""
    if not CACHE_DIR.exists(): return
    for pattern in ("EP*.mp3", "EP*.txt"):
        files = sorted(CACHE_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[keep:]:
            try:
                old.unlink()
                print(f"  [prune] removed {old.name}")
            except OSError:
                pass


def save_state(state: dict) -> None:
    state["last_check"] = datetime.now().astimezone().isoformat(timespec="seconds")
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def load_existing_auto() -> dict:
    if OUT_FILE.exists():
        return json.loads(OUT_FILE.read_text())
    return {"episodes": {}, "schema": 1}


def save_auto(data: dict) -> None:
    data["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-ep", type=int, default=None,
                    help="re-process this episode even if already seen")
    ap.add_argument("--no-audio", action="store_true",
                    help="skip audio download + transcription (placeholder only)")
    ap.add_argument("--model", default="small",
                    help="whisper model: tiny|base|small|medium|large (default small)")
    ap.add_argument("--push", action="store_true",
                    help="git commit + push _episodes_auto.json after a successful update")
    args = ap.parse_args()
    load_dotenv()

    print(f"[{datetime.now().isoformat(timespec='seconds')}] fetching RSS …")
    root = fetch_rss()
    items = root.findall(".//item")
    state = load_state()
    last_seen = int(state.get("last_seen_ep", 0))
    auto = load_existing_auto()
    episodes = auto.setdefault("episodes", {})

    new_entries: list[dict] = []
    max_seen = last_seen
    for item in items:
        title = (item.findtext("title") or "").strip()
        ep = parse_ep_num(title)
        if ep is None:
            continue
        if args.force_ep is not None:
            if ep != args.force_ep:
                continue
        elif ep <= last_seen:
            continue

        date = parse_pubdate(item.findtext("pubDate") or "")
        link = item.findtext("link") or ""
        audio_url = get_audio_url(item)

        if args.dry_run:
            print(f"  EP{ep} ({date}) → would transcribe (audio={bool(audio_url)})")
            new_entries.append({"ep": ep, "_dry": True})
            max_seen = max(max_seen, ep)
            continue

        if audio_url and not args.no_audio:
            entry = build_audio_entry(ep, title, date, link, audio_url,
                                       model=args.model, no_audio=False)
            print(f"  EP{ep} ({date}) → audio entry ({entry['auto_status']})")
        else:
            entry = build_placeholder_entry(ep, title, date, link)
            if audio_url:
                entry["audio_url"] = audio_url
            entry["auto_status"] = "audio-pending" if audio_url else "no-audio"
            print(f"  EP{ep} ({date}) → placeholder ({entry['auto_status']})")

        new_entries.append(entry)
        episodes[str(ep)] = entry
        max_seen = max(max_seen, ep)

    if not new_entries:
        print("  no new episodes.")
        return 0

    if args.dry_run:
        print("[dry-run] not writing.")
        return 0

    save_auto(auto)
    if args.force_ep is None:
        state["last_seen_ep"] = max_seen
    save_state(state)
    print(f"[done] wrote {OUT_FILE.name}, state.last_seen_ep={state['last_seen_ep']}")
    prune_audio_cache(keep=8)

    if args.push:
        eps_done = sorted(int(e.get("ep") or 0) for e in new_entries if e.get("ep"))
        msg = f"auto: ingest EP{eps_done[-1]}" if eps_done else "auto: update episodes"
        git_commit_and_push([OUT_FILE], msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
