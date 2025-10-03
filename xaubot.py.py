#!/usr/bin/env python3
"""
XAUUSD Multi-Timeframe SMC Signal Bot
-------------------------------------
Features:
- HTF: H4 + H1 trend (EMA50 vs EMA200) and OB/FVG detection (approximation)
- LTF: M5 CHoCH/BOS, retest + engulfing entry
- 1:2 Risk/Reward with position sizing by ACCOUNT_BALANCE and RISK_PER_TRADE
- Telegram commands: /start, /stop, /price
- Cooldown: one signal per M5 candle; one trade per HTF zone (state tracker)
- Runs every 5 minutes
Notes:
- Replace TELEGRAM_TOKEN and CHAT_ID with your own values before running.
- This script uses yfinance (data is likely delayed ~1m); not suitable for high-frequency live execution.
"""
import os
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime


# =====================
# User configurable settings
# =====================
PAIR = "GC=F"  # XAUUSD symbol in yfinance
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ACCOUNT_BALANCE = 10000.0
RISK_PER_TRADE = 0.01
BOT_ACTIVE = False
LOOKBACK_H1 = "14d"
LOOKBACK_5M = "5d"
SCHEDULE_MINUTES = 5

# State trackers
last_signal_candle = None
last_zone = None
last_signal_zone_time = None
last_update_id = None

# ---------------------
# Utilities
# ---------------------
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Failed to send telegram message:", e)

def get_updates():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": last_update_id + 1 if last_update_id else None}
    try:
        resp = requests.get(url, params=params, timeout=15).json()
        if "result" in resp:
            for update in resp["result"]:
                last_update_id = update["update_id"]
                handle_command(update)
    except Exception as e:
        print("Error in get_updates:", e)

def handle_command(update):
    global BOT_ACTIVE
    message = update.get("message")
    if not message:
        return
    chat_id = str(message["chat"]["id"])
    text = message.get("text", "").strip()

    if chat_id != str(CHAT_ID):
        print("Ignoring message from unknown chat:", chat_id)
        return

    if text == "/start":
        BOT_ACTIVE = True
        send_telegram("✅ Bot started. Monitoring XAUUSD (Gold).")
    elif text == "/stop":
        BOT_ACTIVE = False
        send_telegram("🛑 Bot stopped.")
    elif text == "/price":
        price = get_current_price()
        if price:
            send_telegram(f"💰 Current XAUUSD Price: {price:.2f}")
        else:
            send_telegram("Price not available right now.")
    else:
        send_telegram("Commands: /start, /stop, /price")

def get_data(interval, period="7d"):
    try:
        df = yf.download(
            PAIR,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False  # <---- Explicitly set this
        )
        df.dropna(inplace=True)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        return df
    except Exception as e:
        print(f"Error fetching {interval} data:", e)
        return None

def get_current_price():
    df = get_data("1m", "1d")
    if df is None or df.empty:
        return None
    return df['Close'].iloc[-1]

# ---------------------
# HTF Trend Bias (H4 + H1)
# ---------------------
def get_trend_htf():
    h4 = get_data("4h", period="30d")
    h1 = get_data("1h", period=LOOKBACK_H1)
    if h4 is None or h1 is None or h4.empty or h1.empty:
        return None
    h4['EMA50'] = h4['Close'].ewm(span=50).mean()
    h4['EMA200'] = h4['Close'].ewm(span=200).mean()
    h1['EMA50'] = h1['Close'].ewm(span=50).mean()
    h1['EMA200'] = h1['Close'].ewm(span=200).mean()
    h4_bias = "BULLISH" if h4['EMA50'].iloc[-1] > h4['EMA200'].iloc[-1] else "BEARISH"
    h1_bias = "BULLISH" if h1['EMA50'].iloc[-1] > h1['EMA200'].iloc[-1] else "BEARISH"
    return h4_bias if h4_bias == h1_bias else None

# ---------------------
# HTF OB/FVG
# ---------------------
def detect_ob_fvg_htf():
    df = get_data("1h", period=LOOKBACK_H1)
    if df is None or df.empty:
        return None, None, None
    for i in range(-12, -2):
        try:
            if df['Low'].iloc[i+1] > df['High'].iloc[i-1]:
                return "BULLISH_FVG", df.index[i+1], (df['High'].iloc[i-1] + df['Low'].iloc[i+1]) / 2
            if df['High'].iloc[i+1] < df['Low'].iloc[i-1]:
                return "BEARISH_FVG", df.index[i+1], (df['Low'].iloc[i-1] + df['High'].iloc[i+1]) / 2
        except: continue
    return None, None, None

# ---------------------
# LTF Entry
# ---------------------
def detect_entry_ltf(trend, zone_type, zone_price):
    df = get_data("5m", period=LOOKBACK_5M)
    if df is None or df.empty:
        return False, None, None, False, None
    recent_high = df['High'].rolling(window=12).max().iloc[-2]
    recent_low = df['Low'].rolling(window=12).min().iloc[-2]
    last_close = df['Close'].iloc[-1]
    structure = None
    if trend == "BULLISH" and last_close > recent_high:
        structure = "BOS_UP"
    elif trend == "BEARISH" and last_close < recent_low:
        structure = "BOS_DOWN"
    zone_retest_ok = False
    if zone_price:
        last_mid = (df['High'].iloc[-1] + df['Low'].iloc[-1]) / 2
        if abs(last_mid - zone_price) / zone_price <= 0.005:
            zone_retest_ok = True
    last, prev = df.iloc[-1], df.iloc[-2]
    engulfing = False
    if trend == "BULLISH" and last['Close'] > prev['High']:
        engulfing = True
    if trend == "BEARISH" and last['Close'] < prev['Low']:
        engulfing = True
    stop_loss = df['Low'].rolling(window=24).min().iloc[-2] if trend == "BULLISH" else df['High'].rolling(window=24).max().iloc[-2]
    entry_ok, entry_price = (True, last_close) if structure and zone_retest_ok and engulfing else (False, None)
    return entry_ok, entry_price, stop_loss, zone_retest_ok, df.index[-1]

# ---------------------
# Risk management
# ---------------------
def risk_management(entry_price, stop_loss, direction):
    if entry_price is None or stop_loss is None:
        return None, None
    if direction == "BUY":
        risk_per_unit = entry_price - stop_loss
        tp = entry_price + 2 * risk_per_unit
    else:
        risk_per_unit = stop_loss - entry_price
        tp = entry_price - 2 * risk_per_unit
    if risk_per_unit <= 0:
        return None, None
    risk_amount = ACCOUNT_BALANCE * RISK_PER_TRADE
    size = risk_amount / risk_per_unit
    return tp, size

# ---------------------
# Check signal
# ---------------------
def check_signal():
    global last_zone, last_signal_zone_time, last_signal_candle
    trend = get_trend_htf()
    if not trend: return None
    zone_type, zone_time, zone_price = detect_ob_fvg_htf()
    if not zone_type: return None
    if last_zone is None or zone_time != last_zone[1]:
        last_zone = (zone_type, zone_time, zone_price)
        last_signal_zone_time = None
    if last_signal_zone_time == zone_time: return None
    entry_ok, entry_price, stop_loss, zone_retest_ok, m5_time = detect_entry_ltf(trend, zone_type, zone_price)
    if not entry_ok: return None
    if last_signal_candle == m5_time: return None
    tp, size = risk_management(entry_price, stop_loss, "BUY" if trend == "BULLISH" else "SELL")
    if tp is None or size is None: return None
    last_signal_candle, last_signal_zone_time = m5_time, zone_time
    return (f"XAUUSD {trend} Signal ✅\nHTF Zone: {zone_type} @ {zone_price:.2f}\n"
            f"Entry: {entry_price:.2f}\nSL: {stop_loss:.2f}\nTP: {tp:.2f}\nSize: {size:.4f}\n"
            f"Time (UTC): {m5_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ---------------------
# Main loop
# ---------------------
def main():
    global BOT_ACTIVE
    send_telegram("🤖 Bot started (inactive). Use /start to activate.")
    while True:
        get_updates()
        if BOT_ACTIVE:
            signal = check_signal()
            if signal: send_telegram(signal)
        time.sleep(SCHEDULE_MINUTES * 60)

if __name__ == "__main__":
    main()
