#!/usr/bin/env python3
"""
backfill_call_tickers.py — resolve ticker symbols for calls in _episodes_auto.json

For each call in episodes[*].calls that has no {mkt, code} object yet, scan the call's
title (t) and content (c) for known stock names, then attach {mkt, code} when confident.

Built on factual name→code mapping (20+ most common 股癌 stocks + episode stock_meta).
Idempotent: already-resolved calls are skipped.

Usage:
  python backfill_call_tickers.py
Output:
  Resolved N tickers from _episodes_auto.json
"""

from __future__ import annotations
import json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EPS_AUTO = ROOT / "_episodes_auto.json"

# Built-in factual mapping of common 股癌 stock names → {mkt, code}
COMMON_STOCKS = {
    "台積電": {"mkt": "tw", "code": "2330"},
    "國巨": {"mkt": "tw", "code": "2327"},
    "聯發科": {"mkt": "tw", "code": "2454"},
    "創意": {"mkt": "tw", "code": "3443"},
    "世芯": {"mkt": "tw", "code": "3661"},
    "華新科": {"mkt": "tw", "code": "2492"},
    "信昌電": {"mkt": "tw", "code": "6173"},
    "旺宏": {"mkt": "tw", "code": "2337"},
    "愛普": {"mkt": "tw", "code": "6531"},
    "麗智": {"mkt": "tw", "code": "6231"},
    "立隆": {"mkt": "tw", "code": "2348"},
    "金山": {"mkt": "tw", "code": "2328"},
    "宇豪": {"mkt": "tw", "code": "5293"},
    "世界": {"mkt": "tw", "code": "5347"},
    "漢唐": {"mkt": "tw", "code": "3706"},
    "Intel": {"mkt": "us", "code": "INTC"},
    "NVIDIA": {"mkt": "us", "code": "NVDA"},
    "輝達": {"mkt": "us", "code": "NVDA"},
    "AMD": {"mkt": "us", "code": "AMD"},
    "Qualcomm": {"mkt": "us", "code": "QCOM"},
    "Meta": {"mkt": "us", "code": "META"},
    "Amazon": {"mkt": "us", "code": "AMZN"},
    "Google": {"mkt": "us", "code": "GOOGL"},
    "Tesla": {"mkt": "us", "code": "TSLA"},
    "TSLA": {"mkt": "us", "code": "TSLA"},
    "Palantir": {"mkt": "us", "code": "PLTR"},
    "PLTR": {"mkt": "us", "code": "PLTR"},
    "Broadcom": {"mkt": "us", "code": "AVGO"},
    "AVGO": {"mkt": "us", "code": "AVGO"},
    "Atlassian": {"mkt": "us", "code": "TEAM"},
    "TEAM": {"mkt": "us", "code": "TEAM"},
    "CrowdStrike": {"mkt": "us", "code": "CRWD"},
    "CRWD": {"mkt": "us", "code": "CRWD"},
    "Cloudflare": {"mkt": "us", "code": "NET"},
    "NET": {"mkt": "us", "code": "NET"},
    "Adobe": {"mkt": "us", "code": "ADBE"},
    "ADBE": {"mkt": "us", "code": "ADBE"},
    "Salesforce": {"mkt": "us", "code": "CRM"},
    "CRM": {"mkt": "us", "code": "CRM"},
}


def build_mapping_from_stock_meta(eps_data: dict) -> dict:
    """Extract {name → {mkt, code}} from episode stock_meta blocks."""
    mapping = {}
    for ep_str, ep_obj in (eps_data.get("episodes") or {}).items():
        stock_meta = ep_obj.get("stock_meta") or {}
        for key, meta in stock_meta.items():
            if "/" in key:  # format: "TW/2330"
                parts = key.split("/")
                if len(parts) == 2:
                    mkt, code = parts[0].lower(), parts[1]
                    name = meta.get("name", "")
                    if name:
                        mapping[name] = {"mkt": mkt, "code": code}
    return mapping


def resolve_ticker_in_text(text: str, all_mappings: dict) -> dict | None:
    """Scan text for known stock names, return first match as {mkt, code} or None."""
    if not text:
        return None
    text_lower = text.lower()
    for name, ticker in all_mappings.items():
        name_lower = name.lower()
        # Check if name appears as whole word (not substring)
        if re.search(r"\b" + re.escape(name_lower) + r"\b", text_lower):
            return ticker
    return None


def backfill_tickers() -> int:
    """Load _episodes_auto.json, resolve tickers, write back atomically. Return count resolved."""
    if not EPS_AUTO.exists():
        print(f"[error] {EPS_AUTO.name} not found")
        return 0

    try:
        eps_data = json.loads(EPS_AUTO.read_text())
    except json.JSONDecodeError as e:
        print(f"[error] failed to parse {EPS_AUTO.name}: {e}")
        return 0

    # Build full mapping: built-in + episode stock_meta
    mapping = dict(COMMON_STOCKS)
    mapping.update(build_mapping_from_stock_meta(eps_data))

    resolved = 0
    for ep_str, ep_obj in (eps_data.get("episodes") or {}).items():
        for call in (ep_obj.get("calls") or []):
            # Skip if already has ticker
            if call.get("ticker") and isinstance(call["ticker"], dict):
                continue

            # Try to resolve from title + content
            t = call.get("t", "")
            c = call.get("c", "")
            combined = f"{t} {c}"

            ticker = resolve_ticker_in_text(combined, mapping)
            if ticker:
                call["ticker"] = ticker
                resolved += 1
                print(f"  EP{call.get('ep')} '{t[:40]}...' → {ticker['mkt'].upper()}/{ticker['code']}")

    # Write back atomically
    if resolved > 0:
        tmp = EPS_AUTO.parent / f"{EPS_AUTO.name}.tmp"
        try:
            tmp.write_text(json.dumps(eps_data, ensure_ascii=False, indent=2) + "\n")
            os.replace(str(tmp), str(EPS_AUTO))
            print(f"[done] resolved {resolved} tickers in {EPS_AUTO.name}")
        except Exception as e:
            print(f"[error] failed to write {EPS_AUTO.name}: {e}")
            try:
                tmp.unlink()
            except OSError:
                pass
            return 0
    else:
        print(f"[done] no new tickers to resolve (all up-to-date)")

    return resolved


if __name__ == "__main__":
    raise SystemExit(backfill_tickers())
