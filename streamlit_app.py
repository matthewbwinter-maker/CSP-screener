import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="CSP Premium Hunter", layout="wide")
st.title("💰 Weekly CSP Premium Hunter")
st.write("Prioritizing High IV, Liquidity, and Technical Entry.")

# High-liquidity Blue Chips & High-Vol Tech "Want-to-Owns"
TICKERS = ['TSLA', 'NVDA', 'AMD', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'NFLX', 'META', 'JPM', 'GS', 'DIS']

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

if st.button("🔥 Scan for Premiums"):
    results = []
    status = st.empty()
    
    for symbol in TICKERS:
        status.text(f"Checking {symbol} for juice...")
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1y")
            if len(hist) < 30: continue
            
            # 1. Fetch Option Chain for the nearest Weekly
            exp = t.options[0]
            chain = t.option_chain(exp)
            
            # --- METRIC CALCULATIONS ---
            # Volatility (IV)
            mean_iv = chain.puts['impliedVolatility'].mean()
            iv_val = mean_iv * 100
            
            # Liquidity (Open Interest)
            total_oi = chain.puts['openInterest'].sum()
            
            # Technicals (RSI)
            rsi = get_rsi(hist['Close']).iloc[-1]
            
            # Safety Nets (Fundamentals)
            info = t.info
            debt_ratio = info.get('debtToEquity', 200)
            payout = info.get('payoutRatio', 1)

            # --- SCORING (The Premium Hunter Mix) ---
            score = 0
            if iv_val > 30: score += 30 # Primary Target: High Premium
            if total_oi > 1000: score += 20 # Can we get out easily?
            if 30 < rsi < 48: score += 20 # Are we at a local bottom?
            if debt_ratio < 150: score += 15 # Solvency Check
            if payout < 0.85: score += 15 # Reduced priority safety net
            
            results.append({
                "Ticker": symbol,
                "Score": score,
                "IV %": round(iv_val, 1),
                "RSI": round(rsi, 1),
                "Open Int": int(total_oi),
                "Price": round(hist['Close'].iloc[-1], 2),
                "Exp": exp
            })
        except:
            continue
            
    status.empty()
    
    if results:
        df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        # Display with high-score highlighting
        st.dataframe(df.style.background_gradient(subset=['Score', 'IV %'], cmap='YlGn'))
    else:
        st.error("No data found. Check your internet connection or API limits.")
