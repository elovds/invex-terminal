"""
INVEX Terminal — send_report.py
Envia informes per email via Gmail SMTP.
  --mode alert   → envia email breu NOMÉS si hi ha alertes d'alta prioritat
  --mode weekly  → envia sempre l'informe complet setmanal
"""
import argparse
import json
import os
import smtplib
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RECIPIENT = "evilagrands@gmail.com"
SENDER    = os.environ.get("GMAIL_USER", "")
PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")

SIGNAL_COLORS = {
    "COMPRAR":   "#00e5a0",
    "VENDRE":    "#ff4d4d",
    "VIGILAR ↑": "#ffd700",
    "VIGILAR ↓": "#ff8c00",
    "MANTENIR":  "#8b95a8",
}

BASE_CSS = """
body{margin:0;padding:0;background:#0d1117;font-family:'Segoe UI',Arial,sans-serif;color:#e6edf3}
.wrap{max-width:720px;margin:0 auto;padding:24px}
.header{text-align:center;padding:32px 0 20px}
.header h1{color:#4da6ff;font-size:26px;margin:0 0 4px;letter-spacing:2px}
.header p{color:#8b95a8;font-size:13px;margin:0}
.sec{margin:24px 0}
.sec-title{color:#4da6ff;font-size:13px;font-weight:700;border-bottom:1px solid #21262d;
  padding-bottom:8px;margin-bottom:14px;letter-spacing:1px;text-transform:uppercase}
table{width:100%;border-collapse:collapse}
th{background:#161b22;color:#8b95a8;font-size:11px;padding:9px 10px;text-align:left}
td{padding:9px 10px;border-bottom:1px solid #21262d;font-size:13px;vertical-align:top}
.abox{padding:11px 14px;border-radius:6px;margin-bottom:9px;border-left:4px solid}
.alta{background:#200a0a;border-color:#ff4d4d}
.mitja{background:#1a1400;border-color:#ffd700}
.kpi{display:inline-block;background:#161b22;border-radius:8px;padding:14px 20px;
  margin:5px;min-width:130px;text-align:center}
.kv{font-size:22px;font-weight:700;margin:4px 0}
.kl{font-size:11px;color:#8b95a8}
.foot{text-align:center;color:#3d444d;font-size:11px;padding:24px 0}
"""


def load_analysis() -> dict:
    try:
        with open("analysis.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("ERROR: analysis.json no trobat. Executa primer analyze.py", file=sys.stderr)
        sys.exit(1)


def send_email(subject: str, html: str):
    if not SENDER or not PASSWORD:
        print("ERROR: GMAIL_USER o GMAIL_APP_PASSWORD no configurats", file=sys.stderr)
        sys.exit(1)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"INVEX Terminal <{SENDER}>"
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.ehlo()
        s.starttls()
        s.login(SENDER, PASSWORD)
        s.sendmail(SENDER, RECIPIENT, msg.as_string())
    print(f"✓ Email enviat: {subject}")


def color_val(v: float, pos_color="#00e5a0", neg_color="#ff4d4d") -> str:
    return pos_color if v >= 0 else neg_color


def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    c = color_val(v)
    return f'<span style="color:{c}">{sign}{v:.2f}%</span>'


def fmt_eur(v: float) -> str:
    sign = "+" if v >= 0 else ""
    c = color_val(v)
    return f'<span style="color:{c}">{sign}{v:.0f} €</span>'


# ── Alert email ────────────────────────────────────────────────────────────────

def build_alert_html(data: dict) -> str:
    alerts  = data["alerts"]
    summary = data["portfolio_summary"]
    today   = date.today().strftime("%d/%m/%Y")

    boxes = "".join(
        f'<div class="abox {a["priority"].lower()}">{a["msg"]}</div>'
        for a in alerts
    )

    pnl_color = color_val(summary["total_pnl_eur"])

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>{BASE_CSS}</style></head>
<body><div class="wrap">
  <div class="header">
    <h1>⚡ INVEX ALERTES</h1>
    <p>{today} — Senyals importants detectats</p>
  </div>

  <div class="sec">
    <div class="sec-title">Estat del Portafoli</div>
    <table><tr>
      <td>Valor total</td>
      <td><b>{summary['total_value_eur']:.0f} €</b></td>
      <td>P&amp;L total</td>
      <td><b style="color:{pnl_color}">
        {'+' if summary['total_pnl_eur']>=0 else ''}{summary['total_pnl_eur']:.0f} €
        ({'+' if summary['total_pnl_pct']>=0 else ''}{summary['total_pnl_pct']:.2f}%)
      </b></td>
    </tr></table>
  </div>

  <div class="sec">
    <div class="sec-title">🚨 Alertes ({len(alerts)})</div>
    {boxes}
  </div>

  <div class="foot">INVEX Terminal — Generat automàticament · No és assessorament financer</div>
</div></body></html>"""


# ── Weekly report ──────────────────────────────────────────────────────────────

def build_weekly_html(data: dict) -> str:
    summary  = data["portfolio_summary"]
    holdings = data["holdings"]
    alerts   = data["alerts"]
    news     = data["news"]
    earnings = data["earnings"]
    today    = date.today().strftime("%d/%m/%Y")
    week_num = date.today().isocalendar()[1]

    # KPIs
    pnl_color  = color_val(summary["total_pnl_eur"])
    sp_color   = color_val(summary["sp500_ytd"])
    ibex_color = color_val(summary["ibex_ytd"])

    kpis = f"""
    <div class="kpi">
      <div class="kl">VALOR TOTAL</div>
      <div class="kv">{summary['total_value_eur']:.0f} €</div>
    </div>
    <div class="kpi">
      <div class="kl">P&amp;L TOTAL</div>
      <div class="kv" style="color:{pnl_color}">
        {'+' if summary['total_pnl_eur']>=0 else ''}{summary['total_pnl_eur']:.0f} €
      </div>
      <div style="font-size:11px;color:#8b95a8">
        {'+' if summary['total_pnl_pct']>=0 else ''}{summary['total_pnl_pct']:.2f}%
      </div>
    </div>
    <div class="kpi">
      <div class="kl">S&amp;P 500 YTD</div>
      <div class="kv" style="color:{sp_color}">
        {'+' if summary['sp500_ytd']>=0 else ''}{summary['sp500_ytd']:.2f}%
      </div>
    </div>
    <div class="kpi">
      <div class="kl">IBEX 35 YTD</div>
      <div class="kv" style="color:{ibex_color}">
        {'+' if summary['ibex_ytd']>=0 else ''}{summary['ibex_ytd']:.2f}%
      </div>
    </div>"""

    # Holdings table
    rows = ""
    for h in holdings:
        cur_sym   = "$" if h["cur"] == "USD" else "€"
        sig_color = SIGNAL_COLORS.get(h["signal"], "#8b95a8")
        rows += f"""<tr>
          <td>
            <b style="color:#{h['color']}">{h['tick']}</b><br>
            <small style="color:#8b95a8">{h['name']}</small>
          </td>
          <td>{cur_sym}{h['price']:.2f}</td>
          <td>{fmt_pct(h['pnl_pct'])}</td>
          <td>{fmt_eur(h['pnl_eur'])}</td>
          <td style="font-size:12px">
            RSI: <b>{h['rsi']}</b><br>
            MA20: {cur_sym}{h['ma20']}<br>
            MA50: {cur_sym}{h['ma50']}
          </td>
          <td><b style="color:{sig_color}">{h['signal']}</b></td>
          <td style="color:#8b95a8;font-size:11px">{h.get('signal_reason','')}</td>
        </tr>"""

    # Alerts
    if alerts:
        alert_html = "".join(
            f'<div class="abox {a["priority"].lower()}">{a["msg"]}</div>'
            for a in alerts[:12]
        )
    else:
        alert_html = '<p style="color:#8b95a8">Sense alertes destacades aquesta setmana.</p>'

    # Fundamentals
    fund_rows = "".join(f"""<tr>
      <td style="color:#{h['color']};font-weight:600">{h['tick']}</td>
      <td>{h.get('rating','—')}</td>
      <td>{h.get('target','—')}</td>
      <td>{fmt_pct(h['upside']) if h.get('upside') else '—'}</td>
      <td>{h.get('pe','—')}</td>
      <td>{h.get('div','—')}</td>
      <td>{h.get('analysts','—')}</td>
    </tr>""" for h in holdings)

    # Earnings
    if earnings:
        earn_rows = "".join(f"""<tr>
          <td style="color:#4da6ff">{e['tick']}</td>
          <td>{e['date']}</td>
          <td style="color:#ffd700">{e['days']} dies</td>
        </tr>""" for e in earnings[:5])
    else:
        earn_rows = '<tr><td colspan="3" style="color:#8b95a8">Sense resultats propers</td></tr>'

    # News
    news_html = ""
    if news:
        news_rows = "".join(f"""<tr>
          <td style="color:#4da6ff;width:55px">{n['tick']}</td>
          <td>{n['text']}</td>
          <td style="color:#8b95a8;width:85px;font-size:11px">{n['date']}</td>
        </tr>""" for n in news[:8])
        news_html = f"""
        <div class="sec">
          <div class="sec-title">📰 Notícies Recents</div>
          <table>{news_rows}</table>
        </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>{BASE_CSS}</style></head>
<body><div class="wrap">

  <div class="header">
    <h1>📊 INVEX INFORME SETMANAL</h1>
    <p>Setmana {week_num} · {today}</p>
  </div>

  <div class="sec" style="text-align:center">{kpis}</div>

  <div class="sec">
    <div class="sec-title">Posicions i Senyals Tècnics</div>
    <table>
      <tr>
        <th>Actiu</th><th>Preu</th><th>P&amp;L%</th><th>P&amp;L €</th>
        <th>Tècnic</th><th>Senyal</th><th>Raó</th>
      </tr>
      {rows}
    </table>
  </div>

  <div class="sec">
    <div class="sec-title">📋 Fonamentals i Consens Analistes</div>
    <table>
      <tr><th>Actiu</th><th>Rating</th><th>Target</th><th>Upside</th>
          <th>PER</th><th>Div.</th><th>Analistes</th></tr>
      {fund_rows}
    </table>
  </div>

  <div class="sec">
    <div class="sec-title">🚨 Alertes i Recomanacions</div>
    {alert_html}
  </div>

  <div class="sec">
    <div class="sec-title">📅 Resultats Propers (Earnings)</div>
    <table>
      <tr><th>Ticker</th><th>Data</th><th>Dies restants</th></tr>
      {earn_rows}
    </table>
  </div>

  {news_html}

  <div class="foot">
    INVEX Terminal · Informe setmanal automàtic cada dilluns<br>
    Dades: Yahoo Finance (retard màxim 15 min) · No és assessorament financer
  </div>
</div></body></html>"""


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["alert", "weekly"], required=True)
    args = parser.parse_args()

    data = load_analysis()

    if args.mode == "alert":
        high_alerts = [a for a in data.get("alerts", []) if a["priority"] == "ALTA"]
        if not high_alerts:
            print("Sense alertes d'alta prioritat avui. No s'envia email.")
            return
        subject = (f"⚡ INVEX Alertes — {len(high_alerts)} senyals importants "
                   f"({date.today().strftime('%d/%m/%Y')})")
        html = build_alert_html(data)
    else:
        subject = f"📊 INVEX Informe Setmanal — {date.today().strftime('%d/%m/%Y')}"
        html = build_weekly_html(data)

    send_email(subject, html)


if __name__ == "__main__":
    main()
