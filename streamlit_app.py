import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & SCORING LOGIC ---
TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'BRK-B', 'JNJ', 'JPM', 'V', 'PG', 'KO']

def calculate_score(data, info, options_chain):
    score = 0
    details = {}
    
    # Fundamental Scoring (30 pts)
    fcf = info.get('freeCashflow', 0)
    market_cap = info.get('marketCap', 1)
    fcf_yield = (fcf / market_cap) * 100
    if fcf_yield > 3: score += 10; details['FCF Yield'] = "✅"
    
    debt_equity = info.get('debtToEquity', 200)
    if debt_equity < 150: score += 10; details['Debt/Equity'] = "✅"
    
    payout = info.get('payoutRatio', 1)
    if payout < 0.6: score += 10; details['Payout Ratio'] = "✅"

    # Technical Scoring (40 pts)
    current_price = data['Close'].iloc[-1]
    sma_200 = data['Close'].rolling(window=200).mean().iloc[-1]
    rsi = ta.rsi(data['Close'], length=14).iloc[-1]
    
    if current_price < sma_200 * 1.05: score += 15; details['Near 200SMA'] = "✅"
    if 30 < rsi < 50: score += 15; details['RSI Optimal'] = "✅"
    
    # Options Scoring (30 pts)
    # Simple IV Check (yfinance doesn't provide IV Rank directly, we use current IV)
    avg_iv = options_chain.puts['impliedVolatility'].mean()
    if avg_iv > 0.25: score += 15; details['High IV'] = "✅"
    
    spread = (options_chain.puts['ask'] - options_chain.puts['bid']).mean()
    if spread < 0.10: score += 15; details['Tight Spread'] = "✅"

    return score, details

# --- 2. STREAMLIT UI ---
st.set_page_config(layout="wide")
st.title("🎯 Blue Chip Weekly Put Screener")
st.write("Filtering the 'Critical 20' criteria for Cash Secured Puts.")

if st.button("Run Global Scan"):
    results = []
    
    for symbol in TICKERS:
        try:
            ticker = yf.Ticker(symbol)
            # Fetch 1 year of history for Technicals
            hist = ticker.history(period="1y")
            info = ticker.info
            
            # Fetch the closest weekly expiration
            expirations = ticker.options
            if not expirations: continue
            opt_chain = ticker.option_chain(expirations[0]) # Closest expiration
            
            score, crit_details = calculate_score(hist, info, opt_chain)
            
            results.append({
                "Ticker": symbol,
                "Score": score,
                "Price": round(hist['Close'].iloc[-1], 2),
                "RSI": round(ta.rsi(hist['Close']).iloc[-1], 2),
                "Checks": crit_details
            })
        except Exception as e:
            st.error(f"Error scanning {symbol}: {e}")

    # Display Results
    df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
    
    # Highlight high scores
    def color_score(val):
        color = 'green' if val >= 70 else 'orange' if val >= 40 else 'red'
        return f'color: {color}'

    st.table(df.style.applymap(color_score, subset=['Score']))

    # --- 3. DETAILED ANALYSIS ---
    selected_ticker = st.selectbox("Select Ticker for Strike Analysis", df['Ticker'])
    if selected_ticker:
        t = yf.Ticker(selected_ticker)
        chain = t.option_chain(t.options[0])
        puts = chain.puts[['strike', 'bid', 'ask', 'impliedVolatility', 'openInterest']]
        
        # Filter for "Safe" Delta strikes (Approximate)
        current_price = t.history(period="1d")['Close'].iloc[-1]
        target_puts = puts[(puts['strike'] < current_price * 0.95) & (puts['strike'] > current_price * 0.85)]
        
        st.subheader(f"Recommended Strikes for {selected_ticker} (Exp: {t.options[0]})")
        st.dataframe(target_puts)
