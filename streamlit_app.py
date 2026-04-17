import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Dynamic Wheel", layout="wide")
st.title("🎡 Act 60: Strategic Wheel Screener")

TICKERS = ['TSLA', 'NVDA', 'AMD', 'AAPL', 'AMZN', 'MSFT', 'GOOGL', 'META', 'COIN', 'MSTR', 'NFLX', 'DIS', 'MARA']

if st.button("🔍 Run Strategic Scan"):
    results = []
    status = st.empty()
    
    for symbol in TICKERS:
        status.text(f"Analyzing {symbol}...")
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="150d")
            if hist.empty: continue
            
            # --- 1. EARNINGS HARD BLOCK (> 7 Days) ---
            days_to_earn = 99
            cal = t.get_calendar()
            if cal is not None and not cal.empty:
                next_earn = cal.iloc[0, 0].replace(tzinfo=None)
                days_to_earn = (next_earn - datetime.now()).days
                # Hard block: If earnings are 7 days or less, we delete from list
                if 0 <= days_to_earn <= 7:
                    continue 

            # --- 2. THE MATH FIX (PRE-MARKET / WEEKEND) ---
            price = hist['Close'].iloc[-1]
            exp = t.options[0]
            chain = t.option_chain(exp)
            target = price * 0.90
            idx = (chain.puts['strike'] - target).abs().idxmin()
            opt = chain.puts.loc[idx]
            
            # If market is closed, Bid/Ask might be 0. Use 'Last Price' as fallback.
            premium = (opt['bid'] + opt['ask']) / 2
            if premium <= 0:
                premium = opt['lastPrice']
            
            weekly_yield = (premium / opt['strike']) * 100

            # --- 3. LINEAR SCORING (ANTI-CLUSTERING) ---
            score = 50 # Start neutral
            
            # Distance to 50MA (Linear: More points for deeper value)
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            pct_from_sma = ((price / sma_50) - 1) * 100
            score -= (pct_from_sma * 2) # If price is 5% above SMA, score drops 10. If 5% below, score rises 10.

            # Yield Scoring (Linear: More juice = more points)
            score += (weekly_yield * 20) # 1.5% yield adds 30 points

            # RSI Buffer
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain/loss)))
            rsi_val = rsi.iloc[-1]
            score += (50 - rsi_val) # Points if RSI is low (oversold)

            # Earnings Safety (Bonus for far-out earnings)
            if days_to_earn > 30: score += 15

            results.append({
                "Ticker": symbol,
                "Score": round(score, 1),
                "Weekly %": round(weekly_yield, 2),
                "Strike": opt['strike'],
                "Dist 50MA": f"{round(pct_from_sma, 1)}%",
                "Earn In": f"{days_to_earn}d",
                "RSI": round(rsi_val, 1),
                "Premium": round(premium, 2)
            })
        except: continue
            
    status.empty()
    if results:
        df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No tickers passed the >7 day earnings filter.")
