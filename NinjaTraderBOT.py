# NinjaTraderBOT.py
import os
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.utils import iswrapper
import threading
import time
from datetime import datetime
from discord_webhooks import DiscordWebhooks

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


class TestApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)
        self.nextValidOrderId = None
        self.ask_price = None
        self.bid_price = None
        self.order_filled = False
        self.current_order_id = None
        self.current_action = None
        self.lock = threading.Lock()

    @iswrapper
    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextValidOrderId = orderId

    @iswrapper
    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 2:  # BID price
            self.bid_price = price
        elif tickType == 1:  # ASK price
            self.ask_price = price

    @iswrapper
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        if status == 'Filled':
            self.order_filled = True
            self.send_discord_notification(orderId, self.current_action, filled, avgFillPrice)

    def place_market_order(self, action, symbol, quantity, limit_price, limit_offset=0.0):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = "USD"
        contract.exchange = "NASDAQ"

        order = Order()
        order.action = action
        order.orderType = "LMT"
        order.totalQuantity = quantity
        order.lmtPrice = limit_price + limit_offset if action == "BUY" else limit_price - limit_offset
        order.tif = "GTC"
        order.outsideRth = True
        order.eTradeOnly = ''
        order.firmQuoteOnly = ''

        with self.lock:
            self.current_order_id = self.nextValidOrderId
            self.current_action = action
            self.placeOrder(self.current_order_id, contract, order)
            self.nextValidOrderId += 1

    def cancel_current_order(self):
        with self.lock:
            if self.current_order_id:
                self.cancelOrder(self.current_order_id)

    def sell_with_timeout(self, symbol, quantity, fallback_bid_price, initial_ask_price, is_partial_profit=False):
        timeout = 8.0
        polling_interval = 2

        for _ in range(int(timeout / polling_interval)):
            if not self.order_filled:
                self.cancel_current_order()
                current_price = self.ask_price or initial_ask_price
                self.place_market_order("SELL", symbol, quantity, current_price)
                time.sleep(polling_interval)
                if self.order_filled:
                    print("Order filled successfully.")
                    return
            initial_ask_price = round((initial_ask_price * 1.001), 2)

        if not self.order_filled:
            self.cancel_current_order()
            self.place_market_order("SELL", symbol, quantity, fallback_bid_price)

    def send_discord_notification(self, orderId, action, filled, avgFillPrice):
        time_filled = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        webhook = DiscordWebhooks(WEBHOOK_URL)
        title_text = f'Order #{orderId} {action} Filled'
        webhook.set_content(content='@everyone', title=title_text,
                            description=f'Order ID {orderId} was successfully {action.lower()}ed.',
                            color=0x242424)
        webhook.set_footer(text=f'RTAlerts || {time_filled}')
        webhook.add_field(name='Action', value=action, inline=True)
        webhook.add_field(name='Filled Quantity', value=f'{filled}', inline=True)
        webhook.add_field(name='Average Fill Price', value=f'{avgFillPrice}', inline=True)
        webhook.add_field(name='Order ID', value=f'{orderId}', inline=True)
        webhook.add_field(name='Exchange', value='NASDAQ', inline=True)
        webhook.send()

    def run(self):
        super().run()


def main():
    app = TestApp()
    app.connect("127.0.0.1", 7497, 0)
    api_thread = threading.Thread(target=app.run, daemon=True)
    api_thread.start()


if __name__ == "__main__":
    main()
