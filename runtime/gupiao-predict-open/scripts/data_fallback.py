#!/usr/bin/env python3
"""
Open data fallback for 点石成金.

This module is intentionally pure Python. It uses eltdx first for quotes and
opentdx for K-line data, with conservative empty fallbacks for optional fields
that require paid/closed L2 feeds.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from typing import Any


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ")
    if hasattr(value, "value"):
        return str(value.value)
    if hasattr(value, "_asdict"):
        return str(value._asdict())
    return str(value)


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=_json_default))


def _market_for(code: str):
    from opentdx import MARKET

    code = str(code).strip()
    if code.startswith("6"):
        return MARKET.SH
    if code.startswith(("8", "4")):
        return MARKET.BJ
    return MARKET.SZ


def _bar_to_dict(bar: dict[str, Any], source: str = "opentdx") -> dict[str, Any]:
    when = bar.get("datetime") or bar.get("date") or bar.get("time")
    return {
        "date": _json_default(when) if when is not None else "",
        "open": float(bar.get("open") or 0),
        "high": float(bar.get("high") or 0),
        "low": float(bar.get("low") or 0),
        "close": float(bar.get("close") or 0),
        "volume": float(bar.get("vol") or bar.get("volume") or 0),
        "amount": float(bar.get("amount") or 0),
        "turnover": float(bar.get("turnover") or 0),
        "source": source,
    }


def get_quote(code: str) -> dict[str, Any]:
    code = str(code).strip()
    try:
        from eltdx import TdxClient

        client = TdxClient(timeout=5, probe_hosts=True, probe_timeout=2)
        client.connect()
        try:
            rows = client.get_quote([code])
        finally:
            client.close()
        if rows:
            row = rows[0]
            price = float(getattr(row, "last_price", 0) or 0)
            pre_close = float(getattr(row, "pre_close_price", 0) or 0)
            return {
                "code": code,
                "source": "eltdx",
                "price": price,
                "change_pct": round((price - pre_close) / (pre_close or 1) * 100, 4),
                "volume": float(getattr(row, "total_hand", 0) or 0),
                "amount": float(getattr(row, "amount", 0) or 0),
                "open": float(getattr(row, "open_price", 0) or 0),
                "high": float(getattr(row, "high_price", 0) or 0),
                "low": float(getattr(row, "low_price", 0) or 0),
            }
    except Exception:
        pass

    from opentdx import QuotationClient

    client = QuotationClient(raise_exception=True)
    client.connect().login()
    try:
        rows = client.get_quotes(_market_for(code), code)
    finally:
        client.disconnect()
    if not rows:
        raise RuntimeError(f"No quote data for {code}")
    row = rows[0]
    price = float(row.get("close") or 0)
    pre_close = float(row.get("pre_close") or 0)
    return {
        "code": code,
        "source": "opentdx",
        "price": price,
        "change_pct": round((price - pre_close) / (pre_close or 1) * 100, 4),
        "volume": float(row.get("vol") or 0),
        "amount": float(row.get("amount") or 0),
        "open": float(row.get("open") or 0),
        "high": float(row.get("high") or 0),
        "low": float(row.get("low") or 0),
    }


def get_kline(code: str, period: str = "daily", limit: int = 180) -> list[dict[str, Any]]:
    from opentdx import PERIOD, TdxClient

    period_map = {
        "daily": PERIOD.DAILY,
        "day": PERIOD.DAILY,
        "d": PERIOD.DAILY,
        "101": PERIOD.DAILY,
        "m1": PERIOD.MIN_1,
        "1m": PERIOD.MIN_1,
        "min1": PERIOD.MIN_1,
        "m5": PERIOD.MIN_5,
        "5m": PERIOD.MIN_5,
        "min5": PERIOD.MIN_5,
        "m15": PERIOD.MIN_15,
        "15m": PERIOD.MIN_15,
        "m30": PERIOD.MIN_30,
        "30m": PERIOD.MIN_30,
        "m60": PERIOD.MIN_60,
        "60m": PERIOD.MIN_60,
    }
    mapped = period_map.get(str(period or "daily").lower(), PERIOD.DAILY)
    with TdxClient() as client:
        rows = client.stock_kline(_market_for(code), str(code).strip(), mapped, count=int(limit or 180))
    return [_bar_to_dict(row) for row in rows]


def get_daily_kline(code: str, limit: int = 180) -> list[dict[str, Any]]:
    return get_kline(code, "daily", limit)


def get_capital_flow(code: str) -> dict[str, Any]:
    quote = get_quote(code)
    return {
        "source": quote.get("source", "tdx"),
        "code": str(code).strip(),
        "main_net": 0.0,
        "retail_net": 0.0,
        "amount": float(quote.get("amount") or 0),
        "note": "Open fallback has no closed L2 capital breakdown; use mx-data/TDX MCP when available.",
    }


def get_l2_data(code: str) -> dict[str, Any]:
    capital = get_capital_flow(code)
    return {
        "code": str(code).strip(),
        "source": capital["source"],
        "large_buy": 0.0,
        "large_sell": 0.0,
        "main_net": capital["main_net"],
        "amount": capital["amount"],
        "note": capital["note"],
    }


def check_health() -> dict[str, Any]:
    detail: dict[str, Any] = {}
    try:
        detail["quote"] = get_quote("000001")
        primary_ok = True
    except Exception as exc:
        detail["quote_error"] = f"{type(exc).__name__}: {exc}"
        primary_ok = False
    try:
        detail["kline_sample"] = get_daily_kline("000001", 1)
        backup_ok = bool(detail["kline_sample"])
    except Exception as exc:
        detail["kline_error"] = f"{type(exc).__name__}: {exc}"
        backup_ok = False
    return {"primary_ok": primary_ok, "backup_ok": backup_ok, "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser(description="点石成金开源数据兜底层")
    parser.add_argument("--mode", choices=["health", "quote", "kline", "capital", "l2", "concepts", "boards", "belong"], default="health")
    parser.add_argument("--code")
    parser.add_argument("--symbol")
    parser.add_argument("--count", type=int, default=60)
    args = parser.parse_args()

    code = args.code or "000001"
    if args.mode == "health":
        print_json(check_health())
    elif args.mode == "quote":
        print_json(get_quote(code))
    elif args.mode == "kline":
        print_json(get_daily_kline(code, args.count))
    elif args.mode == "capital":
        print_json(get_capital_flow(code))
    elif args.mode == "l2":
        print_json(get_l2_data(code))
    elif args.mode in {"concepts", "boards", "belong"}:
        print_json({"source": "open_fallback", "data": [], "note": f"{args.mode} requires TDX MCP/mx-data enrichment"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
