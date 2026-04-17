import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Tactical Wheel Screener", layout="wide")
st.title("🎡 Tactical Wheel: 80% POP Screener")

# Tickers with high options volume
TICKERS = ['TSLA', 'NVDA', 'AMD', 'AAPL', 'AMZN', 'MSFT', 'GOOGL', 'META', 'NFLX', 'COIN', 'MSTR']

if st.button("🔍 Scan for High-Probability Entry"):
    results = []
    status = st.empty()
    
    for symbol in TICKERS:
        status.text(f"Evaluating {symbol}...")
        try:
            t = yf.Ticker(symbol)
            
            # --- 1. HARD BLOCK: EARNINGS (BOOBY TRAP #1) ---
            # If earnings are in the next 14 days, we skip entirely
            calendar = t.calendar
            if calendar is not None and not calendar.empty:
                next_earnings = calendar.iloc[0, 0]
                days_to_earnings = (next_earnings.replace(tzinfo=None) - datetime.now()).days
                if 0 <= days_to_earnings <= 14:
                    continue 

            # --- 2. TECHNICAL SUPPORT (50-Day MA) ---
            hist = t.history(period="100d")
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            current_price = hist['Close'].iloc[-1]
            # Preference: Price is near or below 50MA (not overextended)
            dist_to_sma = (current_price - sma_50) / sma_50

            # --- 3. OPTIONS DATA (Liquidity & PCR) ---
            exp = t.options[0] # Nearest weekly
            chain = t.option_chain(exp)
            
            # Put/Call OI Ratio
            total_call_oi = chain.calls['openInterest'].sum()
            total_put_oi = chain.puts['openInterest'].sum()
            pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0

            # --- 4. 80% PROBABILITY STRIKE (0.20 Delta) ---
            # We target a strike roughly 8-10% below current price for high-vol tech
            target_strike = current_price * 0.90 
            idx = (chain.puts['strike'] - target_strike).abs().idxmin()
            opt = chain.puts.loc[idx]
            
            # Bid-Ask Spread %
            spread = (opt['ask'] - opt['bid']) / ((opt['ask'] + opt['bid']) / 2)

            # --- WEIGHTED SCORING ---
            score = 0
            # Spread check (Max 30) - High importance for execution
            if spread < 0.05: score += 30
            elif spread < 0.15: score += 15
            
            # Support check (Max 30) - Are we at a floor?
            if current_price < sma_50: score += 30 # Below MA = Entry Zone
            elif dist_to_sma < 0.05: score += 15   # Close to MA
            
            # PCR Sentiment (Max 20)
            if pcr_oi > 1.2: score += 20 # High Put OI = Institutional Floor
            
            # IV Juice (Max 20)
            if opt['impliedVolatility'] > 0.40: score += 20

            results.append({
                "Ticker": symbol,
                "Score": score,
                "Price": round(current_price, 2),
                "50MA": round(sma_50, 2),
                "Strike (80%)": opt['strike'],
                "Spread %": f"{round(spread*100, 1)}%",
                "PC Ratio": round(pcr_oi, 2),
                "IV %": round(opt['impliedVolatility']*100, 1)
            })
        except:
            continue
            
    status.empty()
    if results:
        df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("All stocks currently blocked (likely due to Earnings or low liquidity).")
