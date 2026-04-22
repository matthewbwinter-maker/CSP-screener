import time
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="30 Ticker CSP Screener", layout="wide")
st.title("🏆 30 Blue Chip CSP Screener")

# =========================
# DEFAULT UNIVERSE
# =========================
DEFAULT_TICKERS = """
AAPL, MSFT, NVDA, AMZN, META, GOOGL, AVGO, TSLA,
JPM, BAC, GS, UNH, LLY, COST, WMT, HD,
PEP, KO, MCD, NKE, DIS, CRM, ORCL, CSCO,
AMD, QCOM, TXN, INTC, IBM, CAT
"""

ticker_input = st.text_area("Tickers", DEFAULT_TICKERS)
tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

min_premium = st.slider("Min Premium ($)", 0.1, 5.0, 0.5)
min_roc = st.slider("Min ROC %", 0.0, 2.0, 0.3) / 100

batch_size = 5  # CRITICAL for Yahoo stability

# =========================
# SAFE FETCH
# =========================
@st.cache_data(ttl=300)
def fetch_chain(ticker):
    try:
        tk = yf.Ticker(ticker)
        exps = tk.options
        if not exps:
            return None

        expiry = exps[0]
        chain = tk.option_chain(expiry)

        if chain is None or chain.puts is None:
            return None

        return (expiry, chain.puts)
    except:
        return None


# =========================
# SCAN FUNCTION
# =========================
def scan_batch(batch):
    results = []

    for t in batch:
        data = fetch_chain(t)

        if data is None:
            results.append({"Ticker": t, "Status": "No data"})
            continue

        expiry, puts = data

        best = None
        best_score = -1

        for _, row in puts.iterrows():
            try:
                strike = float(row["strike"])
                bid = float(row["bid"])
                ask = float(row["ask"])
                iv = float(row.get("impliedVolatility", 0))
                oi = float(row.get("openInterest", 0))
                vol = float(row.get("volume", 0))

                if bid <= 0 or ask <= 0:
                    continue

                mid = (bid + ask) / 2

                if mid < min_premium:
                    continue

                roc = mid / strike
                if roc < min_roc:
                    continue

                spread = (ask - bid) / mid
                if spread > 0.25:
                    continue

                score = (
                    0.4 * roc +
                    0.3 * iv +
                    0.2 * (1 / (1 + spread)) +
                    0.1 * (oi / 1000)
                )

                if score > best_score:
                    best_score = score
                    best = {
                        "Ticker": t,
                        "Expiry": expiry,
                        "Strike": strike,
                        "Premium": round(mid, 2),
                        "ROC %": round(roc * 100, 2),
                        "IV %": round(iv * 100, 1),
                        "OI": int(oi),
                        "Volume": int(vol),
                        "Score": round(score, 4),
                        "Status": "OK"
                    }

            except:
                continue

        if best:
            results.append(best)
        else:
            results.append({"Ticker": t, "Status": "No valid contracts"})

    return results


# =========================
# RUN
# =========================
if st.button("🚀 Scan All 30 Tickers"):

    all_results = []
    progress = st.progress(0)
    status = st.empty()

    batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]

    for i, batch in enumerate(batches):
        status.write(f"Scanning batch {i+1}/{len(batches)}...")

        batch_results = scan_batch(batch)
        all_results.extend(batch_results)

        progress.progress((i+1)/len(batches))

        time.sleep(2)  # CRITICAL anti-rate-limit

    progress.empty()
    status.empty()

    df = pd.DataFrame(all_results)

    if "Score" in df.columns:
        df = df.sort_values("Score", ascending=False)

    st.dataframe(df, use_container_width=True)

    valid = df[df["Status"] == "OK"]

    if not valid.empty:
        top = valid.iloc[0]
        st.success(
            f"TOP: {top['Ticker']} {top['Strike']}P | "
            f"Premium ${top['Premium']} | ROC {top['ROC %']}%"
        )
    else:
        st.warning("No strong CSP setups right now.")
