"""
INVEX Terminal — analyze.py
Llegeix data.json, calcula RSI/MA i genera analysis.json amb senyals i alertes.
"""
import json
import sys
from datetime import date

import pandas as pd
import yfinance as yf


def calc_rsi(prices: pd.Series, n: int = 14) -> float:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0).rolling(n).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(n).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 1) if not pd.isna(val) else 50.0


def calc_ma(prices: pd.Series, n: int) -> float:
    val = prices.rolling(n).mean().iloc[-1]
    return round(float(val), 3) if not pd.isna(val) else round(float(prices.iloc[-1]), 3)


def signal_and_reason(rsi: float, price: float, ma20: float, ma50: float,
                      lo52: float, hi52: float, upside: float) -> tuple[str, str]:
    reasons = []

    if rsi < 30:
        signal = "COMPRAR"
        reasons.append(f"RSI={rsi} sobrevenut")
    elif rsi < 40:
        signal = "VIGILAR ↑"
        reasons.append(f"RSI={rsi} proper a zona de compra")
    elif rsi > 70:
        signal = "VENDRE"
        reasons.append(f"RSI={rsi} sobrecomprat")
    elif rsi > 60:
        signal = "VIGILAR ↓"
        reasons.append(f"RSI={rsi} proper a zona de venda")
    else:
        signal = "MANTENIR"

    if hi52 > 0 and price >= hi52 * 0.97:
        reasons.append("proper al màxim 52S")
        if signal == "MANTENIR":
            signal = "VIGILAR ↓"
    if lo52 > 0 and price <= lo52 * 1.05:
        reasons.append("proper al mínim 52S")
        if signal == "MANTENIR":
            signal = "VIGILAR ↑"

    if price < ma20 and price < ma50:
        reasons.append("per sota MA20 i MA50")
        if signal == "MANTENIR":
            signal = "VIGILAR ↓"
    elif price > ma20 and price > ma50:
        reasons.append("per sobre MA20 i MA50")

    if upside > 25 and signal == "MANTENIR":
        signal = "VIGILAR ↑"
        reasons.append(f"upside analistes +{upside}%")

    return signal, "; ".join(reasons) if reasons else "sense senyals especials"


def build_alerts(tick: str, name: str, rsi: float, price: float,
                 lo52: float, hi52: float, pnl_pct: float,
                 upside: float, earnings_days: int | None) -> list[dict]:
    alerts = []

    if rsi < 30:
        alerts.append({"tick": tick, "priority": "ALTA",
                        "msg": f"🟢 {tick} ({name}): RSI={rsi} — zona de sobrevendes. Possible oportunitat de compra."})
    elif rsi > 70:
        alerts.append({"tick": tick, "priority": "ALTA",
                        "msg": f"🔴 {tick} ({name}): RSI={rsi} — zona de sobrecompra. Considera reduir posició."})

    if hi52 > 0 and price >= hi52 * 0.98:
        alerts.append({"tick": tick, "priority": "MITJA",
                        "msg": f"⚠️ {tick} ({name}): Proper al màxim de 52 setmanes ({hi52:.2f}). Resistència important."})

    if lo52 > 0 and price <= lo52 * 1.03:
        alerts.append({"tick": tick, "priority": "ALTA",
                        "msg": f"🟡 {tick} ({name}): Proper al mínim de 52 setmanes ({lo52:.2f}). Zona de suport clau."})

    if pnl_pct < -15:
        alerts.append({"tick": tick, "priority": "MITJA",
                        "msg": f"📉 {tick} ({name}): Pèrdua acumulada del {pnl_pct:.1f}%. Revisa la tesi d'inversió."})

    if upside > 30:
        alerts.append({"tick": tick, "priority": "MITJA",
                        "msg": f"📈 {tick} ({name}): Upside dels analistes del +{upside:.1f}%. Considera augmentar posició."})

    if earnings_days is not None and 0 <= earnings_days <= 7:
        alerts.append({"tick": tick, "priority": "ALTA",
                        "msg": f"📅 {tick} ({name}): Resultats en {earnings_days} dies. Alta volatilitat esperada."})

    return alerts


def main():
    try:
        with open("data.json", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("ERROR: data.json no trobat. Executa primer fetch_data.py", file=sys.stderr)
        sys.exit(1)

    holdings  = data["holdings"]
    eurusd    = data.get("eurusd", 1.095)
    earn_map  = {e["tick"]: e["days"] for e in data.get("earnings", [])}

    total_value_eur = data.get("cash", 0)
    total_capital   = data.get("capital", 6500.0)
    analyzed        = []
    all_alerts      = []

    for h in holdings:
        tick    = h["tick"]
        yf_tick = h.get("yf", tick)
        print(f"  Analitzant {tick}...", end=" ", flush=True)

        try:
            hist   = yf.Ticker(yf_tick).history(period="3mo", interval="1d", auto_adjust=True)
            prices = hist["Close"].dropna()
            rsi  = calc_rsi(prices)       if len(prices) >= 15 else 50.0
            ma20 = calc_ma(prices, 20)    if len(prices) >= 20 else h["price"]
            ma50 = calc_ma(prices, 50)    if len(prices) >= 50 else h["price"]
        except Exception as e:
            print(f"(fetch error: {e})", end=" ", file=sys.stderr)
            rsi, ma20, ma50 = 50.0, h["price"], h["price"]

        price   = h["price"]
        qty     = h["qty"]
        entrada = h["entrada"]
        cur     = h["cur"]

        value_eur = (qty * price) / eurusd if cur == "USD" else qty * price
        cost_eur  = (qty * entrada) / eurusd if cur == "USD" else qty * entrada
        pnl_eur   = round(value_eur - cost_eur, 2)
        pnl_pct   = round((price - entrada) / entrada * 100, 2) if entrada else 0
        total_value_eur += value_eur

        lo52   = h.get("lo52", 0)
        hi52   = h.get("hi52", 0)
        upside = h.get("upside", 0)

        signal, reason = signal_and_reason(rsi, price, ma20, ma50, lo52, hi52, upside)
        alerts = build_alerts(tick, h["name"], rsi, price, lo52, hi52,
                              pnl_pct, upside, earn_map.get(tick))
        all_alerts.extend(alerts)

        analyzed.append({
            **h,
            "rsi":          rsi,
            "ma20":         round(ma20, 2),
            "ma50":         round(ma50, 2),
            "signal":       signal,
            "signal_reason": reason,
            "pnl_pct":      pnl_pct,
            "pnl_eur":      pnl_eur,
            "value_eur":    round(value_eur, 2),
        })
        print(f"RSI={rsi} | {signal}")

    priority_order = {"ALTA": 0, "MITJA": 1, "BAIXA": 2}
    all_alerts.sort(key=lambda a: priority_order.get(a["priority"], 3))

    total_pnl_eur = round(total_value_eur - total_capital, 2)
    total_pnl_pct = round(total_pnl_eur / total_capital * 100, 2) if total_capital else 0

    output = {
        "generated": date.today().strftime("%d/%m/%Y"),
        "lastUpdate": data.get("lastUpdate", ""),
        "eurusd":  eurusd,
        "portfolio_summary": {
            "total_value_eur": round(total_value_eur, 2),
            "total_capital":   total_capital,
            "total_pnl_eur":   total_pnl_eur,
            "total_pnl_pct":   total_pnl_pct,
            "cash":            data.get("cash", 0),
            "sp500_ytd":       data.get("benchmarks", {}).get("sp500Ytd", 0),
            "ibex_ytd":        data.get("benchmarks", {}).get("ibexYtd", 0),
        },
        "holdings": analyzed,
        "alerts":   all_alerts,
        "news":     data.get("news", []),
        "earnings": data.get("earnings", []),
    }

    with open("analysis.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    n_high = sum(1 for a in all_alerts if a["priority"] == "ALTA")
    print(f"\nanalysis.json guardat — {len(all_alerts)} alertes ({n_high} altes)")


if __name__ == "__main__":
    print("INVEX — Analitzant portafoli...")
    main()
