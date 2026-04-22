import math
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Reliable CSP Screener", layout="wide")
st.title("🏆 Reliable CSP Opportunity Screener")

# =========================================================
# INPUT
# =========================================================
ticker_str = st.text_area(
    "Tickers (keep to 4–10)",
    "NVDA, MSFT, AAPL, AMZN, META, AVGO"
)

tickers = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]

otm_target = st.slider("Target OTM %", 2, 15, 6)
dte = st.slider("Days to Expiration (approx)", 5, 14, 7)

# =========================================================
# HELPERS
# =========================================================
def annualize(x, dte):
    return x * (365 / dte)

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

# =========================================================
# FETCH PRICE DATA (ROBUST)
# =========================================================
@st.cache_data(ttl=300)
def fetch_data(tickers):
    data = yf.download(
        tickers,
        period="3mo",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False
    )
    return data

data = fetch_data(tickers)

# =========================================================
# BUILD SCREEN
# =========================================================
rows = []

for t in tickers:
    try:
        df = data[t] if len(tickers) > 1 else data

        if "Close" not in df:
            continue

        close = df["Close"].dropna()

        if len(close) < 25:
            continue

        spot = float(close.iloc[-1])

        # realized vol (proxy)
        hv20 = close.pct_change().dropna().tail(20).std() * math.sqrt(252)

        # target strike
        strike = spot * (1 - otm_target / 100)

        # simple premium model:
        # premium ~ IV * sqrt(time) * price * scaling factor
        iv_proxy = hv20 * 1.25  # inflate realized vol → implied-ish

        time_factor = math.sqrt(dte / 365)

        est_premium = spot * iv_proxy * time_factor * 0.35

        roc = est_premium / strike
        annualized = annualize(roc, dte)

        # scoring
        premium_score = roc
        vol_score = iv_proxy
        quality_score = 1 / (1 + hv20)  # lower chaos = better stock

        score = (
            0.35 * premium_score +
            0.30 * vol_score +
            0.20 * quality_score +
            0.15 * annualized
        )

        rows.append({
            "Ticker": t,
            "Price": round(spot, 2),
            "Strike": round(strike, 2),
            "Est Premium": round(est_premium, 2),
            "ROC %": round(roc * 100, 2),
            "Annual %": round(annualized * 100, 1),
            "HV20 %": round(hv20 * 100, 1),
            "Score": score
        })

    except Exception:
        continue

# =========================================================
# DISPLAY
# =========================================================
if not rows:
    st.error("No data returned. Reduce tickers.")
else:
    df = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))

    top = df.iloc[0]

    st.success(
        f"🥇 TOP: {top['Ticker']} | Strike {top['Strike']} | "
        f"Premium ${top['Est Premium']} | ROC {top['ROC %']}%"
    )

    st.dataframe(df, use_container_width=True, hide_index=True)
