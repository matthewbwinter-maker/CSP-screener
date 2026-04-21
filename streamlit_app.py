import math
from datetime import datetime, date

import pandas as pd
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="CSP Opportunity Screener", layout="wide")
st.title("🏆 CSP Opportunity Screener")

# ----------------------------
# Helpers
# ----------------------------
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
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or pd.isna(hi) or hi - lo == 0:
        return pd.Series([0.5] * len(series), index=series.index)
    return (s - lo) / (hi - lo)

def estimate_put_delta(spot: float, strike: float, dte: int, iv: float, r: float = 0.04) -> float:
    if spot <= 0 or strike <= 0 or dte <= 0 or iv <= 0:
        return float("nan")
    T = dte / 365.0
    try:
        d1 = (math.log(spot / strike) + (r + 0.5 * iv**2) * T) / (iv * math.sqrt(T))
        return norm_cdf(d1) - 1.0
    except Exception:
        return float("nan")

def label_setup(score: float) -> str:
    if score >= 0.85:
        return "Exceptional"
    elif score >= 0.74:
        return "Good"
    elif score >= 0.64:
        return "Acceptable"
    return "Pass"

def premium_label(roc: float, annualized_roc: float) -> str:
    if roc >= 0.0060 and annualized_roc >= 0.28:
        return "Juicy"
    elif roc >= 0.0045 and annualized_roc >= 0.22:
        return "Decent"
    elif roc >= 0.0035 and annualized_roc >= 0.18:
        return "Thin"
    return "Too Thin"


# ----------------------------
# Data Fetch
# ----------------------------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_last_prices_and_stats(tickers):
    rows = []

    for t in tickers:
        try:
            hist = yf.download(
                t,
                period="3mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )

            if hist is None or hist.empty:
                continue

            # Flatten in case yfinance returns multiindex columns
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)

            if "Close" not in hist.columns:
                continue

            close = hist["Close"].dropna()
            if len(close) < 25:
                continue

            spot = float(close.iloc[-1])
            ret_5d = (spot / float(close.iloc[-6]) - 1.0) if len(close) >= 6 else float("nan")
            hv20 = close.pct_change().dropna().tail(20).std() * math.sqrt(252)

            rows.append({
                "Ticker": t,
                "Spot": round(spot, 2),
                "Ret5D": ret_5d,
                "HV20": hv20,
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


# ----------------------------
# Ranking
# ----------------------------
def rank_underlyings(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["DownMoveScore"] = -out["Ret5D"].fillna(0)
    out["UnderlyingScore"] = (
        0.55 * min_max_scale(out["HV20"].fillna(0)) +
        0.45 * min_max_scale(out["DownMoveScore"].fillna(0))
    )
    out = out.sort_values("UnderlyingScore", ascending=False).reset_index(drop=True)
    out.insert(0, "Rank", range(1, len(out) + 1))
    return out

def score_puts(puts: pd.DataFrame, spot: float, expiry: str, rf_rate: float) -> pd.DataFrame:
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
        itm = bool(row.get("inTheMoney", False))

        if strike <= 0:
            continue

        if bid > 0 and ask > 0 and ask >= bid:
            mid = (bid + ask) / 2
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
        delta = estimate_put_delta(spot, strike, dte, iv, rf_rate)
        prob_otm = (1.0 + delta) if pd.notna(delta) else float("nan")
        prem_eff = (roc / abs(delta)) if pd.notna(delta) and abs(delta) > 0 else float("nan")
        prem_label = premium_label(roc, annualized_roc)

        rows.append({
            "Expiry": expiry,
            "DTE": dte,
            "Spot": round(spot, 2),
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
            "PremiumEfficiency": prem_eff,
            "PremiumLabel": prem_label,
            "OpenInterest": oi,
            "Volume": volume,
            "InTheMoney": itm,
        })

    return pd.DataFrame(rows)

def filter_and_rank_puts(
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

    ranked = df.loc[filt].copy()

    if exclude_too_thin:
        ranked = ranked[ranked["PremiumLabel"] != "Too Thin"].copy()

    if ranked.empty:
        return ranked

    ranked["Score"] = (
        0.35 * min_max_scale(ranked["AnnualizedROC"]) +
        0.25 * min_max_scale(ranked["PremiumEfficiency"]) +
        0.15 * min_max_scale(ranked["ProbOTMEst"]) +
        0.15 * min_max_scale(ranked["BE_Buffer_Pct"]) -
        0.10 * min_max_scale(ranked["Spread_Pct"])
    )

    ranked["Setup"] = ranked["Score"].apply(label_setup)
    ranked = ranked.sort_values("Score", ascending=False).reset_index(drop=True)
    ranked.insert(0, "Rank", range(1, len(ranked) + 1))
    return ranked


# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    ticker_str = st.text_area(
        "Tickers",
        "NVDA, AAPL, MSFT, AMZN, META, AVGO, JPM, UNH, COST"
    )
    tickers = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]

    min_otm_pct = st.slider("Min OTM %", 0.0, 20.0, 5.0, 0.5) / 100.0
    min_be_buffer_pct = st.slider("Min Break-even Buffer %", 0.0, 20.0, 6.0, 0.5) / 100.0
    min_delta_abs = st.slider("Min |Delta|", 0.01, 0.50, 0.10, 0.01)
    max_delta_abs = st.slider("Max |Delta|", 0.01, 0.50, 0.18, 0.01)
    max_spread_pct = st.slider("Max Bid/Ask Spread %", 1.0, 50.0, 10.0, 1.0) / 100.0

    min_oi = st.number_input("Min Open Interest", min_value=0, value=300, step=50)
    min_volume = st.number_input("Min Volume", min_value=0, value=1, step=1)
    min_mid = st.number_input("Min Premium ($)", min_value=0.0, value=0.35, step=0.05, format="%.2f")
    min_roc = st.slider("Min ROC %", 0.0, 2.0, 0.40, 0.05) / 100.0
    min_annualized_roc = st.slider("Min Annualized ROC %", 0.0, 100.0, 20.0, 1.0) / 100.0
    exclude_too_thin = st.checkbox("Exclude 'Too Thin' premium", value=True)
    rf_rate = st.number_input("Risk-free Rate", min_value=0.0, max_value=0.15, value=0.04, step=0.005, format="%.3f")


# ----------------------------
# Session State
# ----------------------------
if "underlying_rank" not in st.session_state:
    st.session_state["underlying_rank"] = None
if "scan_error" not in st.session_state:
    st.session_state["scan_error"] = None


# ----------------------------
# Step 1
# ----------------------------
if st.button("1) Rank Underlyings", type="primary"):
    with st.spinner("Ranking underlyings..."):
        try:
            raw = fetch_last_prices_and_stats(tickers)

            if raw.empty:
                st.session_state["underlying_rank"] = None
                st.session_state["scan_error"] = (
                    "No price data returned. Yahoo likely blocked requests or one of the symbols failed."
                )
            else:
                ranked_names = rank_underlyings(raw)
                st.session_state["underlying_rank"] = ranked_names
                st.session_state["scan_error"] = None

        except Exception as e:
            st.session_state["underlying_rank"] = None
            st.session_state["scan_error"] = f"Price ranking failed: {e}"

if st.session_state["scan_error"]:
    st.error(st.session_state["scan_error"])


# ----------------------------
# Step 2 / 3
# ----------------------------
underlying_rank = st.session_state["underlying_rank"]

if underlying_rank is not None and not underlying_rank.empty:
    st.success(f"Loaded {len(underlying_rank)} underlyings.")

    show_df = underlying_rank.copy()
    show_df["Ret5D"] = (show_df["Ret5D"] * 100).round(2)
    show_df["HV20"] = (show_df["HV20"] * 100).round(2)
    show_df["UnderlyingScore"] = show_df["UnderlyingScore"].round(3)

    st.dataframe(show_df, use_container_width=True, hide_index=True)

    top_names = underlying_rank["Ticker"].head(5).tolist()

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_ticker = st.selectbox("2) Pick one ticker to inspect", options=top_names, index=0)

    with col2:
        expirations = []
        try:
            expirations = fetch_expirations(selected_ticker)
        except Exception as e:
            st.warning(f"Could not fetch expirations for {selected_ticker}: {e}")

        selected_expiry = st.selectbox("Expiry", options=expirations if expirations else [])

    if selected_expiry and st.button("3) Fetch best put opportunities"):
        with st.spinner(f"Fetching {selected_ticker} options..."):
            try:
                spot = float(
                    underlying_rank.loc[underlying_rank["Ticker"] == selected_ticker, "Spot"].iloc[0]
                )

                chain = fetch_option_chain(selected_ticker, selected_expiry)
                puts = chain.puts.copy()

                scored = score_puts(puts, spot, selected_expiry, rf_rate)

                ranked_puts = filter_and_rank_puts(
                    df=scored,
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

                if ranked_puts.empty:
                    st.warning("No contracts passed your filters for this ticker/expiry.")
                else:
                    top = ranked_puts.iloc[0]
                    st.success(
                        f"Top setup: {selected_ticker} {top['Strike']:.2f}P | "
                        f"Mid ${top['Mid']:.2f} | Delta {top['DeltaEst']:.2f} | "
                        f"Prob OTM {top['ProbOTMEst']:.0%} | {top['PremiumLabel']} | {top['Setup']}"
                    )

                    display = ranked_puts.copy()
                    pct_cols = [
                        "OTM_Pct", "BE_Buffer_Pct", "ROC",
                        "AnnualizedROC", "Spread_Pct", "ProbOTMEst"
                    ]
                    for col in pct_cols:
                        display[col] = (display[col] * 100).round(2)

                    display["DeltaEst"] = display["DeltaEst"].round(3)
                    display["PremiumEfficiency"] = display["PremiumEfficiency"].round(4)
                    display["Score"] = display["Score"].round(3)
                    display["IV"] = (display["IV"] * 100).round(1)

                    st.dataframe(
                        display[[
                            "Rank", "Setup", "PremiumLabel", "Expiry", "DTE", "Spot", "Strike",
                            "Bid", "Ask", "Mid", "DeltaEst", "ProbOTMEst", "OTM_Pct",
                            "BE_Buffer_Pct", "ROC", "AnnualizedROC", "PremiumEfficiency",
                            "Spread_Pct", "IV", "OpenInterest", "Volume", "Score"
                        ]],
                        use_container_width=True,
                        hide_index=True
                    )

            except Exception as e:
                st.error(f"Option-chain fetch failed for {selected_ticker}: {e}")
else:
    st.info("Click '1) Rank Underlyings' to begin.")
