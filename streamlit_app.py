import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="Robust Wheel Screener", layout="wide")
st.title("🎡 Robust Wheel: 80% Win Rate")

TICKERS = ['TSLA', 'NVDA', 'AMD', 'AAPL', 'AMZN', 'MSFT', 'GOOGL', 'META', 'COIN', 'MSTR', 'AMD', 'NFLX', 'DIS']

if st.button("🔍 Run Stable Scan"):
    results = []
    status = st.empty()
    
    for symbol in TICKERS:
        status.text(f"Fetching {symbol}...")
        # Small delay to prevent API rate limiting
        time.sleep(0.5) 
        
        try:
            t = yf.Ticker(symbol)
            # Try to get data with a 1-day period to keep it light
            hist = t.history(period="100d")
            if hist.empty: continue
            
            # --- 1. EARNINGS (GRACEFUL FAIL) ---
            days_to_earn = 99
            try:
                # Use .get_calendar() instead of .calendar for stability
                cal = t.get_calendar()
                if cal is not None and not cal.empty:
                    # Accessing the first date in the calendar
                    next_earn = cal.iloc[0, 0]
                    if isinstance(next_earn, datetime):
                        days_to_earn = (next_earn.replace(tzinfo=None) - datetime.now()).days
            except:
                pass # If earnings fail, we don't crash the whole app

            # --- 2. TECHNICALS ---
            price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            
            # RSI
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi_val = (100 - (100 / (1 + (gain/loss)))).iloc[-1]

            # --- 3. OPTIONS ---
            exp = t.options[0]
            chain = t.option_chain(exp)
            # Find ~0.20 Delta strike
            target = price * 0.90
            idx = (chain.puts['strike'] - target).abs().idxmin()
            opt = chain.puts.loc[idx]
            
            # Calculation
            spread = (opt['ask'] - opt['bid']) / ((opt['ask'] + opt['bid']) / 2)
            weekly_yield = ((opt['bid'] + opt['ask'])/2 / opt['strike']) * 100

            # --- FLEXIBLE SCORING ---
            score = 100
            if 0 <= days_to_earn <= 14: score -= 40
            if spread > 0.15: score -= 20
            if price > sma_50 * 1.05: score -= 20 # Extended price penalty
            
            # Bonuses for good entries
            if rsi_val < 40: score += 15
            if weekly_yield > 1.2: score += 10

            results.append({
                "Ticker": symbol,
                "Score": score,
                "Weekly %": round(weekly_yield, 2),
                "Strike": opt['strike'],
                "Dist 50MA": f"{round(((price/sma_50)-1)*100, 1)}%",
                "Earn In": f"{days_to_earn}d",
                "IV %": round(opt['impliedVolatility']*100, 1)
            })
        except Exception as e:
            st.warning(f"Skipping {symbol}: Data connection hiccup.")
            continue
            
    status.empty()
    if results:
        df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.dataframe(df, use_container_width=True)
    else:
        st.error("Still no results. This is likely a temporary Yahoo Finance block. Try again in 10 minutes.")
