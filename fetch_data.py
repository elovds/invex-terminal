"""
INVEX Terminal — fetch_data.py
Obté preus, YTD i historial mensual via yfinance i guarda data.json.
"""
import json
import sys
from datetime import date, datetime

import pandas as pd
import yfinance as yf

# ── Configuració del portafoli ────────────────────────────────────────────────
PORTFOLIO = [
    {"tick": "GOOGL", "name": "Alphabet Inc.",   "qty": 6,   "entrada": 312.0, "cur": "USD", "color": "4da6ff", "yf": "GOOGL"},
    {"tick": "AAPL",  "name": "Apple Inc.",       "qty": 5,   "entrada": 246.0, "cur": "USD", "color": "8b95a8", "yf": "AAPL"},
    {"tick": "MSFT",  "name": "Microsoft Corp.",  "qty": 6,   "entrada": 477.0, "cur": "USD", "color": "a78bfa", "yf": "MSFT"},
    {"tick": "SAN",   "name": "Banco Santander",  "qty": 150, "entrada": 7.70,  "cur": "EUR", "color": "00e5a0", "yf": "SAN.MC"},
]
CASH    = 237.91
CAPITAL = 6500.0

MONTHS_CA = ["Gen","Feb","Mar","Abr","Mai","Jun","Jul","Ago","Set","Oct","Nov","Des"]
YEAR      = date.today().year
YEAR_START = f"{YEAR}-01-01"

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe(val, default=0, digits=2):
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return round(float(val), digits)
    except Exception:
        return default

def year_start_price(hist: pd.DataFrame) -> float:
    """Primer preu de tancament de l'any."""
    if hist.empty:
        return None
    return float(hist["Close"].iloc[0])

def ytd_monthly(hist: pd.DataFrame, p0: float) -> list:
    """
    Retorna llista de YTD% al tancament de cada mes complet + valor actual.
    Sempre comença amb [0, ...].
    """
    if hist.empty or p0 is None or p0 == 0:
        return [0]
    today = date.today()
    # Resample mensual: últim tancament de cada mes
    monthly = hist["Close"].resample("ME").last().dropna()
    result = [0.0]
    for ts, price in monthly.items():
        month_end = ts.date()
        # Ignora el mes actual si no ha acabat
        if month_end.year == today.year and month_end.month >= today.month:
            continue
        result.append(round((price - p0) / p0 * 100, 2))
    # Afegeix valor actual (mes en curs)
    last_price = float(hist["Close"].iloc[-1])
    result.append(round((last_price - p0) / p0 * 100, 2))
    return result

def recommendation_label(key: str) -> str:
    key = (key or "").lower()
    if key in ("strong_buy", "strongbuy"):  return "Strong Buy"
    if key == "buy":                         return "Buy"
    if key == "hold":                        return "Hold"
    if key in ("sell", "underperform"):      return "Sell"
    return "—"

def get_buys(ticker: yf.Ticker, n_analysts: int) -> int:
    try:
        rec = ticker.recommendations
        if rec is not None and not rec.empty:
            last = rec.tail(1)
            sb = int(last.get("strongBuy",  pd.Series([0])).values[0])
            b  = int(last.get("buy",        pd.Series([0])).values[0])
            if sb + b > 0:
                return sb + b
    except Exception:
        pass
    return max(1, int(n_analysts * 0.75))

def fetch_news(ticker: yf.Ticker, tick: str, n: int = 3) -> list:
    try:
        items = ticker.news or []
        out = []
        for item in items[:n]:
            c = item.get("content", {})
            title = c.get("title") or item.get("title", "")
            pub   = c.get("pubDate") or item.get("providerPublishTime")
            if not title:
                continue
            if isinstance(pub, (int, float)):
                pub = datetime.utcfromtimestamp(pub).strftime("%d/%m/%Y")
            elif isinstance(pub, str):
                try:
                    pub = datetime.fromisoformat(pub.replace("Z","")).strftime("%d/%m/%Y")
                except Exception:
                    pub = str(pub)[:10]
            else:
                pub = date.today().strftime("%d/%m/%Y")
            out.append({"tick": tick, "text": title, "date": pub})
        return out
    except Exception:
        return []

def fetch_earnings(ticker: yf.Ticker, tick: str) -> dict | None:
    try:
        cal = ticker.calendar
        if cal is None:
            return None
        earn = cal.get("Earnings Date")
        if earn is None:
            return None
        if isinstance(earn, (list, tuple)) and earn:
            earn = earn[0]
        if hasattr(earn, "date"):
            earn = earn.date()
        elif isinstance(earn, str):
            earn = datetime.fromisoformat(earn).date()
        days = (earn - date.today()).days
        if days < 0:
            return None
        return {"tick": tick, "date": earn.strftime("%d/%m/%Y"), "days": days}
    except Exception:
        return None

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today_str = date.today().strftime("%d/%m/%Y")

    # EUR/USD
    try:
        eurusd = safe(yf.Ticker("EURUSD=X").fast_info["lastPrice"], 1.095, 4)
    except Exception:
        eurusd = 1.095

    holdings_out = []
    mensual      = {}
    all_news     = []
    earnings_out = []

    for cfg in PORTFOLIO:
        yf_tick = cfg["yf"]
        print(f"  Fetching {yf_tick}...", end=" ", flush=True)
        try:
            t    = yf.Ticker(yf_tick)
            info = t.info

            # Preu actual
            price = safe(
                t.fast_info.get("lastPrice")
                or info.get("currentPrice")
                or info.get("regularMarketPrice"),
                cfg["entrada"]
            )

            # Historial anual (diari per resampling mensual precís)
            hist = t.history(start=YEAR_START, auto_adjust=True)
            p0   = year_start_price(hist) or cfg["entrada"]
            monthly_vals = ytd_monthly(hist, p0)
            mensual[cfg["tick"]] = monthly_vals

            # Fonamentals
            fpe     = info.get("forwardPE")
            margins = info.get("operatingMargins")
            divy    = info.get("dividendYield")
            lo52    = safe(info.get("fiftyTwoWeekLow"), 0)
            hi52    = safe(info.get("fiftyTwoWeekHigh"), 0)
            target  = safe(info.get("targetMeanPrice"), 0)
            n_anal  = int(info.get("numberOfAnalystOpinions") or 0)
            rating  = recommendation_label(info.get("recommendationKey", ""))
            buys    = get_buys(t, n_anal)

            cur_sym = "$" if cfg["cur"] == "USD" else "€"
            upside  = round((target - price) / price * 100, 1) if target > 0 and price > 0 else 0

            holdings_out.append({
                "tick":     cfg["tick"],
                "name":     cfg["name"],
                "qty":      cfg["qty"],
                "entrada":  cfg["entrada"],
                "price":    price,
                "cur":      cfg["cur"],
                "color":    cfg["color"],
                "pe":       f"{round(fpe,1)}x"           if fpe     else "—",
                "margin":   f"{round(margins*100,1)}%"   if margins else "—",
                "div":      f"{round(divy*100,2)}%"      if divy    else "0%",
                "lo52":     lo52,
                "hi52":     hi52,
                "rating":   rating,
                "target":   f"{cur_sym}{round(target,0):.0f}" if target > 0 else "—",
                "analysts": n_anal,
                "buys":     buys,
                "upside":   upside,
            })

            # Notícies
            all_news.extend(fetch_news(t, cfg["tick"], n=2))

            # Resultats
            earn = fetch_earnings(t, cfg["tick"])
            if earn:
                earnings_out.append(earn)

            print("OK")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            # Fallback mínim
            holdings_out.append({**cfg, "price": cfg["entrada"], "pe": "—",
                "margin": "—", "div": "—", "lo52": 0, "hi52": 0,
                "rating": "—", "target": "—", "analysts": 0, "buys": 0, "upside": 0})
            mensual[cfg["tick"]] = [0]

    # Benchmarks
    BENCHMARKS = {"SP500": "^GSPC", "IBEX35": "^IBEX"}
    benchmarks = {}
    for name, yf_tick in BENCHMARKS.items():
        print(f"  Fetching {name}...", end=" ", flush=True)
        try:
            t    = yf.Ticker(yf_tick)
            hist = t.history(start=YEAR_START, auto_adjust=True)
            p0   = year_start_price(hist) or 1
            last = float(hist["Close"].iloc[-1]) if not hist.empty else p0
            ytd  = round((last - p0) / p0 * 100, 2)
            monthly_vals = ytd_monthly(hist, p0)
            benchmarks[name] = {"ytd": ytd, "monthly": monthly_vals}
            mensual[name]    = monthly_vals
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            benchmarks[name] = {"ytd": 0, "monthly": [0]}
            mensual[name]    = [0]

    # Portafoli mensual (mitjana ponderada pels pesos actuals)
    try:
        eurusd_calc = eurusd
        vals  = []
        wgts  = []
        for h in holdings_out:
            v = h["qty"] * h["price"]
            v_eur = v / eurusd_calc if h["cur"] == "USD" else v
            wgts.append(v_eur)
            vals.append(mensual.get(h["tick"], [0]))
        total_w  = sum(wgts)
        max_len  = max(len(v) for v in vals)
        pf_monthly = []
        for i in range(max_len):
            w_sum = 0.0
            for j, v in enumerate(vals):
                val_i = v[i] if i < len(v) else (v[-1] if v else 0)
                if val_i is None:
                    val_i = 0
                w_sum += val_i * (wgts[j] / total_w if total_w else 0)
            pf_monthly.append(round(w_sum, 2))
        mensual["Portafoli"] = pf_monthly
    except Exception as e:
        print(f"  Warning: no s'ha pogut calcular Portafoli mensual: {e}", file=sys.stderr)
        mensual["Portafoli"] = [0]

    # Ordenar earnings per dies
    earnings_out.sort(key=lambda x: x["days"])

    # Nombre de mesos (per eix X del gràfic)
    n_mesos = max((len(v) for v in mensual.values()), default=1)

    output = {
        "lastUpdate": today_str,
        "eurusd":     eurusd,
        "cash":       CASH,
        "capital":    CAPITAL,
        "nMesos":     n_mesos,
        "benchmarks": {
            "sp500Ytd": benchmarks.get("SP500",  {}).get("ytd", 0),
            "ibexYtd":  benchmarks.get("IBEX35", {}).get("ytd", 0),
        },
        "holdings": holdings_out,
        "mensual":  mensual,
        "earnings": earnings_out,
        "news":     all_news,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\ndata.json guardat — {len(holdings_out)} posicions, {len(earnings_out)} earnings, {len(all_news)} notícies")

if __name__ == "__main__":
    print("INVEX — Actualitzant dades de mercat...")
    main()
