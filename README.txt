XAUUSD Multi-Timeframe SMC Signal Bot - README
---------------------------------------------
WHAT THIS IS
This Python project monitors XAUUSD (Gold) and sends trading signals to Telegram
when multi-timeframe Smart Money Concept (SMC) conditions align:
- HTF: H4 + H1 trend alignment (EMA50 vs EMA200)
- HTF: H1 OB / FVG detection (approximate)
- LTF: M5 BOS/CHoCH + retest of HTF zone + engulfing candle confirmation
- Risk management: 1:2 Risk:Reward, position sizing via ACCOUNT_BALANCE & RISK_PER_TRADE
- Cooldown & State tracking: one signal per M5 candle and one trade per HTF zone

REQUIREMENTS
- Python 3.9+
- See requirements.txt for pip packages

SETUP
1. Place the files in a directory on your machine or VPS.
2. Edit 'trading_bot.py' and set TELEGRAM_TOKEN and CHAT_ID.
   - Create a Telegram bot with @BotFather and get the token.
   - Start a chat with your bot and use getUpdates or your own helper to find CHAT_ID.
3. (Optional) To use Telegram Webhooks, expose the machine (VPS) with a public URL & TLS.
   - Example: run behind an nginx reverse-proxy with a valid certificate, or use a tunnel (ngrok)
   - Set webhook: https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<your-host>/<YOUR_TOKEN>
   - Alternatively, you can poll getUpdates instead of using webhooks (modify the code accordingly).
4. Install dependencies:
   pip install -r requirements.txt
5. Run:
   python trading_bot.py

NOTES & WARNINGS
- yfinance provides data that may be delayed ~1 minute and is not guaranteed for live trading.
- OB/FVG detection is an approximation designed for signal generation and backtesting. Visual/manual verification recommended.
- This project sends signals only — it does NOT execute live orders for you.
- Always test in a demo account & paper-trade before risking real capital.

FILES
- trading_bot.py  : Main bot script
- README.txt      : This file
- requirements.txt: Python dependencies

LICENSE & DISCLAIMER
Use at your own risk. This project is for educational purposes only.
