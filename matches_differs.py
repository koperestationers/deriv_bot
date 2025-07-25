import asyncio
import websockets
import json
import os
import logging
import math
import random
from datetime import datetime
from collections import deque, Counter


# Configuration
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "QqPlMT0ilFFqPlR")  # George Demo
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1089")  # Generic
ACCOUNT_CURRENCY = os.getenv("DERIV_ACCOUNT_CURRENCY", "USD")
MIN_STAKE = 0.35
PROFIT_PERCENTAGE = 5.71
SYMBOL = "1HZ10V"
MAX_TIMEOUT = 3  # Maximum timeout for trade responses in seconds


class DerivBot:
    def __init__(self):
        self.logger = logging.getLogger("DerivBot")
        self.endpoint = f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}"
        self.balance = 0
        self.base_stake = MIN_STAKE
        self.stake = self.base_stake
        self.matingale_stake = self.base_stake
        self.largest_stake = self.base_stake
        self.largest_stake_info = None
        self.min_account_balance = self.base_stake
        self.profit_percentage = PROFIT_PERCENTAGE / 100
        self.base_profit_on_win = self.profit_percentage * self.stake
        self.outcome_on_win = self.stake + self.base_profit_on_win
        self.tick_history = deque(maxlen=1000)  # Store last 1000 ticks
        self.least_digit = 0

    async def connect_forever(self):
        reconnect_delay = 1
        while True:
            try:
                async with websockets.connect(self.endpoint) as ws:
                    self.ws = ws
                    await self.authorize()
                    # Fetch initial 1000 ticks
                    initial_ticks = await self.fetch_ticks(count=1000)
                    self.tick_history.extend(initial_ticks)
                    await self.trade_loop()
            except websockets.exceptions.ConnectionClosedError:
                self.logger.warning(f"WebSocket failed. Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)

    async def authorize(self):
        await self.ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))
        try:
            res = json.loads(await self.ws.recv())
            if res.get("msg_type") == "authorize":
                self.balance = res["authorize"]["balance"]
                self.logger.info(f"Authorized. Balance: {self.balance}")
            else:
                self.logger.error("Authorization failed")
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON in authorize response")

    async def fetch_ticks(self, count=1000):
        request = {
            "ticks_history": SYMBOL,
            "end": "latest",
            "count": count,
            "style": "ticks"
        }
        await self.ws.send(json.dumps(request))
        try:
            res = json.loads(await self.ws.recv())
            if res.get("msg_type") == "history":
                return res["history"]["prices"]
            else:
                self.logger.error("Failed to fetch ticks")
                return []
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON in ticks response")
            return []

    def get_least_occurring_digit(self, ticks):
        last_digits = [int(str(price).split('.')[1][-1]) for price in ticks if len(str(price).split('.')) > 1]
        digit_counts = Counter(last_digits)
        if digit_counts:
            return min(digit_counts, key=digit_counts.get)
        return random.randint(0, 9)  # Fallback if no digits found

    async def trade_loop(self):
        while True:
            await self.place_trade()
            await asyncio.sleep(0.01)

    async def place_trade(self):
        # Fetch latest 20 ticks and update tick_history
        latest_ticks = await self.fetch_ticks(count=20)
        self.tick_history.extend(latest_ticks)  # Replaces oldest 20 due to maxlen=1000
        self.least_digit = self.get_least_occurring_digit(self.tick_history)
        buy_request = {
            "buy": 1,
            "price": self.stake,
            "parameters": {
                "amount": self.stake,
                "basis": "stake",
                "contract_type": "DIGITDIFF",
                "currency": ACCOUNT_CURRENCY,
                "barrier": str(self.least_digit),
                "duration": 1,
                "duration_unit": "t",
                "symbol": SYMBOL
            }
        }
        await self.ws.send(json.dumps(buy_request))
        contract_id = None
        try:
            async with asyncio.timeout((random.randint(20, 10*MAX_TIMEOUT)) / 10):
                while True:
                    res = json.loads(await self.ws.recv())
                    msg_type = res.get("msg_type")
                    if msg_type == "buy":
                        if res.get("error"):
                            self.logger.error(f"Buy error: {res['error']['message']}")
                            break
                        contract_id = res["buy"]["contract_id"]
                    elif msg_type == "proposal_open_contract":
                        await self.adjust_stake(res, contract_id)
                        break
                    elif msg_type == "error":
                        self.logger.error(f"Trade error: {res['error']['message']}")
                        await self.update_balance()
                        break
        except asyncio.TimeoutError:
            if contract_id:
                await self.check_contract_status(contract_id)
            else:
                await self.update_balance()

    async def check_contract_status(self, contract_id):
        await self.ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": contract_id}))
        try:
            async with asyncio.timeout(2):
                res = json.loads(await self.ws.recv())
                if res.get("msg_type") == "proposal_open_contract":
                    await self.adjust_stake(res, contract_id)
                else:
                    self.logger.error(f"Contract status error for {contract_id}")
                    await self.update_balance()
        except (asyncio.TimeoutError, json.JSONDecodeError):
            self.logger.warning(f"Failed to check contract {contract_id}")
            await self.update_balance()

    async def adjust_stake(self, res, contract_id):
        profit = res["proposal_open_contract"].get("profit", 0)
        self.balance = res["proposal_open_contract"].get("current_balance", self.balance)
        if profit < 0:
            await self.update_balance()
            if self.stake <= self.balance:
                self.profit_on_win = self.outcome_on_win + self.base_profit_on_win
                self.stake = await self.round_to_2_dp(self.profit_on_win / self.profit_percentage)
                self.outcome_on_win = self.stake + self.profit_on_win
                if self.stake >= self.largest_stake:
                    self.min_account_balance += self.stake
                    self.largest_stake = self.stake
                    self.largest_stake_info = f"{datetime.now().strftime('%d-%m %H:%M')} barrier: {self.least_digit} Largest Stake:{self.stake}"
            else:
                self.stake = self.base_stake
        else:
            self.stake = self.base_stake
            self.outcome_on_win = self.stake + self.base_profit_on_win
        self.logger.info(f"Contract {contract_id} amt: {self.stake}, {self.largest_stake_info}")

    async def round_to_2_dp(self, value):
        value = math.ceil(value * 100) / 100  # Round up to 2 decimal places
        return round(value, 2)

    async def update_balance(self):
        await self.ws.send(json.dumps({"balance": 1}))
        try:
            res = json.loads(await self.ws.recv())
            if res.get("msg_type") == "balance":
                self.balance = res["balance"]["balance"]
            else:
                self.logger.error("Balance update failed")
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON in balance response")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.info("Starting new session")
    bot = DerivBot()
    await bot.connect_forever()

if __name__ == "__main__":
    asyncio.run(main())