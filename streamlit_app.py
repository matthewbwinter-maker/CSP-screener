import math
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="CSP Screener", layout="wide")
st.title("🏆 Reliable CSP Screener (Real-World Workflow)")

# =========================
# INPUT
# =========================
DEFAULT_TICKERS = """
AAPL, MSFT, NVDA, AMZN, META, GOOGL, AVGO, TSLA,
JPM, BAC, GS, UNH, LLY, COST, WMT, HD,
PEP, KO, MCD, NKE, DIS, CRM, ORCL, CSCO,
AMD, QCOM, TXN, INTC, IBM, CAT
"""

ticker_input = st.text_area("Tickers", DEFAULT_TICKERS)
tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

otm_target = st.slider("Target OTM % (5–10 ideal)", 2, 15, 6)
dte = st.slider("Days to Expiration (5–10 ideal)", 5, 14, 7)

# =========================
# FUNCTIONS
# =========================
def get_price_data(ticker):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df is None or df.empty:
            return None
        return df
    except:
        return None

def get_close_series(df):
    if "Close" not in df.columns:
        return None
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
    close = close.dropna()
    if close.empty:
        return None
    return close

def calc_vol(close):
    returns = close.pct_change().dropna()
    if len(returns) < 10:
        return None
    return returns.tail(20).std() * math.sqrt(252)

# =========================
# RUN
# =========================
if st.button("🚀 Scan Opportunities"):

    results = []
    status = st.empty()

    for t in tickers:
        status.write(f"Scanning {t}...")

        df = get_price_data(t)
        if df is None:
            continue

        close = get_close_series(df)
        if close is None or len(close) < 20:
            continue

        try:
            price = float(close.values[-1])
        except:
            continue

        hv = calc_vol(close)
        if hv is None:
            continue

        # implied vol proxy
        iv = hv * 1.3

        # target strike
        strike = price * (1 - otm_target / 100)

        # expected move (real trading concept)
        expected_move = price * iv * math.sqrt(dte / 365)

        # realistic premium zone (not fake precision)
        premium_low = expected_move * 0.25
        premium_high = expected_move * 0.40

        roc_low = premium_low / strike
        roc_high = premium_high / strike

        score = (
            0.4 * roc_high +
            0.3 * iv +
            0.2 * (1 / (1 + hv)) +
            0.1 * roc_low
        )

        results.append({
            "Ticker": t,
            "Price": round(price, 2),
            "Target Strike": round(strike, 2),
            "Premium Range": f"${round(premium_low,2)} - ${round(premium_high,2)}",
            "ROC Range %": f"{round(roc_low*100,2)} - {round(roc_high*100,2)}",
            "Vol %": round(hv * 100, 1),
            "Score": round(score, 4)
        })

    status.empty()

    if not results:
        st.error("No data returned — reduce tickers or check connection.")
    else:
        df = pd.DataFrame(results).sort_values("Score", ascending=False).reset_index(drop=True)
        df.insert(0, "Rank", range(1, len(df) + 1))

        st.dataframe(df, use_container_width=True)

        top = df.iloc[0]
        st.success(
            f"TOP: {top['Ticker']} → Sell ~{top['Target Strike']} Put | "
            f"Premium Range {top['Premium Range']}"
        )
