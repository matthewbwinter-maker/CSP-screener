import math
import time
from datetime import datetime, date

import pandas as pd
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="Computed Put Opportunity Screener", layout="wide")
st.title("🏆 Computed High-Quality Put Screener")


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
            if len(close) < 25:
                continue

            spot = float(close.iloc[-1])
            hv20 = close.pct_change().dropna().tail(20).std() * math.sqrt(252)
            ret20d = spot / float(close.iloc[-21]) - 1.0 if len(close) >= 21 else float("nan")

            rows.append({
                "Ticker": ticker,
                "Spot": spot,
                "HV20": hv20,
                "Ret20D": ret20d,
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


def build_put_candidates(symbol: str, spot: float, hv20: float, ret20d: float, expiry: str, rf_rate: float) -> pd.DataFrame:
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
        premium_lbl = premium_label(roc, annualized_roc)

        stock_quality_proxy = (
            0.60 * max(0.0, 1.0 - min(hv20 / 0.80, 1.0)) +
            0.40 * max(0.0, 1.0 - min(abs(ret20d) / 0.25, 1.0))
        )

        rows.append({
            "Ticker": symbol,
            "Expiry": expiry,
            "DTE": dte,
            "Spot": round(spot, 2),
            "HV20": hv20,
            "Ret20D": ret20d,
            "StockQualityProxy": stock_quality_proxy,
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
            "PremiumLabel": premium_lbl,
            "OpenInterest": oi,
            "Volume": volume,
            "InTheMoney": in_the_money,
        })

    return pd.DataFrame(rows)


def filter_candidates(df: pd.DataFrame, cfg: dict, mode_name: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    filt = (
        (~df["InTheMoney"]) &
        (df["OTM_Pct"] >= cfg["min_otm_pct"]) &
        (df["BE_Buffer_Pct"] >= cfg["min_be_buffer_pct"]) &
        (df["Mid"] >= cfg["min_mid"]) &
        (df["ROC"] >= cfg["min_roc"]) &
        (df["AnnualizedROC"] >= cfg["min_annualized_roc"]) &
        (df["OpenInterest"] >= cfg["min_oi"]) &
        (df["Volume"] >= cfg["min_volume"]) &
        (df["Spread_Pct"] <= cfg["max_spread_pct"]) &
        (df["DeltaEst"].notna()) &
        (df["PremiumEfficiency"].notna()) &
        (df["DeltaEst"].abs() >= cfg["min_delta_abs"]) &
        (df["DeltaEst"].abs() <= cfg["max_delta_abs"])
    )

    out = df.loc[filt].copy()

    if cfg["exclude_too_thin"]:
        out = out[out["PremiumLabel"] != "Too Thin"].copy()

    if not out.empty:
        out["FilterMode"] = mode_name

    return out


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    out["PremiumScore"] = (
        0.70 * min_max_scale(out["AnnualizedROC"]) +
        0.30 * min_max_scale(out["PremiumEfficiency"])
    )

    out["VolatilityScore"] = min_max_scale(out["IV"])

    out["LiquidityScore"] = (
        0.55 * min_max_scale(out["OpenInterest"]) +
        0.25 * min_max_scale(out["Volume"]) -
        0.20 * min_max_scale(out["Spread_Pct"])
    )

    out["SafetyScore"] = (
        0.45 * min_max_scale(out["ProbOTMEst"]) +
        0.35 * min_max_scale(out["BE_Buffer_Pct"]) +
        0.20 * min_max_scale(out["OTM_Pct"])
    )

    out["StockQualityScore"] = min_max_scale(out["StockQualityProxy"])

    out["Score"] = (
        0.26 * out["StockQualityScore"] +
        0.30 * out["PremiumScore"] +
        0.20 * out["VolatilityScore"] +
        0.12 * out["LiquidityScore"] +
        0.12 * out["SafetyScore"]
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
    if row["PremiumScore"] >= 0.75:
        reasons.append("strong premium")
    elif row["PremiumScore"] >= 0.60:
        reasons.append("decent premium")
    if row["VolatilityScore"] >= 0.70:
        reasons.append("high IV")
    if row["LiquidityScore"] >= 0.70:
        reasons.append("good liquidity")
    if row["SafetyScore"] >= 0.70:
        reasons.append("good cushion")
    if row["StockQualityScore"] >= 0.70:
        reasons.append("better underlying quality")
    return ", ".join(reasons[:4])


def run_scan(tickers, expiry, rf_rate):
    prices = fetch_last_prices(tickers)
    if prices.empty:
        return None, "No price data returned from Yahoo."

    strict_cfg = {
        "min_otm_pct": 0.05,
        "min_be_buffer_pct": 0.06,
        "min_delta_abs": 0.10,
        "max_delta_abs": 0.20,
        "max_spread_pct": 0.10,
        "min_oi": 300,
        "min_volume": 1,
        "min_mid": 0.50,
        "min_roc": 0.0050,
        "min_annualized_roc": 0.24,
        "exclude_too_thin": True,
    }

    relaxed_cfg = {
        "min_otm_pct": 0.03,
        "min_be_buffer_pct": 0.04,
        "min_delta_abs": 0.08,
        "max_delta_abs": 0.22,
        "max_spread_pct": 0.15,
        "min_oi": 100,
        "min_volume": 0,
        "min_mid": 0.20,
        "min_roc": 0.0025,
        "min_annualized_roc": 0.12,
        "exclude_too_thin": False,
    }

    strict_all = []
    relaxed_all = []

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
            hv20 = float(row["HV20"].iloc[0])
            ret20d = float(row["Ret20D"].iloc[0])

            cands = build_put_candidates(
                symbol=ticker,
                spot=spot,
                hv20=hv20,
                ret20d=ret20d,
                expiry=expiry,
                rf_rate=rf_rate,
            )

            if cands.empty:
                continue

            strict_hits = filter_candidates(cands, strict_cfg, "Strict")
            if not strict_hits.empty:
                strict_all.append(strict_hits)
            else:
                relaxed_hits = filter_candidates(cands, relaxed_cfg, "Relaxed")
                if not relaxed_hits.empty:
                    relaxed_all.append(relaxed_hits)

            time.sleep(1.2)

        except Exception:
            continue

    progress.empty()
    status.empty()

    if strict_all:
        ranked = pd.concat(strict_all, ignore_index=True)
        ranked = score_candidates(ranked)
        ranked = keep_best_per_ticker(ranked)
        ranked["WhyItRanked"] = ranked.apply(explain_row, axis=1)
        return ranked, None

    if relaxed_all:
        ranked = pd.concat(relaxed_all, ignore_index=True)
        ranked = score_candidates(ranked)
        ranked = keep_best_per_ticker(ranked)
        ranked["WhyItRanked"] = ranked.apply(explain_row, axis=1)
        return ranked, "No strict candidates passed. Showing relaxed candidates."

    return None, "No strict or relaxed candidates passed, or Yahoo returned no usable option-chain data."


# ---------------- Sidebar ----------------
with st.sidebar:
    ticker_str = st.text_area(
        "Tickers (keep to ~4-8 names on Yahoo)",
        "NVDA, MSFT, AAPL, AMZN, META, AVGO"
    )
    tickers = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]

    expiry_source_ticker = tickers[0] if tickers else "NVDA"
    expirations = []
    try:
        expirations = fetch_expirations(expiry_source_ticker)
    except Exception:
        expirations = []

    if expirations:
        expiry = st.selectbox("Choose expiry", options=expirations, index=0)
    else:
        expiry = st.text_input("Expiry (YYYY-MM-DD)", "2026-04-24")

    rf_rate = st.number_input(
        "Risk-free Rate",
        min_value=0.0,
        max_value=0.15,
        value=0.04,
        step=0.005,
        format="%.3f"
    )

if "scan_results" not in st.session_state:
    st.session_state["scan_results"] = None
if "scan_message" not in st.session_state:
    st.session_state["scan_message"] = None

if st.button("🚀 Scan Best High-Quality Put Opportunities", type="primary"):
    with st.spinner("Scanning put opportunities..."):
        results, message = run_scan(tickers=tickers, expiry=expiry, rf_rate=rf_rate)
        st.session_state["scan_results"] = results
        st.session_state["scan_message"] = message

if st.session_state["scan_message"]:
    if st.session_state["scan_results"] is None:
        st.error(st.session_state["scan_message"])
    else:
        st.warning(st.session_state["scan_message"])

results = st.session_state["scan_results"]

if results is None:
    st.info("Set your universe and click the scan button.")
else:
    top = results.iloc[0]
    st.success(
        f"Top setup: {top['Ticker']} {top['Strike']:.2f}P | "
        f"Mid ${top['Mid']:.2f} | Delta {top['DeltaEst']:.2f} | "
        f"Prob OTM {top['ProbOTMEst']:.0%} | "
        f"{top['PremiumLabel']} | {top['Setup']}"
    )

    display = results.copy()

    pct_cols = [
        "HV20", "IV", "OTM_Pct", "BE_Buffer_Pct", "ROC",
        "AnnualizedROC", "Spread_Pct", "ProbOTMEst"
    ]
    for col in pct_cols:
        display[col] = (display[col] * 100).round(2)

    score_cols = [
        "StockQualityScore", "PremiumScore", "VolatilityScore",
        "LiquidityScore", "SafetyScore", "Score"
    ]
    for col in score_cols:
        display[col] = display[col].round(3)

    display["DeltaEst"] = display["DeltaEst"].round(3)
    display["PremiumEfficiency"] = display["PremiumEfficiency"].round(4)

    st.dataframe(
        display[[
            "Rank", "Ticker", "FilterMode", "Setup", "PremiumLabel", "Expiry", "DTE",
            "Spot", "Strike", "Bid", "Ask", "Mid", "DeltaEst", "ProbOTMEst",
            "OTM_Pct", "BE_Buffer_Pct", "ROC", "AnnualizedROC", "HV20", "IV",
            "PremiumEfficiency", "OpenInterest", "Volume", "Spread_Pct",
            "StockQualityScore", "PremiumScore", "VolatilityScore",
            "LiquidityScore", "SafetyScore", "Score", "WhyItRanked"
        ]],
        use_container_width=True,
        hide_index=True
    )
