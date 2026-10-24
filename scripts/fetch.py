"""日本株の日足を取得して data/ に JSON で保存する。

GitHub Actions から平日の夕方に実行される。
銘柄はリポジトリ直下の tickers.json で管理する。
取得に失敗した銘柄は前回のファイルをそのまま残す。
"""

import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))
PERIOD = "5y"


def num(x, digits=2):
    v = round(float(x), digits)
    return int(v) if v == int(v) else v


def fetch_one(code: str):
    sym = f"{code}.T"
    last_err = None
    for attempt in range(3):
        try:
            df = yf.Ticker(sym).history(period=PERIOD, interval="1d", auto_adjust=False)
            if df is None or df.empty:
                raise RuntimeError("empty")
            rows = []
            for idx, r in df.iterrows():
                vals = [r["Open"], r["High"], r["Low"], r["Close"]]
                if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
                    continue
                if r["Close"] <= 0:
                    continue
                vol = r.get("Volume", 0)
                vol = 0 if vol is None or (isinstance(vol, float) and math.isnan(vol)) else int(vol)
                rows.append([idx.strftime("%Y-%m-%d"), num(r["Open"]), num(r["High"]),
                             num(r["Low"]), num(r["Close"]), vol])
            if len(rows) < 20:
                raise RuntimeError(f"too few rows ({len(rows)})")
            return rows
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(3 * (attempt + 1))
    print(f"  ! {code}: {last_err}", file=sys.stderr)
    return None


def main():
    tickers = json.loads((ROOT / "tickers.json").read_text(encoding="utf-8"))
    DATA.mkdir(exist_ok=True)
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    index = []
    ok = 0
    for t in tickers:
        code, name = str(t["code"]), t["name"]
        print(f"- {code} {name}")
        rows = fetch_one(code)
        path = DATA / f"{code}.json"
        if rows:
            path.write_text(json.dumps({"code": code, "name": name, "rows": rows},
                                       ensure_ascii=False, separators=(",", ":")),
                            encoding="utf-8")
            ok += 1
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            r = saved["rows"]
            index.append({"code": code, "name": name, "last": r[-1][0],
                          "close": r[-1][4], "prev": r[-2][4] if len(r) > 1 else r[-1][4]})
        time.sleep(0.5)

    (DATA / "index.json").write_text(
        json.dumps({"updated": now, "tickers": index}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"done: {ok}/{len(tickers)} updated")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
