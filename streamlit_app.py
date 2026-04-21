import math
from datetime import datetime, date

import pandas as pd
import streamlit as st
import yfinance as yf

# ----------------------------
# PAGE / STYLE
# ----------------------------
st.set_page_config(page_title="CSP Screener", layout="wide")
st.title("🏆 CSP Put Screener")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    [data-testid="stMetricValue"] { color: #00FF00 !important; font-size: 1.6rem !important; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900; }
    tbody tr td { color: #FFFFFF !important; font-weight: 700 !important; }
    div.stButton > button {
        background-color: #00FF00 !important;
        color: #000000 !important;
        font-weight: 900 !important;
        width: 100% !important;
        height: 3.5em !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# HELPERS
# ----------------------------
def norm_cdf(x: float) -> float:
    """Standard normal CDF using erf, no scipy required."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def safe_float(x, default=0.0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default

def min_max_scale(series: pd.Series) -> pd.Series:
    """Scale to [0,1]; if constant, return 0.5s."""
    s = series.astype(float)
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or pd.isna(hi) or hi - lo == 0:
        return pd.Series([0.5] * len(series), index=series.index)
    return (s - lo) / (hi - lo)

def estimate_put_delta(spot: float, strike: float, dte: int, iv: float, r: float = 0.04) -> float:
    """
    Black-Scholes approx for European put delta.
    Returns negative number, usually between -1 and 0.
    """
    if spot <= 0 or strike <= 0 or dte <= 0 or iv <= 0:
        return float("nan")

    T = dte / 365.0
    sigma = iv
    try:
        d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        put_delta = norm_cdf(d1) - 1.0
        return put_delta
    except Exception:
        return float("nan")

@st.cache_data(ttl=60)
def fetch_last_prices(tickers):
    """
    Fetch recent prices in one request instead of one-by-one history calls.
    """
    data = yf.download(
        tickers=tickers,
        period="5d",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    prices = {}

    if len(tickers) == 1:
        # Single ticker shape
        close_series = data["Close"].dropna()
        if not close_series.empty:
            prices[tickers[0]] = float(close_series.iloc[-1])
        return prices

    for t in tickers:
        try:
            close_series = data[t]["Close"].dropna()
            if not close_series.empty:
                prices[t] = float(close_series.iloc[-1])
        except Exception:
            continue

    return prices

def get_put_candidates(symbol: str, spot: float, target_date: str, rf_rate: float):
    """
    Pull put chain and compute metrics for ALL reasonable candidate puts.
    """
    tk = yf.Ticker(symbol)
    chain = tk.option_chain(target_date)
    puts = chain.puts.copy()

    if puts.empty:
        return pd.DataFrame()

    expiry = datetime.strptime(target_date, "%Y-%m-%d").date()
    today = date.today()
    dte = (expiry - today).days

    if dte <= 0:
        return pd.DataFrame()

    rows = []

    for _, row in puts.iterrows():
        strike = safe_float(row.get("strike"))
        bid = safe_float(row.get("bid"))
        ask = safe_float(row.get("ask"))
        last_price = safe_float(row.get("lastPrice"))
        iv = safe_float(row.get("impliedVolatility"))
        oi = safe_float(row.get("openInterest"))
        volume = safe_float(row.get("volume"))
        in_the_money = bool(row.get("inTheMoney", False))

        if strike <= 0:
            continue

        # Mid price fallback logic
        if bid > 0 and ask > 0 and ask >= bid:
            mid = (bid + ask) / 2.0
        elif last_price > 0:
            mid = last_price
        else:
            continue

        if mid <= 0:
            continue

        otm_pct = (spot - strike) / spot
        breakeven = strike - mid
        breakeven_buffer_pct = (spot - breakeven) / spot
        roc = mid / strike
        annualized_roc = roc * (365.0 / dte)

        spread_pct = ((ask - bid) / mid) if (bid > 0 and ask > 0 and mid > 0) else 1.0
        delta = estimate_put_delta(spot, strike, dte, iv, rf_rate)
        prob_otm = (1.0 + delta) if pd.notna(delta) else float("nan")  # put delta is negative

        rows.append({
            "Ticker": symbol,
            "Spot": round(spot, 2),
            "Expiry": target_date,
            "DTE": dte,
            "Strike": strike,
            "Bid": bid,
            "Ask": ask,
            "Mid": round(mid, 3),
            "IV": iv,
            "DeltaEst": delta,
            "ProbOTMEst": prob_otm,
            "OTM_Pct": otm_pct,
            "Breakeven": round(breakeven, 3),
            "BE_Buffer_Pct": breakeven_buffer_pct,
            "ROC": roc,
            "AnnualizedROC": annualized_roc,
            "Spread_Pct": spread_pct,
            "OpenInterest": oi,
            "Volume": volume,
            "InTheMoney": in_the_money,
        })

    return pd.DataFrame(rows)

# ----------------------------
# SIDEBAR INPUTS
# ----------------------------
with st.sidebar:
    st.header("⚡ Criteria")

    ticker_str = st.text_area(
        "Universe",
        "NVDA, AAPL, MSFT, AMZN, META, AVGO, JPM, UNH, COST"
    )
    tickers = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]

    target_date = st.text_input("Expiration (YYYY-MM-DD)", "2026-04-24")

    st.subheader("Filters")
    min_otm_pct = st.slider("Min OTM %", 0.0, 20.0, 5.0, 0.5) / 100.0
    min_be_buffer_pct = st.slider("Min Breakeven Buffer %", 0.0, 20.0, 5.0, 0.5) / 100.0
    min_delta_abs = st.slider("Min |Delta|", 0.01, 0.50, 0.08, 0.01)
    max_delta_abs = st.slider("Max |Delta|", 0.01, 0.50, 0.20, 0.01)
    max_spread_pct = st.slider("Max Bid/Ask Spread %", 1.0, 50.0, 12.0, 1.0) / 100.0
    min_oi = st.number_input("Min Open Interest", min_value=0, value=200, step=50)
    min_volume = st.number_input("Min Volume", min_value=0, value=1, step=1)
    min_mid = st.number_input("Min Premium ($)", min_value=0.0, value=0.20, step=0.05, format="%.2f")

    st.subheader("Model")
    rf_rate = st.number_input("Risk-free Rate", min_value=0.0, max_value=0.15, value=0.04, step=0.005, format="%.3f")

    st.subheader("Ranking Weights")
    w_annualized = st.slider("Weight: Annualized ROC", 0.0, 1.0, 0.35, 0.05)
    w_prob = st.slider("Weight: Prob OTM", 0.0, 1.0, 0.25, 0.05)
    w_be = st.slider("Weight: Break-even Buffer", 0.0, 1.0, 0.20, 0.05)
    w_otm = st.slider("Weight: OTM %", 0.0, 1.0, 0.10, 0.05)
    w_spread_penalty = st.slider("Penalty: Spread %", 0.0, 1.0, 0.10, 0.05)

# ----------------------------
# RUN SCAN
# ----------------------------
if st.button("🚀 Scan CSP Candidates"):
    if not tickers:
        st.error("Enter at least one ticker.")
        st.stop()

    prices = fetch_last_prices(tickers)

    all_candidates = []
    progress = st.progress(0)
    status = st.empty()

    for i, symbol in enumerate(tickers):
        progress.progress((i + 1) / len(tickers))
        status.text(f"Scanning {symbol}...")

        try:
            spot = prices.get(symbol)
            if spot is None or spot <= 0:
                continue

            df = get_put_candidates(symbol, spot, target_date, rf_rate)
            if df.empty:
                continue

            all_candidates.append(df)
        except Exception as e:
            st.warning(f"{symbol}: {e}")
            continue

    progress.empty()
    status.empty()

    if not all_candidates:
        st.error("No option-chain data returned.")
        st.stop()

    df = pd.concat(all_candidates, ignore_index=True)

    # ----------------------------
    # FILTERS
    # ----------------------------
    filt = (
        (~df["InTheMoney"]) &
        (df["OTM_Pct"] >= min_otm_pct) &
        (df["BE_Buffer_Pct"] >= min_be_buffer_pct) &
        (df["Mid"] >= min_mid) &
        (df["OpenInterest"] >= min_oi) &
        (df["Volume"] >= min_volume) &
        (df["Spread_Pct"] <= max_spread_pct) &
        (df["DeltaEst"].notna()) &
        (df["DeltaEst"].abs() >= min_delta_abs) &
        (df["DeltaEst"].abs() <= max_delta_abs)
    )

    ranked = df.loc[filt].copy()

    if ranked.empty:
        st.error("No contracts passed your filters. Loosen one or two filters and rerun.")
        st.stop()

    # ----------------------------
    # SCORE
    # ----------------------------
    ranked["Score"] = (
        w_annualized * min_max_scale(ranked["AnnualizedROC"]) +
        w_prob * min_max_scale(ranked["ProbOTMEst"]) +
        w_be * min_max_scale(ranked["BE_Buffer_Pct"]) +
        w_otm * min_max_scale(ranked["OTM_Pct"]) -
        w_spread_penalty * min_max_scale(ranked["Spread_Pct"])
    )

    ranked = ranked.sort_values("Score", ascending=False).reset_index(drop=True)
    ranked.insert(0, "Rank", range(1, len(ranked) + 1))

    # ----------------------------
    # DISPLAY
    # ----------------------------
    top = ranked.iloc[0]
    st.success(
        f"🥇 Top candidate: {top['Ticker']} {top['Strike']:.2f}P "
        f"| Mid ${top['Mid']:.2f} | Delta {top['DeltaEst']:.2f} "
        f"| Prob OTM {top['ProbOTMEst']:.0%}"
    )

    display = ranked.copy()
    pct_cols = ["OTM_Pct", "BE_Buffer_Pct", "ROC", "AnnualizedROC", "Spread_Pct", "ProbOTMEst"]
    for col in pct_cols:
        display[col] = (display[col] * 100).round(2)

    display["DeltaEst"] = display["DeltaEst"].round(3)
    display["Score"] = display["Score"].round(3)
    display["IV"] = (display["IV"] * 100).round(1)

    st.dataframe(
        display[[
            "Rank", "Ticker", "Expiry", "DTE", "Spot", "Strike", "Bid", "Ask", "Mid",
            "DeltaEst", "ProbOTMEst", "OTM_Pct", "BE_Buffer_Pct",
            "ROC", "AnnualizedROC", "Spread_Pct", "IV", "OpenInterest", "Volume", "Score"
        ]],
        use_container_width=True,
        hide_index=True
    )
