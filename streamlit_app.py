import math
import time
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Real CSP Screener", layout="wide")
st.title("🏆 Real CSP Opportunity Screener")

# =========================
# INPUT
# =========================
ticker_input = st.text_input(
    "Enter tickers (keep to 3–6)",
    "NVDA, MSFT, AAPL"
)

tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

target_delta_low = st.slider("Min Delta", 0.05, 0.30, 0.10)
target_delta_high = st.slider("Max Delta", 0.05, 0.40, 0.20)

min_premium = st.slider("Min Premium ($)", 0.1, 5.0, 0.5)
min_roc = st.slider("Min ROC %", 0.0, 2.0, 0.3) / 100

# =========================
# HELPERS
# =========================
def safe_float(x):
    try:
        return float(x)
    except:
        return None

# =========================
# MAIN
# =========================
if st.button("🚀 Run Screener"):

    results = []
    status = st.empty()

    for t in tickers:
        status.write(f"Scanning {t}...")

        try:
            tk = yf.Ticker(t)

            expirations = tk.options
            if not expirations:
                results.append({"Ticker": t, "Status": "No expirations"})
                continue

            expiry = expirations[0]  # nearest weekly

            chain = tk.option_chain(expiry)
            puts = chain.puts

            if puts is None or puts.empty:
                results.append({"Ticker": t, "Status": "No puts"})
                continue

            best_row = None
            best_score = -1

            for _, row in puts.iterrows():

                strike = safe_float(row.get("strike"))
                bid = safe_float(row.get("bid"))
                ask = safe_float(row.get("ask"))
                iv = safe_float(row.get("impliedVolatility"))
                oi = safe_float(row.get("openInterest"))
                vol = safe_float(row.get("volume"))

                if not strike or strike <= 0:
                    continue

                mid = None
                if bid and ask and ask >= bid:
                    mid = (bid + ask) / 2
                else:
                    continue

                if mid < min_premium:
                    continue

                roc = mid / strike
                if roc < min_roc:
                    continue

                # crude delta proxy from moneyness
                # (yahoo delta often missing)
                # deeper OTM = lower delta
                # normalize approx
                price = strike / (1 - 0.10)  # rough reverse assumption
                delta_est = mid / price if price else 0.1

                if not (target_delta_low <= abs(delta_est) <= target_delta_high):
                    continue

                spread = (ask - bid) / mid if mid > 0 else 1

                if spread > 0.25:
                    continue

                score = (
                    0.4 * roc +
                    0.3 * (iv if iv else 0) +
                    0.2 * (1 / (1 + spread)) +
                    0.1 * (oi if oi else 0) / 1000
                )

                if score > best_score:
                    best_score = score
                    best_row = {
                        "Ticker": t,
                        "Expiry": expiry,
                        "Strike": strike,
                        "Premium": round(mid, 2),
                        "ROC %": round(roc * 100, 2),
                        "IV %": round((iv or 0) * 100, 1),
                        "Spread %": round(spread * 100, 1),
                        "OI": int(oi or 0),
                        "Volume": int(vol or 0),
                        "Score": round(score, 4),
                        "Status": "OK"
                    }

            if best_row:
                results.append(best_row)
            else:
                results.append({"Ticker": t, "Status": "No valid contracts"})

            time.sleep(1.2)  # avoid rate limit

        except Exception:
            results.append({"Ticker": t, "Status": "Error / Rate limited"})
            continue

    status.empty()

    df = pd.DataFrame(results)

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
        st.warning("No good trades found right now.")
