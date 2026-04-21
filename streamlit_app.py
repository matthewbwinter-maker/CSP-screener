import math
import time
from datetime import datetime, date

import pandas as pd
import streamlit as st
import yfinance as yf


# ---------------------------------
# PAGE / STYLE
# ---------------------------------
st.set_page_config(page_title="CSP Screener", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    [data-testid="stMetricValue"] { color: #00FF00 !important; font-size: 1.7rem !important; }
    thead tr th {
        background-color: #00FF00 !important;
        color: #000000 !important;
        font-weight: 900 !important;
    }
    tbody tr td {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
    }
    div.stButton > button {
        background-color: #00FF00 !important;
        color: #000000 !important;
        font-weight: 900 !important;
        width: 100% !important;
        height: 3.5em !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏆 CSP SCREENER")


# ---------------------------------
# HELPERS
# ---------------------------------
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def safe_float(x, default=0.0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def min_max_scale(series: pd.Series) -> pd.Series:
    s = series.astype(float)
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or pd.isna(hi) or hi - lo == 0:
        return pd.Series([0.5] * len(series), index=series.index)
    return (s - lo) / (hi - lo)


def estimate_put_delta(spot: float, strike: float, dte: int, iv: float, r: float = 0.04) -> float:
    """
    Black-Scholes approximation for European put delta.
    """
    if spot <= 0 or strike <= 0 or dte <= 0 or iv <= 0:
        return float("nan")

    T = dte / 365.0
    sigma = iv

    try:
        d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        put_delta = norm_cdf(d1) - 1.0
        return put_delta
    except Exception:
        return float("nan")


def label_setup(score: float) -> str:
    if score >= 0.82:
        return "Exceptional"
    elif score >= 0.72:
        return "Good"
    elif score >= 0.62:
        return "Acceptable"
    return "Pass"


@st.cache_data(ttl=300, show_spinner=False)
def fetch_last_prices(tickers):
    """
    Pull recent closing prices in one batch call.
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


@st.cache_data(ttl=300, show_spinner=False)
def fetch_option_chain(symbol: str, expiry: str):
    """
    Cached option-chain fetch to reduce repeated Yahoo hits.
    """
    tk = yf.Ticker(symbol)
    return tk.option_chain(expiry)


def get_put_candidates(symbol: str, spot: float, target_date: str, rf_rate: float) -> pd.DataFrame:
    """
    Fetch all put candidates for a symbol/expiry and compute ranking metrics.
    """
    chain = fetch_option_chain(symbol, target_date)
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

        # Use midpoint when valid, otherwise lastPrice fallback
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
        be_buffer_pct = (spot - breakeven) / spot
        roc = mid / strike
        annualized_roc = roc * (365.0 / dte)

        spread_pct = ((ask - bid) / mid) if (bid > 0 and ask > 0 and mid > 0) else 1.0
        delta = estimate_put_delta(spot, strike, dte, iv, rf_rate)
        prob_otm = (1.0 + delta) if pd.notna(delta) else float("nan")
        premium_efficiency = (roc / abs(delta)) if pd.notna(delta) and abs(delta) > 0 else float("nan")

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
            "BE_Buffer_Pct": be_buffer_pct,
            "ROC": roc,
            "AnnualizedROC": annualized_roc,
            "Spread_Pct": spread_pct,
            "PremiumEfficiency": premium_efficiency,
            "OpenInterest": oi,
            "Volume": volume,
            "InTheMoney": in_the_money,
        })

    return pd.DataFrame(rows)


def run_scan(
    tickers,
    target_date,
    rf_rate,
    min_otm_pct,
    min_be_buffer_pct,
    min_delta_abs,
    max_delta_abs,
    max_spread_pct,
    min_oi,
    min_volume,
    min_mid,
    w_annualized,
    w_prob,
    w_be,
    w_efficiency,
    w_spread_penalty,
):
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

            # Small pause to be gentler with Yahoo
            time.sleep(1.5)

        except Exception as e:
            st.warning(f"{symbol}: {e}")
            continue

    progress.empty()
    status.empty()

    if not all_candidates:
        return None, "No option-chain data returned."

    df = pd.concat(all_candidates, ignore_index=True)

    # FILTER FIRST
    filt = (
        (~df["InTheMoney"]) &
        (df["OTM_Pct"] >= min_otm_pct) &
        (df["BE_Buffer_Pct"] >= min_be_buffer_pct) &
        (df["Mid"] >= min_mid) &
        (df["OpenInterest"] >= min_oi) &
        (df["Volume"] >= min_volume) &
        (df["Spread_Pct"] <= max_spread_pct) &
        (df["DeltaEst"].notna()) &
        (df["PremiumEfficiency"].notna()) &
        (df["DeltaEst"].abs() >= min_delta_abs) &
        (df["DeltaEst"].abs() <= max_delta_abs)
    )

    ranked = df.loc[filt].copy()

    if ranked.empty:
        return None, "No contracts passed your filters."

    # SCORE
    ranked["Score"] = (
        w_annualized * min_max_scale(ranked["AnnualizedROC"]) +
        w_prob * min_max_scale(ranked["ProbOTMEst"]) +
        w_be * min_max_scale(ranked["BE_Buffer_Pct"]) +
        w_efficiency * min_max_scale(ranked["PremiumEfficiency"]) -
        w_spread_penalty * min_max_scale(ranked["Spread_Pct"])
    )

    ranked["Setup"] = ranked["Score"].apply(label_setup)

    # Keep only best contract per ticker
    ranked = ranked.sort_values(["Ticker", "Score"], ascending=[True, False])
    best_per_ticker = ranked.groupby("Ticker", as_index=False).head(1).copy()

    # Sort overall best names
    best_per_ticker = best_per_ticker.sort_values("Score", ascending=False).reset_index(drop=True)
    best_per_ticker.insert(0, "Rank", range(1, len(best_per_ticker) + 1))

    return best_per_ticker, None


# ---------------------------------
# SIDEBAR
# ---------------------------------
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
    min_be_buffer_pct = st.slider("Min Break-even Buffer %", 0.0, 20.0, 6.0, 0.5) / 100.0
    min_delta_abs = st.slider("Min |Delta|", 0.01, 0.50, 0.10, 0.01)
    max_delta_abs = st.slider("Max |Delta|", 0.01, 0.50, 0.18, 0.01)
    max_spread_pct = st.slider("Max Bid/Ask Spread %", 1.0, 50.0, 10.0, 1.0) / 100.0
    min_oi = st.number_input("Min Open Interest", min_value=0, value=300, step=50)
    min_volume = st.number_input("Min Volume", min_value=0, value=1, step=1)
    min_mid = st.number_input("Min Premium ($)", min_value=0.0, value=0.25, step=0.05, format="%.2f")

    st.subheader("Model")
    rf_rate = st.number_input("Risk-free Rate", min_value=0.0, max_value=0.15, value=0.04, step=0.005, format="%.3f")

    st.subheader("Weights")
    w_annualized = st.slider("Weight: Annualized ROC", 0.0, 1.0, 0.25, 0.05)
    w_prob = st.slider("Weight: Prob OTM", 0.0, 1.0, 0.20, 0.05)
    w_be = st.slider("Weight: Break-even Buffer", 0.0, 1.0, 0.20, 0.05)
    w_efficiency = st.slider("Weight: Premium Efficiency", 0.0, 1.0, 0.20, 0.05)
    w_spread_penalty = st.slider("Penalty: Spread %", 0.0, 1.0, 0.15, 0.05)


# ---------------------------------
# BUTTON / SESSION STATE
# ---------------------------------
if "scan_results" not in st.session_state:
    st.session_state["scan_results"] = None

if "scan_error" not in st.session_state:
    st.session_state["scan_error"] = None

if st.button("🚀 Scan CSP Candidates"):
    if not tickers:
        st.session_state["scan_results"] = None
        st.session_state["scan_error"] = "Enter at least one ticker."
    else:
        results, error = run_scan(
            tickers=tickers,
            target_date=target_date,
            rf_rate=rf_rate,
            min_otm_pct=min_otm_pct,
            min_be_buffer_pct=min_be_buffer_pct,
            min_delta_abs=min_delta_abs,
            max_delta_abs=max_delta_abs,
            max_spread_pct=max_spread_pct,
            min_oi=min_oi,
            min_volume=min_volume,
            min_mid=min_mid,
            w_annualized=w_annualized,
            w_prob=w_prob,
            w_be=w_be,
            w_efficiency=w_efficiency,
            w_spread_penalty=w_spread_penalty,
        )
        st.session_state["scan_results"] = results
        st.session_state["scan_error"] = error


# ---------------------------------
# DISPLAY
# ---------------------------------
if st.session_state["scan_error"]:
    st.error(st.session_state["scan_error"])

results = st.session_state["scan_results"]

if results is not None and not results.empty:
    top = results.iloc[0]

    if top["Setup"] == "Pass":
        st.warning("No special trades right now. Best available setup does not stand out.")
    else:
        st.success(
            f"🥇 TOP SETUP: {top['Ticker']} {top['Strike']:.2f}P "
            f"| Mid ${top['Mid']:.2f} | Delta {top['DeltaEst']:.2f} "
            f"| Prob OTM {top['ProbOTMEst']:.0%} | {top['Setup']}"
        )

    good_only = results[results["Setup"] != "Pass"].copy()

    if good_only.empty:
        st.warning("Nothing met the minimum 'Acceptable' threshold.")
    else:
        display = good_only.copy()

        pct_cols = [
            "OTM_Pct", "BE_Buffer_Pct", "ROC", "AnnualizedROC",
            "Spread_Pct", "ProbOTMEst"
        ]
        for col in pct_cols:
            display[col] = (display[col] * 100).round(2)

        display["DeltaEst"] = display["DeltaEst"].round(3)
        display["PremiumEfficiency"] = display["PremiumEfficiency"].round(4)
        display["Score"] = display["Score"].round(3)
        display["IV"] = (display["IV"] * 100).round(1)

        st.dataframe(
            display[[
                "Rank", "Ticker", "Setup", "Expiry", "DTE", "Spot", "Strike",
                "Bid", "Ask", "Mid", "DeltaEst", "ProbOTMEst",
                "OTM_Pct", "BE_Buffer_Pct", "ROC", "AnnualizedROC",
                "PremiumEfficiency", "Spread_Pct", "IV",
                "OpenInterest", "Volume", "Score"
            ]],
            use_container_width=True,
            hide_index=True
        )
