import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Act 60 Wheel Engine",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────
# CUSTOM CSS — Bloomberg Terminal meets Puerto Rico
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0a0e1a;
    color: #c8d4e8;
}

.stApp { background-color: #0a0e1a; }

h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; color: #00d4aa; letter-spacing: -0.02em; }

.metric-card {
    background: linear-gradient(135deg, #0f1629 0%, #131d35 100%);
    border: 1px solid #1e2d4a;
    border-left: 3px solid #00d4aa;
    border-radius: 4px;
    padding: 16px 20px;
    margin: 4px 0;
}

.score-elite  { color: #00ff88; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.score-strong { color: #00d4aa; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.score-ok     { color: #f5a623; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.score-weak   { color: #e05252; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }

.stDataFrame { border: 1px solid #1e2d4a !important; border-radius: 4px; }

.sidebar-header {
    font-family: 'IBM Plex Mono', monospace;
    color: #00d4aa;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    border-bottom: 1px solid #1e2d4a;
    padding-bottom: 6px;
    margin-bottom: 12px;
}

div[data-testid="stMetric"] {
    background: #0f1629;
    border: 1px solid #1e2d4a;
    border-radius: 4px;
    padding: 10px 14px;
}

div[data-testid="stMetric"] label { color: #6b7a99 !important; font-size: 11px; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #00d4aa !important; font-family: 'IBM Plex Mono', monospace; font-size: 1.4rem; }

.stButton > button {
    background: linear-gradient(90deg, #00d4aa, #0095ff);
    color: #0a0e1a;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    border: none;
    border-radius: 3px;
    padding: 10px 28px;
    font-size: 13px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    width: 100%;
}

.stButton > button:hover { opacity: 0.85; }

.tag-act60 {
    background: #00d4aa22;
    border: 1px solid #00d4aa55;
    color: #00d4aa;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 2px;
    letter-spacing: 0.08em;
}

.warn-box {
    background: #2a1a00;
    border: 1px solid #f5a62355;
    border-left: 3px solid #f5a623;
    padding: 10px 14px;
    border-radius: 3px;
    font-size: 12px;
    color: #c8a44a;
    margin: 8px 0;
}

.info-box {
    background: #001a2a;
    border: 1px solid #0095ff44;
    border-left: 3px solid #0095ff;
    padding: 10px 14px;
    border-radius: 3px;
    font-size: 12px;
    color: #6bacd4;
    margin: 8px 0;
}

.stProgress > div > div { background-color: #00d4aa; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────
col_title, col_tag = st.columns([5, 1])
with col_title:
    st.markdown("## ⚙ ACT 60 WHEEL ENGINE")
    st.markdown("<span style='color:#6b7a99; font-size:13px; font-family:IBM Plex Mono'>Cash-Secured Put & Covered Call Screener — PRSCI Premium Optimizer</span>", unsafe_allow_html=True)
with col_tag:
    st.markdown("<br><span class='tag-act60'>PRSCI TAX-FREE</span>", unsafe_allow_html=True)

st.markdown("---")

# ──────────────────────────────────────────────
# ACT 60 EXPLAINER
# ──────────────────────────────────────────────
with st.expander("📋 Act 60 CSP Strategy Logic", expanded=False):
    st.markdown("""
    <div class='info-box'>
    <b>Why options income is central to Act 60:</b> Premium collected from selling puts/calls while a bona fide Puerto Rico resident 
    qualifies as Puerto Rico-Sourced Capital Income (PRSCI) — taxed at 0% on gains. This makes the <b>annualized yield</b> the 
    single most important scoring factor, not just absolute premium. A 2% weekly yield annualizes to ~104% — but only if the 
    contract is liquid, the spread is tight, and you're not selling into an IV crush or earnings event.
    </div>
    
    **Scoring weights used in this screener:**
    | Factor | Weight | Rationale |
    |---|---|---|
    | Annualized Yield | 35% | PRSCI income is tax-free — maximize premium quality |
    | IV Rank (IVR) | 20% | Sell when vol is expensive, not cheap |
    | Liquidity Score | 15% | Tight spreads = execution edge, no slippage tax |
    | Technical Setup | 15% | SMA distance + RSI = entry timing signal |
    | Earnings Safety | 10% | Hard blocks <7d; bonus for >30d runway |
    | Delta/Strike Zone | 5% | 0.25–0.35 delta = optimal premium/assignment balance |
    """, unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR — CONTROLS
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div class='sidebar-header'>🏝 Act 60 Parameters</div>", unsafe_allow_html=True)

    st.markdown("<div class='sidebar-header'>Universe</div>", unsafe_allow_html=True)
    default_tickers = ['TSLA', 'NVDA', 'AMD', 'AAPL', 'AMZN', 'MSFT', 'GOOGL', 'META',
                       'COIN', 'MSTR', 'NFLX', 'DIS', 'MARA', 'PLTR', 'HOOD', 'SOFI', 'IBIT', 'SPY', 'QQQ']
    ticker_input = st.text_area(
        "Tickers (comma-separated)",
        value=", ".join(default_tickers),
        height=100
    )
    TICKERS = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

    st.markdown("<div class='sidebar-header'>Filters</div>", unsafe_allow_html=True)
    min_annual_yield = st.slider("Min Annualized Yield (%)", 20, 150, 40, step=5,
                                  help="Annualized = (weekly % × 52). PRSCI-free income — set high.")
    max_spread_pct = st.slider("Max Bid-Ask Spread (% of mid)", 5, 50, 25, step=5,
                                help="Spread as % of premium. Wider = worse fill, friction erodes yield.")
    min_oi = st.number_input("Min Open Interest", min_value=0, value=50, step=10,
                              help="Low OI = illiquid = bad fills on entry and exit.")
    min_volume = st.number_input("Min Contract Volume", min_value=0, value=10, step=5)
    earnings_hard_block = st.slider("Earnings Hard Block (days)", 3, 14, 7,
                                     help="Skip any ticker with earnings within this many days.")

    st.markdown("<div class='sidebar-header'>Strike Targeting</div>", unsafe_allow_html=True)
    strike_offset = st.slider("Strike Distance from Price (%)", 5, 20, 10, step=1,
                               help="10% OTM is classic for high-IV names. Adjust per your assignment comfort.")
    target_delta_min = st.slider("Min Target Delta", 0.10, 0.40, 0.20, step=0.01)
    target_delta_max = st.slider("Max Target Delta", 0.20, 0.50, 0.40, step=0.01)

    st.markdown("<div class='sidebar-header'>Expiry</div>", unsafe_allow_html=True)
    dte_preference = st.radio("DTE Target", ["Nearest weekly (~7d)", "2-week (~14d)", "Monthly (~30d)"],
                               help="Shorter = more rolls, more PRSCI events. Longer = fewer decisions.")

    st.markdown("<div class='sidebar-header'>Scoring Weights</div>", unsafe_allow_html=True)
    w_yield   = st.slider("Yield Weight",    0.0, 1.0, 0.35, 0.05)
    w_ivr     = st.slider("IV Rank Weight",  0.0, 1.0, 0.20, 0.05)
    w_liq     = st.slider("Liquidity Weight",0.0, 1.0, 0.15, 0.05)
    w_tech    = st.slider("Technical Weight",0.0, 1.0, 0.15, 0.05)
    w_earn    = st.slider("Earnings Weight", 0.0, 1.0, 0.10, 0.05)
    w_delta   = st.slider("Delta Weight",    0.0, 1.0, 0.05, 0.05)

    total_w = w_yield + w_ivr + w_liq + w_tech + w_earn + w_delta
    if abs(total_w - 1.0) > 0.01:
        st.warning(f"Weights sum to {total_w:.2f}. Scores will be normalized.")

    run_scan = st.button("⚡ RUN SCAN")

# ──────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────

def compute_rsi(series, window=14):
    delta = series.diff()
    gain  = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def compute_iv_rank(hist_close, current_iv):
    """
    Approximate HV-based IV rank: where does current IV sit in its 52-week range?
    Uses 30-day realized vol as a proxy since yfinance doesn't give us historical IV.
    """
    returns = hist_close.pct_change().dropna()
    if len(returns) < 30:
        return 50.0  # neutral default
    # rolling 30d realized vol, annualized
    rolling_vols = returns.rolling(30).std() * np.sqrt(252) * 100
    rolling_vols = rolling_vols.dropna()
    if rolling_vols.empty:
        return 50.0
    vol_min = rolling_vols.min()
    vol_max = rolling_vols.max()
    if vol_max == vol_min:
        return 50.0
    ivr = ((current_iv - vol_min) / (vol_max - vol_min)) * 100
    return float(np.clip(ivr, 0, 100))

def get_expiry_index(options_list, dte_pref):
    """Pick the right expiry index based on DTE preference."""
    today = datetime.now()
    targets = {"Nearest weekly (~7d)": 7, "2-week (~14d)": 14, "Monthly (~30d)": 30}
    target_days = targets.get(dte_pref, 7)
    best_idx = 0
    best_diff = 9999
    for i, exp_str in enumerate(options_list[:8]):  # limit search
        try:
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
            diff = abs((exp_dt - today).days - target_days)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        except:
            continue
    return best_idx

def score_ticker(symbol, hist, price, opt, days_to_earn, implied_vol, dte_days):
    """
    Weighted Act 60 score. Returns dict with subscores.
    All subscores normalized 0–100 before weighting.
    """
    scores = {}

    # --- 1. YIELD SCORE (weight: w_yield) ---
    mid_prem = (opt['bid'] + opt['ask']) / 2
    if mid_prem <= 0:
        mid_prem = opt['lastPrice']
    if mid_prem <= 0 or opt['strike'] <= 0:
        return None

    weekly_pct = (mid_prem / opt['strike']) * 100
    # Annualize: compress to 7-day equivalent, then × 52
    annualized = (weekly_pct / max(dte_days, 1)) * 365
    # Normalize 0–100: treat 0%=0, 100% annual=100 (cap at 150%)
    scores['yield_raw']       = round(annualized, 1)
    scores['yield_weekly_pct'] = round(weekly_pct, 2)
    scores['yield_score']     = min(100, (annualized / 150) * 100)

    # --- 2. IV RANK SCORE (weight: w_ivr) ---
    ivr = compute_iv_rank(hist['Close'], implied_vol * 100)
    scores['ivr']       = round(ivr, 1)
    scores['ivr_score'] = ivr  # already 0–100

    # --- 3. LIQUIDITY SCORE (weight: w_liq) ---
    bid, ask = opt['bid'], opt['ask']
    spread = ask - bid
    mid    = (bid + ask) / 2 if mid_prem > 0 else opt['lastPrice']
    spread_pct = (spread / mid * 100) if mid > 0 else 100
    oi    = opt.get('openInterest', 0) or 0
    vol   = opt.get('volume', 0) or 0

    # Spread score: 0% spread = 100, 25%+ = 0
    spread_score = max(0, 100 - (spread_pct / 25 * 100))
    # OI score: log scale, 1000 OI = 100 score
    oi_score     = min(100, (np.log1p(oi) / np.log1p(1000)) * 100)
    # Volume score
    vol_score    = min(100, (np.log1p(vol) / np.log1p(200)) * 100)
    scores['spread_pct']    = round(spread_pct, 1)
    scores['oi']            = int(oi)
    scores['vol']           = int(vol)
    scores['liq_score']     = (spread_score * 0.5) + (oi_score * 0.3) + (vol_score * 0.2)

    # Filter: hard blocks on spread and OI
    if spread_pct > max_spread_pct:
        scores['FILTERED'] = f"Spread {spread_pct:.0f}% > max {max_spread_pct}%"
        return scores
    if oi < min_oi:
        scores['FILTERED'] = f"OI {oi} < min {min_oi}"
        return scores
    if vol < min_volume:
        scores['FILTERED'] = f"Vol {vol} < min {min_volume}"
        return scores

    # --- 4. TECHNICAL SCORE (weight: w_tech) ---
    sma_50 = hist['Close'].rolling(50).mean().iloc[-1]
    sma_200 = hist['Close'].rolling(200).mean().iloc[-1] if len(hist) >= 200 else sma_50
    rsi_val  = compute_rsi(hist['Close']).iloc[-1]
    pct_from_sma50 = ((price / sma_50) - 1) * 100

    # Ideal: price near or slightly below 50SMA (buying opportunity territory)
    # Score peaks at -5% to +0% from SMA50
    sma_score = max(0, 100 - abs(pct_from_sma50 + 2.5) * 4)
    # RSI: ideal 35–50 (not oversold crash, not overbought)
    rsi_score = max(0, 100 - abs(rsi_val - 42.5) * 2.5)
    # 200MA trend: price above 200MA = bullish backdrop (good for wheel)
    trend_score = 100 if price > sma_200 else 40

    scores['rsi']         = round(rsi_val, 1)
    scores['pct_sma50']   = round(pct_from_sma50, 1)
    scores['tech_score']  = (sma_score * 0.45) + (rsi_score * 0.35) + (trend_score * 0.20)

    # --- 5. EARNINGS SAFETY (weight: w_earn) ---
    if days_to_earn <= 7:
        scores['FILTERED'] = f"Earnings in {days_to_earn}d"
        return scores
    elif days_to_earn <= 14:
        earn_score = 20
    elif days_to_earn <= 21:
        earn_score = 50
    elif days_to_earn <= 30:
        earn_score = 75
    else:
        earn_score = 100
    scores['earn_score'] = earn_score

    # --- 6. DELTA SCORE (weight: w_delta) ---
    delta_val = abs(opt.get('delta', 0) or 0)
    if delta_val == 0:
        # Approximate delta from moneyness if not available
        moneyness = opt['strike'] / price
        delta_val = max(0.05, 0.5 - (1 - moneyness) * 2.5)
    scores['delta'] = round(delta_val, 3)
    # Score peaks at target_delta center
    delta_center = (target_delta_min + target_delta_max) / 2
    delta_score  = max(0, 100 - abs(delta_val - delta_center) * 500)
    scores['delta_score'] = delta_score

    # --- COMPOSITE SCORE ---
    weight_sum = w_yield + w_ivr + w_liq + w_tech + w_earn + w_delta
    if weight_sum == 0:
        weight_sum = 1
    composite = (
        scores['yield_score'] * w_yield +
        scores['ivr_score']   * w_ivr   +
        scores['liq_score']   * w_liq   +
        scores['tech_score']  * w_tech  +
        scores['earn_score']  * w_earn  +
        scores['delta_score'] * w_delta
    ) / weight_sum

    scores['composite'] = round(composite, 1)
    scores['premium']   = round(mid_prem, 2)
    scores['strike']    = opt['strike']
    scores['days_to_earn'] = days_to_earn
    scores['dte'] = dte_days
    return scores


# ──────────────────────────────────────────────
# MAIN SCAN
# ──────────────────────────────────────────────
if run_scan:
    results  = []
    filtered = []

    progress_bar = st.progress(0)
    status_text  = st.empty()

    for i, symbol in enumerate(TICKERS):
        progress_bar.progress((i + 1) / len(TICKERS))
        status_text.markdown(f"<span style='font-family:IBM Plex Mono;color:#6b7a99;font-size:12px'>Scanning {symbol}...</span>", unsafe_allow_html=True)

        try:
            t    = yf.Ticker(symbol)
            hist = t.history(period="252d")
            if len(hist) < 30:
                filtered.append({"Ticker": symbol, "Reason": "Insufficient history"})
                continue

            price = hist['Close'].iloc[-1]

            # ── EARNINGS CHECK ──
            days_to_earn = 99
            try:
                cal = t.get_calendar()
                if cal is not None and not cal.empty:
                    next_earn = pd.to_datetime(cal.iloc[0, 0]).replace(tzinfo=None)
                    days_to_earn = (next_earn - datetime.now()).days
                    if 0 <= days_to_earn <= earnings_hard_block:
                        filtered.append({"Ticker": symbol, "Reason": f"Earnings in {days_to_earn}d (hard block)"})
                        continue
            except:
                pass

            # ── OPTION CHAIN ──
            if not t.options:
                filtered.append({"Ticker": symbol, "Reason": "No options available"})
                continue

            exp_idx = get_expiry_index(t.options, dte_preference)
            exp_str = t.options[exp_idx]
            exp_dt  = datetime.strptime(exp_str, "%Y-%m-%d")
            dte_days = max(1, (exp_dt - datetime.now()).days)

            chain = t.option_chain(exp_str)
            puts  = chain.puts

            if puts.empty:
                filtered.append({"Ticker": symbol, "Reason": "No puts on chain"})
                continue

            # ── STRIKE SELECTION ──
            target_strike = price * (1 - strike_offset / 100)
            idx = (puts['strike'] - target_strike).abs().idxmin()
            opt = puts.loc[idx]

            # ── IMPLIED VOL ──
            implied_vol = opt.get('impliedVolatility', 0) or 0
            if implied_vol == 0:
                implied_vol = hist['Close'].pct_change().std() * np.sqrt(252)

            # ── SCORE ──
            s = score_ticker(symbol, hist, price, opt, days_to_earn, implied_vol, dte_days)
            if s is None:
                filtered.append({"Ticker": symbol, "Reason": "Scoring error"})
                continue
            if 'FILTERED' in s:
                filtered.append({"Ticker": symbol, "Reason": s['FILTERED']})
                continue

            # Check annualized yield minimum
            if s.get('yield_raw', 0) < min_annual_yield:
                filtered.append({"Ticker": symbol, "Reason": f"Annual yield {s['yield_raw']:.0f}% < min {min_annual_yield}%"})
                continue

            results.append({
                "Ticker"      : symbol,
                "Score"       : s['composite'],
                "Annual %"    : f"{s['yield_raw']:.0f}%",
                "Weekly %"    : f"{s['yield_weekly_pct']:.2f}%",
                "Strike"      : s['strike'],
                "Price"       : round(price, 2),
                "Premium"     : s['premium'],
                "DTE"         : f"{dte_days}d",
                "IV Rank"     : f"{s['ivr']:.0f}",
                "Spread"      : f"{s['spread_pct']:.1f}%",
                "OI"          : s['oi'],
                "RSI"         : s['rsi'],
                "Dist 50MA"   : f"{s['pct_sma50']:+.1f}%",
                "Delta"       : s['delta'],
                "Earn In"     : f"{s['days_to_earn']}d",
                "Expiry"      : exp_str,
                # Sub-scores for diagnostics
                "_yield_s"    : round(s['yield_score'], 0),
                "_ivr_s"      : round(s['ivr_score'], 0),
                "_liq_s"      : round(s['liq_score'], 0),
                "_tech_s"     : round(s['tech_score'], 0),
                "_earn_s"     : round(s['earn_score'], 0),
                "_delta_s"    : round(s['delta_score'], 0),
            })

        except Exception as e:
            filtered.append({"Ticker": symbol, "Reason": f"Error: {str(e)[:60]}"})
            continue

    progress_bar.empty()
    status_text.empty()

    # ──────────────────────────────────────────
    # RESULTS DISPLAY
    # ──────────────────────────────────────────
    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False).reset_index(drop=True)

        # Summary metrics
        st.markdown("### 📊 Scan Summary")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Passed Filters", len(df))
        with m2:
            st.metric("Filtered Out", len(filtered))
        with m3:
            best_yield = df["Annual %"].str.rstrip("%").astype(float).max() if not df.empty else 0
            st.metric("Best Annual Yield", f"{best_yield:.0f}%")
        with m4:
            top_score = df["Score"].max() if not df.empty else 0
            st.metric("Top Composite Score", f"{top_score:.1f}/100")

        st.markdown("---")

        # Color-code the Score column
        def score_color(val):
            if val >= 75: return 'color: #00ff88; font-weight: 700'
            elif val >= 55: return 'color: #00d4aa; font-weight: 600'
            elif val >= 40: return 'color: #f5a623'
            else: return 'color: #e05252'

        def yield_color(val):
            try:
                v = float(str(val).rstrip('%'))
                if v >= 80: return 'color: #00ff88'
                elif v >= 50: return 'color: #00d4aa'
                elif v >= 30: return 'color: #f5a623'
                else: return 'color: #e05252'
            except: return ''

        # Main table — hide internal sub-score cols
        display_cols = [c for c in df.columns if not c.startswith("_")]
        display_df = df[display_cols]

        styled = display_df.style\
            .applymap(score_color, subset=["Score"])\
            .applymap(yield_color, subset=["Annual %"])\
            .set_properties(**{
                'background-color': '#0f1629',
                'color': '#c8d4e8',
                'border': '1px solid #1e2d4a',
                'font-family': 'IBM Plex Mono, monospace',
                'font-size': '12px'
            })\
            .set_table_styles([{
                'selector': 'th',
                'props': [('background-color', '#131d35'), ('color', '#00d4aa'),
                          ('font-family', 'IBM Plex Mono, monospace'), ('font-size', '11px'),
                          ('border', '1px solid #1e2d4a'), ('text-transform', 'uppercase')]
            }])\
            .format({"Score": "{:.1f}"})

        st.markdown("### 🏆 Ranked Opportunities")
        st.dataframe(styled, use_container_width=True, height=400)

        # ── SCORE BREAKDOWN ──
        st.markdown("### 🔍 Score Breakdown by Component")
        breakdown_data = []
        for _, row in df.iterrows():
            breakdown_data.append({
                "Ticker": row["Ticker"],
                "Yield (35%)":    row["_yield_s"],
                "IV Rank (20%)":  row["_ivr_s"],
                "Liquidity (15%)": row["_liq_s"],
                "Technical (15%)": row["_tech_s"],
                "Earnings (10%)": row["_earn_s"],
                "Delta (5%)":     row["_delta_s"],
                "COMPOSITE":      row["Score"],
            })
        bdf = pd.DataFrame(breakdown_data).set_index("Ticker")
        st.dataframe(
            bdf.style.background_gradient(cmap='RdYlGn', vmin=0, vmax=100)
               .format("{:.0f}")
               .set_properties(**{'font-family': 'IBM Plex Mono, monospace', 'font-size': '12px'}),
            use_container_width=True
        )

        # ── TOP PICK DETAIL ──
        if len(df) > 0:
            top = df.iloc[0]
            st.markdown(f"### ⭐ Top Pick: {top['Ticker']}")
            cols = st.columns(4)
            vals = [
                ("Strike", top['Strike']),
                ("Expiry", top['Expiry']),
                ("Premium", f"${top['Premium']}"),
                ("Annual Yield", top['Annual %']),
            ]
            for col, (label, value) in zip(cols, vals):
                col.metric(label, value)

            st.markdown(f"""
            <div class='info-box'>
            📋 <b>Trade Setup ({top['Ticker']}):</b><br>
            Sell to open 1 put | Strike ${top['Strike']} | Exp {top['Expiry']} | Collect ${top['Premium']} per contract (${'%.0f' % (top['Premium']*100)} per contract notional)<br>
            Capital required (cash-secured): ${top['Price'] * 100:,.0f} per contract<br>
            Yield on capital: {top['Weekly %']} ({top['Annual %']} annualized) — qualifies as PRSCI under Act 60 once PR residency established
            </div>
            """, unsafe_allow_html=True)

        # ── CSV EXPORT ──
        csv = display_df.to_csv(index=False)
        st.download_button(
            "⬇ Export to CSV",
            data=csv,
            file_name=f"act60_wheel_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )

    else:
        st.warning("No tickers passed all filters. Try relaxing: spread %, min yield, OI, or earnings block.")

    # ── FILTERED TICKERS ──
    if filtered:
        with st.expander(f"🚫 Filtered Out ({len(filtered)} tickers)", expanded=False):
            fdf = pd.DataFrame(filtered)
            st.dataframe(fdf, use_container_width=True)

# ──────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center; font-family:IBM Plex Mono, monospace; font-size:10px; color:#3a4a6a; padding: 8px'>
ACT 60 WHEEL ENGINE · PRSCI PREMIUM OPTIMIZER · For informational use only. Not financial advice.<br>
Options involve risk. Verify Act 60 decree eligibility with qualified PR tax counsel before treating income as PRSCI.
</div>
""", unsafe_allow_html=True)
