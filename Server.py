# server.py
from flask import Flask, request, jsonify
from NinjaTraderBOT import TestApp
from waitress import serve
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Create a global instance of the TestApp class
ibkr_client = TestApp()

def start_ibkr():
    # Connect to IBKR
    ibkr_client.connect("127.0.0.1", 7497, 1)

    # Start a separate thread for the IBKR event loop
    api_thread = threading.Thread(target=ibkr_client.run, daemon=True)
    api_thread.start()

# Start the IBKR connection
start_ibkr()

@app.route('/send_signal', methods=['POST'])
def send_signal():
    data = request.json
    signal = data.get('signal')
    symbol = data.get('symbol')
    quantity = data.get('quantity')
    bid_price = data.get('bidPrice')
    ask_price = data.get('askPrice')
    is_partial_profit = data.get('isPartialProfit')

    try:
        with ThreadPoolExecutor(max_workers=10) as executor:
            if signal.lower() == "buy":
                executor.submit(ibkr_client.place_market_order, "BUY", symbol, quantity, ask_price, 0.10)
            elif signal.lower() == "sell":
                if is_partial_profit:
                    executor.submit(ibkr_client.sell_with_timeout, symbol, quantity, bid_price, ask_price)
                else:
                    executor.submit(ibkr_client.place_market_order, "SELL", symbol, quantity, bid_price, 0.10)
            else:
                return jsonify({"error": "Invalid signal. Use 'buy' or 'sell'."})

        return jsonify({"status": "Order placed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=5000, threads=32, connection_limit=1000, 
          channel_timeout=60, cleanup_interval=30, ident='TradingServer')
