import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Wheel Pro Screener", layout="wide")
st.title("🎡 Wheel Strategy: Premium Selector")

# Diverse list: High Vol, Blue Chip, and Tech
TICKERS = ['TSLA', 'NVDA', 'AMD', 'AAPL', 'AMZN', 'MSFT', 'GOOGL', 'META', 'COIN', 'MSTR', 'AMD', 'MARA', 'JPM', 'DIS', 'GS']

if st.button("🔍 Scan for Weekly Plays"):
    results = []
    status = st.empty()
    
    for symbol in TICKERS:
        status.text(f"Checking {symbol}...")
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1y")
            if len(hist) < 50: continue
            
            # --- 1. EARNINGS CHECK (SOFT BLOCK) ---
            earnings_penalty = 0
            days_to_earn = 99
            if t.calendar is not None and not t.calendar.empty:
                next_earn = t.calendar.iloc[0, 0].replace(tzinfo=None)
                days_to_earn = (next_earn - datetime.now()).days
                if 0 <= days_to_earn <= 14:
                    earnings_penalty = 50 # Heavy penalty, but not a delete

            # --- 2. SUPPORT & RSI ---
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            price = hist['Close'].iloc[-1]
            # RSI Calculation
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain/loss)))
            rsi_val = rsi.iloc[-1]

            # --- 3. OPTIONS & 80% PROB ---
            exp = t.options[0]
            chain = t.option_chain(exp)
            # Find ~0.20 Delta strike (approx 10% OTM for these tickers)
            target = price * 0.90
            idx = (chain.puts['strike'] - target).abs().idxmin()
            opt = chain.puts.loc[idx]
            
            # Liquidity: Bid-Ask Spread
            spread = (opt['ask'] - opt['bid']) / ((opt['ask'] + opt['bid']) / 2)
            weekly_yield = ((opt['bid'] + opt['ask'])/2 / opt['strike']) * 100

            # --- FINAL SCORING ---
            score = 100
            if days_to_earn <= 14: score -= earnings_penalty
            if spread > 0.10: score -= 20   # Penalty for bad liquidity
            if price > sma_50 * 1.05: score -= 20 # Penalty for being "extended" (too high)
            if rsi_val > 60: score -= 15    # Penalty for being overbought
            
            # Bonuses
            if 30 < rsi_val < 45: score += 10 # Bonus for oversold
            if weekly_yield > 1.0: score += 10 # Bonus for high juice

            results.append({
                "Ticker": symbol,
                "Score": score,
                "Weekly %": round(weekly_yield, 2),
                "Strike": opt['strike'],
                "Dist to 50MA": f"{round(((price/sma_50)-1)*100, 1)}%",
                "RSI": round(rsi_val, 1),
                "Earn In": f"{days_to_earn}d",
                "IV %": round(opt['impliedVolatility']*100, 1)
            })
        except: continue
            
    status.empty()
    if results:
        df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.dataframe(df, use_container_width=True)
        st.info("Scores above 70 are prime Wheel candidates. Watch out for 'Earn In' < 7d!")
    else:
        st.error("Technical error fetching data. Try again.")
