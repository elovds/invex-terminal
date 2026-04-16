# INVEX Terminal v3.0

Dashboard financer personal amb dades de mercat automàtiques via **yfinance** i desplegament a **GitHub Pages**.

## Arquitectura

```
invex-terminal.html   ← Dashboard (llegeix data.json via fetch)
fetch_data.py         ← Script Python que obté preus de yfinance
data.json             ← Dades de mercat (actualitzades automàticament)
cartera.xlsx          ← Excel per sobreescriure les dades manualment
.github/workflows/
  update.yml          ← GitHub Actions: executa fetch_data.py cada dia feiner
```

## Posicions configurades

| Ticker | Nom | Quantitat | Preu entrada |
|--------|-----|-----------|-------------|
| GOOGL  | Alphabet Inc.   | 6   | $312.00 |
| AAPL   | Apple Inc.      | 5   | $246.00 |
| MSFT   | Microsoft Corp. | 6   | $477.00 |
| SAN.MC | Banco Santander | 150 | €7.70   |

Per canviar les posicions, edita la variable `PORTFOLIO` a `fetch_data.py`.

---

## Ús local

### Requisits

```bash
pip install yfinance pandas
```

### Actualitzar dades i obrir el dashboard

```bash
python fetch_data.py          # genera/actualitza data.json
python -m http.server 8080    # servidor local
# obre http://localhost:8080/invex-terminal.html
```

O simplement fes doble clic a **`INICIAR-INVEX.bat`** (Windows).

---

## Desplegament a GitHub Pages

### 1. Crea el repositori

```bash
git init
git add invex-terminal.html fetch_data.py data.json .github/
git commit -m "Initial commit: INVEX Terminal v3.0"
```

Crea un repositori nou a GitHub (per exemple `invex-terminal`) i puja el codi:

```bash
git remote add origin https://github.com/EL-TEU-USUARI/invex-terminal.git
git branch -M main
git push -u origin main
```

### 2. Activa GitHub Pages

1. Ves a **Settings → Pages** del teu repositori
2. A **Source**, selecciona `Deploy from a branch`
3. Tria la branca `main` i la carpeta `/ (root)`
4. Clica **Save**

El dashboard quedarà disponible a:
```
https://EL-TEU-USUARI.github.io/invex-terminal/invex-terminal.html
```

### 3. Activa permisos per a GitHub Actions

A **Settings → Actions → General → Workflow permissions**:
- Selecciona **Read and write permissions**
- Guarda els canvis

Això permet que el workflow pugui fer commit de `data.json` automàticament.

### 4. Verifica que el workflow funciona

Ves a **Actions → Update market data** i clica **Run workflow** per provar-lo manualment. Si tot va bé, s'executarà automàticament cada dia feiner a les 8h UTC.

---

## Com afegir noves posicions

1. Edita `fetch_data.py` i afegeix una entrada a `PORTFOLIO`:

```python
{"tick": "NVDA", "name": "NVIDIA Corp.", "qty": 3, "entrada": 450.0, "cur": "USD", "color": "76b900", "yf": "NVDA"},
```

2. Executa `python fetch_data.py` localment per generar un nou `data.json`.
3. Fes commit i push — el workflow s'encarregarà de les actualitzacions diàries.

## Sobreescriure dades manualment (via Excel)

Si vols actualitzar ratings d'analistes, notícies o qualsevol dada que yfinance no proporciona:

1. Obre `cartera.xlsx`
2. Edita les fulles corresponents
3. Al dashboard, clica **Carregar Excel** i selecciona `cartera.xlsx`

Les dades de l'Excel sobreescriuen les del `data.json` per a aquella sessió.

---

## Notes

- Els preus s'obtenen de Yahoo Finance via `yfinance`. Poden tenir un retard de 15 minuts.
- Els ratings d'analistes i targets de preu provenen de Yahoo Finance i poden diferir d'altres fonts.
- El `data.json` inclós al repositori és públic — no hi posis dades sensibles.
