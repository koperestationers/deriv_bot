"""
Deriv WebSocket API Client for Odd/Even Trading Bot
Handles authentication, balance fetching, tick streaming, and trade execution
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, Optional, Callable, Any
import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode


class DerivClient:
    """Secure WebSocket client for Deriv API with safety checks"""
    
    def __init__(self, app_id: str, api_token: str, environment: str = "demo"):
        self.app_id = app_id
        self.api_token = api_token
        self.environment = environment
        self.websocket = None
        self.is_connected = False
        self.is_authenticated = False
        self.account_info = None
        self.balance = 0.0
        self.logger = logging.getLogger(__name__)
        
        # Safety check - refuse non-demo environments
        if environment.lower() != "demo":
            raise ValueError("SAFETY: Only demo environment allowed")
        
        # WebSocket URL for demo environment
        self.ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={app_id}"
        
        # Request tracking
        self.request_id = 1
        self.pending_requests = {}
        self.tick_callbacks = []
        
    async def connect(self) -> bool:
        """Establish WebSocket connection with exponential backoff"""
        max_attempts = 5
        base_delay = 1.0
        
        for attempt in range(max_attempts):
            try:
                self.logger.info(f"Connecting to Deriv WebSocket (attempt {attempt + 1}/{max_attempts})")
                self.websocket = await websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10
                )
                self.is_connected = True
                self.logger.info("WebSocket connection established")
                
                # Start message handler
                asyncio.create_task(self._message_handler())
                return True
                
            except Exception as e:
                self.logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    
        self.logger.error("Failed to establish connection after all attempts")
        return False
    
    async def authenticate(self) -> bool:
        """Authenticate with Deriv API"""
        if not self.is_connected:
            raise RuntimeError("Must connect before authenticating")
        
        auth_request = {
            "authorize": self.api_token,
            "req_id": self._get_request_id()
        }
        
        response = await self._send_request(auth_request)
        
        if "error" in response:
            self.logger.error(f"Authentication failed: {response['error']}")
            return False
        
        self.account_info = response.get("authorize", {})
        
        # Check account type based on environment setting
        account_type = os.getenv("ACCOUNT_TYPE", "demo").lower()
        is_virtual = self.account_info.get("is_virtual", False)
        
        if account_type == "demo" and not is_virtual:
            self.logger.error("SAFETY BREACH: Expected demo account but got real account")
            await self.disconnect()
            raise RuntimeError("SAFETY: Demo account required but real account detected")
        elif account_type == "real" and is_virtual:
            self.logger.error("CONFIGURATION ERROR: Expected real account but got demo account")
            await self.disconnect()
            raise RuntimeError("CONFIG: Real account required but demo account detected")
        
        self.is_authenticated = True
        account_desc = "Demo" if is_virtual else "Real"
        self.logger.info(f"Authenticated successfully - {account_desc} Account: {self.account_info.get('loginid')}")
        
        return True
            
    async def get_balance(self) -> float:
        """Fetch current account balance"""
        if not self.is_authenticated:
            raise RuntimeError("Must authenticate before getting balance")
            
        balance_request = {
            "balance": 1,
            "req_id": self._get_request_id()
        }
        
        try:
            response = await self._send_request(balance_request)
            
            if "error" in response:
                self.logger.error(f"Balance fetch failed: {response['error']}")
                return self.balance
                
            balance_data = response.get("balance", {})
            self.balance = float(balance_data.get("balance", 0))
            
            # Use account info from authentication for virtual check
            account_type = os.getenv("ACCOUNT_TYPE", "demo").lower()
            if account_type == "demo" and not self.account_info.get("is_virtual", False):
                raise RuntimeError("SAFETY: Account is not virtual")
                
            self.logger.info(f"Current balance: ${self.balance:.2f}")
            return self.balance
            
        except Exception as e:
            self.logger.error(f"Balance fetch error: {e}")
            return self.balance
    
    async def get_payout_info(self, symbol: str = "R_50") -> Dict:
        """Get payout information for Odd/Even contracts"""
        proposal_request = {
            "proposal": 1,
            "amount": 1,  # Minimum stake for payout calculation
            "basis": "stake",
            "contract_type": "DIGITEVEN",
            "currency": "USD",
            "symbol": symbol,
            "duration": 1,
            "duration_unit": "t",
            "req_id": self._get_request_id()
        }
        
        try:
            response = await self._send_request(proposal_request)
            
            if "error" in response:
                self.logger.error(f"Payout info fetch failed: {response['error']}")
                return {}
                
            proposal = response.get("proposal", {})
            payout = float(proposal.get("payout", 0))
            ask_price = float(proposal.get("ask_price", 1))
            
            # Calculate payout ratio
            payout_ratio = payout / ask_price if ask_price > 0 else 0
            
            return {
                "payout_ratio": payout_ratio,
                "ask_price": ask_price,
                "payout": payout,
                "symbol": symbol
            }
            
        except Exception as e:
            self.logger.error(f"Payout info error: {e}")
            return {}
    
    async def subscribe_ticks(self, symbol: str = "R_50", callback: Optional[Callable] = None):
        """Subscribe to tick stream for specified symbol"""
        if callback:
            self.tick_callbacks.append(callback)
            
        tick_request = {
            "ticks": symbol,
            "subscribe": 1,
            "req_id": self._get_request_id()
        }
        
        try:
            await self._send_message(tick_request)
            self.logger.info(f"Subscribed to ticks for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Tick subscription error: {e}")
    
    async def place_odd_even_trade(self, side: str, stake: float, symbol: str = "R_50") -> Dict:
        """
        Place an Odd/Even trade
        
        Args:
            side: "ODD" or "EVEN"
            stake: Stake amount in USD
            symbol: Trading symbol (default R_50)
            
        Returns:
            Trade result dictionary
        """
        if not self.is_authenticated:
            raise RuntimeError("Must authenticate before trading")
            
        # Safety checks
        if self.environment.lower() != "demo":
            raise RuntimeError("SAFETY: Only demo trading allowed")
            
        if side not in ["ODD", "EVEN"]:
            raise ValueError("Side must be 'ODD' or 'EVEN'")
            
        if stake <= 0:
            raise ValueError("Stake must be positive")
            
        # Map side to contract type
        contract_type = "DIGITODD" if side == "ODD" else "DIGITEVEN"
        
        buy_request = {
            "buy": 1,
            "price": stake,
            "parameters": {
                "amount": stake,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": "USD",
                "symbol": symbol,
                "duration": 1,
                "duration_unit": "t"
            },
            "req_id": self._get_request_id()
        }
        
        try:
            response = await self._send_request(buy_request)
            
            if "error" in response:
                self.logger.error(f"Trade execution failed: {response['error']}")
                return {"success": False, "error": response["error"]}
                
            buy_data = response.get("buy", {})
            contract_id = buy_data.get("contract_id")
            
            self.logger.info(f"Trade placed: {side} ${stake:.2f} - Contract ID: {contract_id}")
            
            return {
                "success": True,
                "contract_id": contract_id,
                "side": side,
                "stake": stake,
                "symbol": symbol,
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"Trade execution error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_contract_result(self, contract_id: str) -> Dict:
        """Get the result of a completed contract"""
        proposal_request = {
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "req_id": self._get_request_id()
        }
        
        try:
            response = await self._send_request(proposal_request)
            
            if "error" in response:
                self.logger.error(f"Contract result fetch failed: {response['error']}")
                return {}
                
            contract = response.get("proposal_open_contract", {})
            
            return {
                "contract_id": contract_id,
                "is_sold": contract.get("is_sold", False),
                "profit": float(contract.get("profit", 0)),
                "payout": float(contract.get("payout", 0)),
                "entry_tick": contract.get("entry_tick"),
                "exit_tick": contract.get("exit_tick"),
                "status": contract.get("status", "open")
            }
            
        except Exception as e:
            self.logger.error(f"Contract result error: {e}")
            return {}
    
    async def disconnect(self):
        """Safely disconnect from WebSocket"""
        self.is_connected = False
        self.is_authenticated = False
        
        if self.websocket:
            try:
                await self.websocket.close()
                self.logger.info("WebSocket disconnected")
            except Exception as e:
                self.logger.error(f"Disconnect error: {e}")
    
    def _get_request_id(self) -> int:
        """Generate unique request ID"""
        req_id = self.request_id
        self.request_id += 1
        return req_id
    
    async def _send_message(self, message: Dict):
        """Send message to WebSocket"""
        if not self.websocket or not self.is_connected:
            raise RuntimeError("WebSocket not connected")
            
        try:
            await self.websocket.send(json.dumps(message))
        except ConnectionClosed:
            self.is_connected = False
            raise RuntimeError("WebSocket connection lost")
    
    async def _send_request(self, request: Dict, timeout: float = 10.0) -> Dict:
        """Send request and wait for response"""
        req_id = request["req_id"]
        
        # Store future for response
        future = asyncio.Future()
        self.pending_requests[req_id] = future
        
        try:
            await self._send_message(request)
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            self.logger.error(f"Request {req_id} timed out")
            self.pending_requests.pop(req_id, None)
            return {"error": {"message": "Request timeout"}}
            
        except Exception as e:
            self.logger.error(f"Request {req_id} failed: {e}")
            self.pending_requests.pop(req_id, None)
            return {"error": {"message": str(e)}}
    
    async def _message_handler(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON received: {e}")
                    
        except ConnectionClosed:
            self.logger.warning("WebSocket connection closed")
            self.is_connected = False
            
        except Exception as e:
            self.logger.error(f"Message handler error: {e}")
            self.is_connected = False
    
    async def _process_message(self, data: Dict):
        """Process incoming message and route to appropriate handler"""
        # Handle request responses
        req_id = data.get("req_id")
        if req_id and req_id in self.pending_requests:
            future = self.pending_requests.pop(req_id)
            if not future.done():
                future.set_result(data)
            return
        
        # Handle tick data
        if "tick" in data:
            await self._handle_tick(data["tick"])
        
        # Handle other message types as needed
        msg_type = data.get("msg_type")
        if msg_type:
            self.logger.debug(f"Received {msg_type} message")
    
    async def _handle_tick(self, tick_data: Dict):
        """Process incoming tick data"""
        try:
            tick = {
                "symbol": tick_data.get("symbol"),
                "quote": float(tick_data.get("quote", 0)),
                "epoch": int(tick_data.get("epoch", 0)),
                "timestamp": time.time()
            }
            
            # Extract last digit for odd/even analysis
            quote_str = str(tick["quote"])
            if "." in quote_str:
                last_digit = int(quote_str.split(".")[-1][-1])
                tick["last_digit"] = last_digit
                tick["is_odd"] = last_digit % 2 == 1
            
            # Call registered callbacks
            for callback in self.tick_callbacks:
                try:
                    await callback(tick)
                except Exception as e:
                    self.logger.error(f"Tick callback error: {e}")
                    
        except Exception as e:
            self.logger.error(f"Tick processing error: {e}")
    
    async def health_check(self) -> bool:
        """Check if connection and authentication are healthy"""
        if not self.is_connected or not self.websocket:
            return False
            
        try:
            # Simple ping request
            ping_request = {
                "ping": 1,
                "req_id": self._get_request_id()
            }
            
            response = await self._send_request(ping_request, timeout=5.0)
            return "pong" in response
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        await self.authenticate()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()


async def create_deriv_client() -> DerivClient:
    """Factory function to create authenticated Deriv client from environment"""
    app_id = os.getenv("DERIV_APP_ID")
    api_token = os.getenv("DERIV_API_TOKEN")
    environment = os.getenv("DERIV_ENV", "demo")
    
    if not app_id or not api_token:
        raise ValueError("DERIV_APP_ID and DERIV_API_TOKEN must be set")
    
    client = DerivClient(app_id, api_token, environment)
    return client
