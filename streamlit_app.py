import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. CONFIGURATION ---
TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'BRK-B', 'JNJ', 'JPM', 'V', 'PG', 'KO']

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_score(data, info, options_chain):
    score = 0
    details = {}
    
    # Fundamental Scoring
    fcf = info.get('freeCashflow', 0)
    market_cap = info.get('marketCap', 1)
    fcf_yield = (fcf / market_cap) * 100 if market_cap > 0 else 0
    if fcf_yield > 3: score += 10; details['FCF Yield'] = "✅"
    
    debt_equity = info.get('debtToEquity', 200)
    if debt_equity < 150: score += 10; details['Debt/Equity'] = "✅"
    
    payout = info.get('payoutRatio', 1)
    if payout < 0.6: score += 10; details['Payout Ratio'] = "✅"

    # Technical Scoring
    current_price = data['Close'].iloc[-1]
    sma_200 = data['Close'].rolling(window=200).mean().iloc[-1]
    rsi_vals = get_rsi(data['Close'])
    rsi = rsi_vals.iloc[-1]
    
    if current_price < sma_200 * 1.05: score += 15; details['Near 200SMA'] = "✅"
    if 30 < rsi < 55: score += 15; details['RSI Optimal'] = "✅"
    
    # Options Scoring
    avg_iv = options_chain.puts['impliedVolatility'].mean()
    if avg_iv > 0.20: score += 15; details['Healthy IV'] = "✅"
    
    spread = (options_chain.puts['ask'] - options_chain.puts['bid']).mean()
    if spread < 0.25: score += 15; details['Liquid'] = "✅"

    return score, details, rsi

# --- 2. UI ---
st.set_page_config(page_title="Put Screener", layout="wide")
st.title("🎯 Blue Chip Put Screener")

if st.button("Run Global Scan"):
    results = []
    for symbol in TICKERS:
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1y")
            if len(hist) < 200: continue
            
            exp = t.options[0]
            chain = t.option_chain(exp)
            
            score, crit, rsi_val = calculate_score(hist, t.info, chain)
            results.append({
                "Ticker": symbol, "Score": score, "Price": round(hist['Close'].iloc[-1], 2),
                "RSI": round(rsi_val, 1), "Checks": str(list(crit.keys()))
            })
        except: continue

    df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
    st.table(df)
