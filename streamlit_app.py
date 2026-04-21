import math
import time
from datetime import datetime, date

import pandas as pd
import streamlit as st
import yfinance as yf


# =========================================================
# PAGE
# =========================================================
st.set_page_config(page_title="High-Quality CSP Screener", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    [data-testid="stMetricValue"] {
        color: #00FF00 !important;
        font-size: 1.7rem !important;
    }
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
        height: 3.2em !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏆 High-Quality Put Opportunity Screener")


# =========================================================
# USER-DEFINED STOCK QUALITY
# Adjust these to match your own conviction
# =========================================================
DEFAULT_QUALITY_MAP = {
    "MSFT": 10,
    "NVDA": 10,
    "AAPL": 9,
    "AMZN": 9,
    "META": 8,
    "AVGO": 8,
    "GOOGL": 9,
    "JPM": 7,
    "UNH": 7,
    "COST": 8,
    "TSLA": 5,
    "AMD": 8,
    "NFLX": 7,
    "LLY": 7,
}


# =========================================================
# HELPERS
# =========================================================
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
    if len(s) == 0:
        return s
    lo = s.min()
    hi = s.max()
    if pd.isna(lo) or pd.isna(hi) or hi - lo == 0:
        return pd.Series([0.5] * len(s), index=s.index)
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
        return norm_cdf(d1) - 1.0
    except Exception:
        return float("nan")

def label_setup(score: float) -> str:
    if score >= 0.84:
        return "Exceptional"
    elif score >= 0.73:
        return "Good"
    elif score >= 0.63:
        return "Acceptable"
    return "Pass"

def premium_label(roc: float, annualized_roc: float) -> str:
    if roc >= 0.0070 and annualized_roc >= 0.30:
        return "Juicy"
    elif roc >= 0.0050 and annualized_roc >= 0.24:
        return "Decent"
    elif roc >= 0.0040 and annualized_roc >= 0.20:
        return "Thin"
    return "Too Thin"

def make_quality_map(user_tickers):
    out = {}
    for t in user_tickers:
        out[t] = DEFAULT_QUALITY_MAP.get(t, 6)
    return out


# =========================================================
# DATA FETCH
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def fetch_last_prices(tickers):
    rows = []

    for ticker in tickers:
        try:
            hist = yf.download(
                ticker,
                period="3mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )

            if hist is None or hist.empty:
                continue

            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)

            if "Close" not in hist.columns:
                continue

            close = hist["Close"].dropna()
            if close.empty:
                continue

            rows.append({
                "Ticker": ticker,
                "Spot": float(close.iloc[-1]),
            })
        except Exception:
            continue

    return pd.DataFrame(rows)

@st.cache_data(ttl=600, show_spinner=False)
def fetch_expirations(symbol: str):
    tk = yf.Ticker(symbol)
    return list(tk.options)

@st.cache_data(ttl=600, show_spinner=False)
def fetch_option_chain(symbol: str, expiry: str):
    tk = yf.Ticker(symbol)
    return tk.option_chain(expiry)


# =========================================================
# CORE SCORING
# =========================================================
def build_put_candidates(
    symbol: str,
    spot: float,
    expiry: str,
    rf_rate: float,
    stock_quality: float,
) -> pd.DataFrame:
    try:
        chain = fetch_option_chain(symbol, expiry)
        puts = chain.puts.copy()
    except Exception:
        return pd.DataFrame()

    if puts.empty:
        return pd.DataFrame()

    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    dte = (expiry_date - date.today()).days
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
        annualized_roc = roc * 365.0 / dte
        spread_pct = ((ask - bid) / mid) if (bid > 0 and ask > 0 and mid > 0) else 1.0
        delta_est = estimate_put_delta(spot, strike, dte, iv, rf_rate)
        prob_otm_est = (1.0 + delta_est) if pd.notna(delta_est) else float("nan")
        premium_efficiency = (roc / abs(delta_est)) if pd.notna(delta_est) and abs(delta_est) > 0 else float("nan")
        prem_label = premium_label(roc, annualized_roc)

        rows.append({
            "Ticker": symbol,
            "StockQuality": stock_quality,
            "Expiry": expiry,
            "DTE": dte,
            "Spot": round(spot, 2),
            "Strike": strike,
            "Bid": bid,
            "Ask": ask,
            "Mid": round(mid, 3),
            "IV": iv,
            "DeltaEst": delta_est,
            "ProbOTMEst": prob_otm_est,
            "OTM_Pct": otm_pct,
            "Breakeven": round(breakeven, 3),
            "BE_Buffer_Pct": be_buffer_pct,
            "ROC": roc,
            "AnnualizedROC": annualized_roc,
            "Spread_Pct": spread_pct,
            "PremiumEfficiency": premium_efficiency,
            "PremiumLabel": prem_label,
            "OpenInterest": oi,
            "Volume": volume,
            "InTheMoney": in_the_money,
        })

    return pd.DataFrame(rows)


def filter_candidates(
    df: pd.DataFrame,
    min_otm_pct: float,
    min_be_buffer_pct: float,
    min_delta_abs: float,
    max_delta_abs: float,
    max_spread_pct: float,
    min_oi: int,
    min_volume: int,
    min_mid: float,
    min_roc: float,
    min_annualized_roc: float,
    exclude_too_thin: bool,
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    filt = (
        (~df["InTheMoney"]) &
        (df["OTM_Pct"] >= min_otm_pct) &
        (df["BE_Buffer_Pct"] >= min_be_buffer_pct) &
        (df["Mid"] >= min_mid) &
        (df["ROC"] >= min_roc) &
        (df["AnnualizedROC"] >= min_annualized_roc) &
        (df["OpenInterest"] >= min_oi) &
        (df["Volume"] >= min_volume) &
        (df["Spread_Pct"] <= max_spread_pct) &
        (df["DeltaEst"].notna()) &
        (df["PremiumEfficiency"].notna()) &
        (df["DeltaEst"].abs() >= min_delta_abs) &
        (df["DeltaEst"].abs() <= max_delta_abs)
    )

    out = df.loc[filt].copy()

    if exclude_too_thin:
        out = out[out["PremiumLabel"] != "Too Thin"].copy()

    return out


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    # Your stated priorities:
    # 1) quality of stock
    # 2) premium richness
    # 3) volatility
    # then guardrails
    out["Score"] = (
        0.30 * min_max_scale(out["StockQuality"]) +
        0.28 * min_max_scale(out["AnnualizedROC"]) +
        0.18 * min_max_scale(out["IV"]) +
        0.10 * min_max_scale(out["PremiumEfficiency"]) +
        0.06 * min_max_scale(out["ProbOTMEst"]) +
        0.05 * min_max_scale(out["BE_Buffer_Pct"]) +
        0.03 * min_max_scale(out["OTM_Pct"]) -
        0.10 * min_max_scale(out["Spread_Pct"])
    )

    out["Setup"] = out["Score"].apply(label_setup)
    return out


def keep_best_per_ticker(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.sort_values(["Ticker", "Score"], ascending=[True, False]).copy()
    out = out.groupby("Ticker", as_index=False).head(1).copy()
    out = out.sort_values("Score", ascending=False).reset_index(drop=True)
    out.insert(0, "Rank", range(1, len(out) + 1))
    return out


def explain_row(row: pd.Series) -> str:
    reasons = []
    if row["StockQuality"] >= 9:
        reasons.append("elite stock")
    elif row["StockQuality"] >= 8:
        reasons.append("high-quality stock")

    if row["AnnualizedROC"] >= 0.30:
        reasons.append("strong premium")
    elif row["AnnualizedROC"] >= 0.24:
        reasons.append("decent premium")

    if row["IV"] >= 0.45:
        reasons.append("high IV")
    elif row["IV"] >= 0.30:
        reasons.append("solid IV")

    if row["Spread_Pct"] <= 0.06:
        reasons.append("tight spread")

    if row["BE_Buffer_Pct"] >= 0.07:
        reasons.append("good cushion")

    return ", ".join(reasons[:4])


def run_scan(
    tickers,
    expiry,
    quality_map,
    rf_rate,
    min_otm_pct,
    min_be_buffer_pct,
    min_delta_abs,
    max_delta_abs,
    max_spread_pct,
    min_oi,
    min_volume,
    min_mid,
    min_roc,
    min_annualized_roc,
    exclude_too_thin,
):
    prices = fetch_last_prices(tickers)
    if prices.empty:
        return None, "No price data returned."

    all_candidates = []
    progress = st.progress(0)
    status = st.empty()

    for i, ticker in enumerate(tickers):
        progress.progress((i + 1) / len(tickers))
        status.text(f"Scanning {ticker}...")

        try:
            row = prices.loc[prices["Ticker"] == ticker]
            if row.empty:
                continue

            spot = float(row["Spot"].iloc[0])
            stock_quality = float(quality_map.get(ticker, 6))

            cands = build_put_candidates(
                symbol=ticker,
                spot=spot,
                expiry=expiry,
                rf_rate=rf_rate,
                stock_quality=stock_quality,
            )

            if cands.empty:
                continue

            filtered = filter_candidates(
                df=cands,
                min_otm_pct=min_otm_pct,
                min_be_buffer_pct=min_be_buffer_pct,
                min_delta_abs=min_delta_abs,
                max_delta_abs=max_delta_abs,
                max_spread_pct=max_spread_pct,
                min_oi=min_oi,
                min_volume=min_volume,
                min_mid=min_mid,
                min_roc=min_roc,
                min_annualized_roc=min_annualized_roc,
                exclude_too_thin=exclude_too_thin,
            )

            if filtered.empty:
                continue

            all_candidates.append(filtered)

            # Be gentler with Yahoo
            time.sleep(1.2)

        except Exception:
            continue

    progress.empty()
    status.empty()

    if not all_candidates:
        return None, "No contracts passed filters, or Yahoo returned no option-chain data."

    ranked = pd.concat(all_candidates, ignore_index=True)
    ranked = score_candidates(ranked)
    ranked = keep_best_per_ticker(ranked)
    ranked["WhyItRanked"] = ranked.apply(explain_row, axis=1)

    return ranked, None


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("Universe")

    ticker_str = st.text_area(
        "Tickers (keep this to ~4-8 names on Yahoo)",
        "NVDA, MSFT, AAPL, AMZN, META, AVGO"
    )
    tickers = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]

    quality_map = make_quality_map(tickers)

    st.subheader("Stock Quality Scores")
    st.caption("10 = best quality / strongest willingness to own")
    for t in tickers:
        quality_map[t] = st.slider(
            f"{t} quality",
            min_value=1,
            max_value=10,
            value=int(quality_map[t]),
            step=1
        )

    st.subheader("Expiry")
    expiry_source_ticker = tickers[0] if tickers else "NVDA"

    expirations = []
    try:
        expirations = fetch_expirations(expiry_source_ticker)
    except Exception:
        expirations = []

    if expirations:
        default_idx = 0
        expiry = st.selectbox("Choose expiry", options=expirations, index=default_idx)
    else:
        expiry = st.text_input("Expiry (YYYY-MM-DD)", "2026-04-24")

    st.subheader("Core Filters")

    min_otm_pct = st.slider("Min OTM %", 0.0, 20.0, 5.0, 0.5) / 100.0
    min_be_buffer_pct = st.slider("Min Break-even Buffer %", 0.0, 20.0, 6.0, 0.5) / 100.0
    min_delta_abs = st.slider("Min |Delta|", 0.01, 0.50, 0.10, 0.01)
    max_delta_abs = st.slider("Max |Delta|", 0.01, 0.50, 0.20, 0.01)
    max_spread_pct = st.slider("Max Bid/Ask Spread %", 1.0, 50.0, 10.0, 1.0) / 100.0

    min_oi = st.number_input("Min Open Interest", min_value=0, value=300, step=50)
    min_volume = st.number_input("Min Volume", min_value=0, value=1, step=1)

    st.subheader("Premium Floors")
    min_mid = st.number_input("Min Premium ($)", min_value=0.0, value=0.50, step=0.05, format="%.2f")
    min_roc = st.slider("Min ROC %", 0.0, 2.0, 0.50, 0.05) / 100.0
    min_annualized_roc = st.slider("Min Annualized ROC %", 0.0, 100.0, 24.0, 1.0) / 100.0

    exclude_too_thin = st.checkbox("Exclude 'Too Thin' premium", value=True)

    st.subheader("Model")
    rf_rate = st.number_input(
        "Risk-free Rate",
        min_value=0.0,
        max_value=0.15,
        value=0.04,
        step=0.005,
        format="%.3f"
    )


# =========================================================
# SESSION STATE
# =========================================================
if "scan_results" not in st.session_state:
    st.session_state["scan_results"] = None

if "scan_error" not in st.session_state:
    st.session_state["scan_error"] = None


# =========================================================
# RUN
# =========================================================
if st.button("🚀 Scan Best High-Quality Put Opportunities", type="primary"):
    with st.spinner("Scanning put opportunities..."):
        results, error = run_scan(
            tickers=tickers,
            expiry=expiry,
            quality_map=quality_map,
            rf_rate=rf_rate,
            min_otm_pct=min_otm_pct,
            min_be_buffer_pct=min_be_buffer_pct,
            min_delta_abs=min_delta_abs,
            max_delta_abs=max_delta_abs,
            max_spread_pct=max_spread_pct,
            min_oi=min_oi,
            min_volume=min_volume,
            min_mid=min_mid,
            min_roc=min_roc,
            min_annualized_roc=min_annualized_roc,
            exclude_too_thin=exclude_too_thin,
        )
        st.session_state["scan_results"] = results
        st.session_state["scan_error"] = error


# =========================================================
# DISPLAY
# =========================================================
if st.session_state["scan_error"]:
    st.error(st.session_state["scan_error"])

results = st.session_state["scan_results"]

if results is None:
    st.info("Set your universe and click the scan button.")
elif results.empty:
    st.warning("No results.")
else:
    top = results.iloc[0]

    if top["Setup"] == "Pass":
        st.warning("No special trade right now. Best available names did not clear the quality bar.")
    else:
        st.success(
            f"Top setup: {top['Ticker']} {top['Strike']:.2f}P | "
            f"Mid ${top['Mid']:.2f} | Delta {top['DeltaEst']:.2f} | "
            f"Prob OTM {top['ProbOTMEst']:.0%} | "
            f"{top['PremiumLabel']} | {top['Setup']}"
        )

    display = results.copy()

    pct_cols = [
        "IV", "OTM_Pct", "BE_Buffer_Pct", "ROC",
        "AnnualizedROC", "Spread_Pct", "ProbOTMEst"
    ]
    for col in pct_cols:
        display[col] = (display[col] * 100).round(2)

    display["DeltaEst"] = display["DeltaEst"].round(3)
    display["PremiumEfficiency"] = display["PremiumEfficiency"].round(4)
    display["Score"] = display["Score"].round(3)

    st.dataframe(
        display[[
            "Rank",
            "Ticker",
            "StockQuality",
            "Setup",
            "PremiumLabel",
            "Expiry",
            "DTE",
            "Spot",
            "Strike",
            "Bid",
            "Ask",
            "Mid",
            "DeltaEst",
            "ProbOTMEst",
            "OTM_Pct",
            "BE_Buffer_Pct",
            "ROC",
            "AnnualizedROC",
            "IV",
            "PremiumEfficiency",
            "Spread_Pct",
            "OpenInterest",
            "Volume",
            "Score",
            "WhyItRanked",
        ]],
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "This ranks the best surviving put per ticker. "
        "If Yahoo rate-limits, reduce the universe to 4-6 names."
    )
