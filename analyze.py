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
                 upside: float, earnings_days: int | None,
                 ma20: float = 0, ma50: float = 0,
                 cur: str = "USD", rating: str = "", analysts: int = 0) -> list[dict]:
    alerts = []
    cur_sym = "$" if cur == "USD" else "€"
    dist_hi = round((price / hi52 - 1) * 100, 1) if hi52 > 0 else 0
    dist_lo = round((price / lo52 - 1) * 100, 1) if lo52 > 0 else 0

    if rsi < 30:
        alerts.append({"tick": tick, "priority": "ALTA", "msg": (
            f"🟢 {tick} — {name} | OPORTUNITAT DE COMPRA\n"
            f"RSI actual: {rsi} (per sota de 30 = sobrevenut tècnicament).\n"
            f"Preu actual: {cur_sym}{price:.2f} | MA20: {cur_sym}{ma20:.2f} | MA50: {cur_sym}{ma50:.2f}\n"
            f"Rang 52S: {cur_sym}{lo52:.2f} – {cur_sym}{hi52:.2f}\n"
            f"Consens analistes: {rating} ({analysts} analistes) | Upside: +{upside:.1f}%\n"
            f"Acció suggerida: Considera obrir o augmentar posició. RSI<30 sovint precedeix recuperació."
        )})
    elif rsi > 70:
        alerts.append({"tick": tick, "priority": "ALTA", "msg": (
            f"🔴 {tick} — {name} | ZONA DE SOBRECOMPRA\n"
            f"RSI actual: {rsi} (per sobre de 70 = sobrecomprat tècnicament).\n"
            f"Preu actual: {cur_sym}{price:.2f} | MA20: {cur_sym}{ma20:.2f} | MA50: {cur_sym}{ma50:.2f}\n"
            f"P&L posició actual: {'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%\n"
            f"Acció suggerida: Considera reduir posició o posar stop-loss per protegir guanys."
        )})

    if hi52 > 0 and price >= hi52 * 0.98:
        alerts.append({"tick": tick, "priority": "MITJA", "msg": (
            f"⚠️ {tick} — {name} | PROPER AL MÀXIM DE 52 SETMANES\n"
            f"Preu: {cur_sym}{price:.2f} | Màxim 52S: {cur_sym}{hi52:.2f} (a {abs(dist_hi):.1f}% del màxim).\n"
            f"Aquesta zona és una resistència tècnica forta. El preu pot rebotar a la baixa.\n"
            f"Acció suggerida: Vigila el volum. Si trenca el màxim amb força, pot continuar pujant. "
            f"Si no, considera recollir beneficis parcialment."
        )})

    if lo52 > 0 and price <= lo52 * 1.03:
        alerts.append({"tick": tick, "priority": "ALTA", "msg": (
            f"🟡 {tick} — {name} | PROPER AL MÍNIM DE 52 SETMANES\n"
            f"Preu: {cur_sym}{price:.2f} | Mínim 52S: {cur_sym}{lo52:.2f} (a {dist_lo:.1f}% del mínim).\n"
            f"Zona de suport clau. Si el preu la trenca a la baixa, podria caure més.\n"
            f"Acció suggerida: Revisa la tesi d'inversió. Si els fonamentals segueixen forts, "
            f"pot ser una oportunitat. Si no, considera tallar pèrdues."
        )})

    if pnl_pct < -15:
        alerts.append({"tick": tick, "priority": "MITJA", "msg": (
            f"📉 {tick} — {name} | PÈRDUA SIGNIFICATIVA\n"
            f"P&L actual: {pnl_pct:.1f}% des del preu d'entrada.\n"
            f"Preu actual: {cur_sym}{price:.2f} | Preu d'entrada: referència inicial\n"
            f"Consens analistes: {rating} ({analysts} analistes) | Upside objectiu: +{upside:.1f}%\n"
            f"Acció suggerida: Avalua si la raó original de la compra segueix vigent. "
            f"Si els analistes mantenen target i els fonamentals no han canviat, pot ser paciència. "
            f"Si no, considera limitar pèrdues."
        )})

    if upside > 30:
        alerts.append({"tick": tick, "priority": "MITJA", "msg": (
            f"📈 {tick} — {name} | UPSIDE ELEVAT SEGONS ANALISTES\n"
            f"Objectiu de preu consens: upside del +{upside:.1f}% respecte al preu actual.\n"
            f"Preu actual: {cur_sym}{price:.2f} | Rating consens: {rating} ({analysts} analistes)\n"
            f"RSI: {rsi} | MA20: {cur_sym}{ma20:.2f} | MA50: {cur_sym}{ma50:.2f}\n"
            f"Acció suggerida: Considera augmentar posició si el RSI no és sobrecomprat "
            f"i els fonamentals ho suporten."
        )})

    if earnings_days is not None and 0 <= earnings_days <= 7:
        alerts.append({"tick": tick, "priority": "ALTA", "msg": (
            f"📅 {tick} — {name} | RESULTATS TRIMESTRALS EN {earnings_days} DIES\n"
            f"Preu actual: {cur_sym}{price:.2f} | P&L posició: {'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%\n"
            f"Els earnings poden generar moviments bruscos del ±5-15%.\n"
            f"Acció suggerida: Decideix si vols mantenir la posició sencera durant els resultats "
            f"o reduir parcialment per gestionar el risc de volatilitat."
        )})

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
                              pnl_pct, upside, earn_map.get(tick),
                              ma20=ma20, ma50=ma50, cur=cur,
                              rating=h.get("rating", ""), analysts=h.get("analysts", 0))
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
