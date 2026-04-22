import math
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="CSP Screener", layout="wide")
st.title("🏆 CSP Screener (Works Version)")

# -----------------------------
# INPUT
# -----------------------------
ticker_input = st.text_input(
    "Enter tickers (comma separated)",
    "NVDA, MSFT, AAPL, AMZN"
)

tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

otm_pct = st.slider("OTM %", 2, 15, 6)
dte = st.slider("Days to Expiration", 5, 14, 7)

# -----------------------------
# FUNCTIONS
# -----------------------------
def get_data(ticker):
    try:
        df = yf.download(
            ticker,
            period="3mo",
            interval="1d",
            progress=False,
            threads=False
        )
        if df is None or df.empty:
            return None
        return df
    except:
        return None

def calc_vol(close):
    return close.pct_change().dropna().tail(20).std() * math.sqrt(252)

# -----------------------------
# RUN
# -----------------------------
if st.button("🚀 Run Screener"):

    results = []
    status = st.empty()

    for t in tickers:
        status.write(f"Scanning {t}...")

        df = get_data(t)

        if df is None or "Close" not in df:
            results.append({
                "Ticker": t,
                "Status": "No data"
            })
            continue

        close = df["Close"].dropna()

        if len(close) < 25:
            results.append({
                "Ticker": t,
                "Status": "Not enough data"
            })
            continue

        price = float(close.iloc[-1])
        hv = calc_vol(close)

        # estimate IV (simple but stable)
        iv = hv * 1.3

        strike = price * (1 - otm_pct / 100)

        # simple premium model
        time_factor = math.sqrt(dte / 365)
        premium = price * iv * time_factor * 0.3

        roc = premium / strike
        annual = roc * (365 / dte)

        score = (
            0.4 * roc +
            0.3 * iv +
            0.2 * (1 / (1 + hv)) +
            0.1 * annual
        )

        results.append({
            "Ticker": t,
            "Price": round(price, 2),
            "Strike": round(strike, 2),
            "Est Premium": round(premium, 2),
            "ROC %": round(roc * 100, 2),
            "Annual %": round(annual * 100, 1),
            "Vol %": round(hv * 100, 1),
            "Score": round(score, 4),
            "Status": "OK"
        })

    status.empty()

    df = pd.DataFrame(results)

    if "Score" in df.columns:
        df = df.sort_values("Score", ascending=False)

    st.dataframe(df, use_container_width=True)

    # top pick
    valid = df[df["Status"] == "OK"]

    if not valid.empty:
        top = valid.iloc[0]
        st.success(
            f"TOP: {top['Ticker']} | Strike {top['Strike']} | "
            f"Premium ${top['Est Premium']} | ROC {top['ROC %']}%"
        )
    else:
        st.warning("No valid tickers returned data.")
