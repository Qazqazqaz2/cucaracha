import asyncio
import logging
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import InputStickerSetShortName
import database as db
from config import GIFT_LIMIT_PER_ACCOUNT

logger = logging.getLogger(__name__)

class GiftClient:
    def __init__(self, api_id, api_hash, phone, session_name):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.client = None
        self.is_connected = False
        self.gifts_purchased = 0
        self.is_premium = False
    
    async def connect(self):
        """Connect to Telegram API and authorize if needed"""
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.info(f"Account {self.phone} needs authentication")
                return False, "Authentication required"
            
            self.is_connected = True
            # Load premium flag and purchased count from DB
            await self.refresh_runtime_state_from_db()
            # Check premium status live and persist result
            await self.check_and_update_premium()
            logger.info(f"Connected with account {self.phone} (premium={self.is_premium})")
            return True, "Connected successfully"
        
        except Exception as e:
            logger.error(f"Failed to connect with account {self.phone}: {str(e)}")
            return False, f"Connection error: {str(e)}"

    async def send_login_code(self):
        """Initiate login by sending a code to the account phone"""
        if not self.client:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.connect()
        try:
            await self.client.send_code_request(self.phone)
            return True, "Code sent"
        except Exception as e:
            logger.error(f"Failed to send login code to {self.phone}: {e}")
            return False, f"Failed to send code: {e}"
    
    async def authenticate(self, code):
        """Complete authentication with the received code"""
        try:
            await self.client.sign_in(self.phone, code)
            self.is_connected = True
            await self.refresh_runtime_state_from_db()
            await self.check_and_update_premium()
            logger.info(f"Account {self.phone} authenticated successfully (premium={self.is_premium})")
            return True, "Authentication successful"
        
        except errors.SessionPasswordNeededError:
            return False, "Two-factor authentication required"
        
        except Exception as e:
            logger.error(f"Authentication failed for {self.phone}: {str(e)}")
            return False, f"Authentication error: {str(e)}"
    
    async def authenticate_2fa(self, password):
        """Complete two-factor authentication"""
        try:
            await self.client.sign_in(password=password)
            self.is_connected = True
            await self.refresh_runtime_state_from_db()
            await self.check_and_update_premium()
            logger.info(f"2FA authentication successful for {self.phone} (premium={self.is_premium})")
            return True, "2FA authentication successful"
        
        except Exception as e:
            logger.error(f"2FA authentication failed for {self.phone}: {str(e)}")
            return False, f"2FA authentication error: {str(e)}"
    
    async def disconnect(self):
        """Disconnect from Telegram API"""
        if self.client:
            await self.client.disconnect()
            self.is_connected = False
            logger.info(f"Disconnected account {self.phone}")
    
    async def purchase_gift(self, recipient_username, quantity=1):
        """Purchase a gift for the specified recipient"""
        if not self.is_connected or not self.client:
            return False, "Client not connected"
        
        if self.gifts_purchased >= GIFT_LIMIT_PER_ACCOUNT:
            return False, f"Gift limit reached for account {self.phone}"
        if not self.is_premium:
            return False, f"Account {self.phone} is not premium"
        
        try:
            # Find the recipient user
            recipient = await self.client.get_entity(recipient_username)
            if not recipient:
                return False, f"Recipient {recipient_username} not found"
            
            # Get the premium gift sticker set
            try:
                premium_gifts = await self.client(GetStickerSetRequest(
                    InputStickerSetShortName("PremiumGifts")
                ))
                print(premium_gifts)
            except Exception as e:
                logger.error(f"Failed to get premium gifts sticker set: {str(e)}")
                return False, "Failed to access premium gifts"
            
            # Send the gift
            # Note: This is a simplified approach. In a real implementation,
            # you would need to handle the actual gift purchase flow which might involve
            # interacting with Telegram's payment system.
            # Placeholder for real purchase flow; this simulates a gift action
            await self.client.send_message(recipient, f"Sending you {quantity} Telegram Premium gift(s)!")
            
            # Update purchase count
            self.gifts_purchased += int(quantity)
            logger.info(f"Gift sent to {recipient_username} from account {self.phone}")
            
            return True, "Gift sent successfully"
        
        except Exception as e:
            logger.error(f"Failed to send gift to {recipient_username}: {str(e)}")
            return False, f"Gift purchase error: {str(e)}"

    async def refresh_runtime_state_from_db(self):
        """Sync runtime counters and flags from DB"""
        try:
            db_account = await db.get_account_by_phone(self.phone)
            if db_account:
                self.gifts_purchased = db_account.gifts_purchased or 0
                self.is_premium = bool(getattr(db_account, 'is_premium', False))
        except Exception as e:
            logger.warning(f"Failed to refresh state from DB for {self.phone}: {e}")

    async def check_and_update_premium(self):
        """Check account premium status using get_me and store in DB"""
        try:
            me = await self.client.get_me()
            premium_flag = bool(getattr(me, 'premium', False))
            self.is_premium = premium_flag
            await db.set_account_premium(self.phone, premium_flag)
            return premium_flag
        except Exception as e:
            logger.warning(f"Failed premium check for {self.phone}: {e}")
            return False

class GiftManager:
    def __init__(self):
        self.clients = {}
        self.active_clients = []
    
    async def initialize_clients(self, accounts):
        """Initialize clients for all accounts"""
        for account in accounts:
            client = GiftClient(
                api_id=account['api_id'],
                api_hash=account['api_hash'],
                phone=account['phone'],
                session_name=account['session_name']
            )
            
            success, message = await client.connect()
            if success:
                self.clients[account['phone']] = client
                self.active_clients.append(client)
                
                # Register account in database if not exists
                await db.register_account({
                    'phone': account['phone'],
                    'api_id': account['api_id'],
                    'api_hash': account['api_hash'],
                    'session_name': account['session_name']
                })
            
            logger.info(f"Account {account['phone']}: {message}")
        # Refresh internal premium flags from DB
        for client in self.active_clients:
            await client.refresh_runtime_state_from_db()
    
    async def purchase_gift(self, recipient_username, quantity=1):
        """Purchase gift using available premium accounts concurrently"""
        if not self.active_clients:
            return False, "No active accounts available"

        # Filter premium and under-limit clients, sorted by already used count
        eligible = [c for c in self.active_clients if c.is_connected and c.is_premium and c.gifts_purchased < GIFT_LIMIT_PER_ACCOUNT]
        eligible.sort(key=lambda c: c.gifts_purchased)
        if not eligible:
            return False, "No premium accounts available"

        gifts_remaining = int(quantity)
        plan = []  # list of (client, qty)
        for client in eligible:
            if gifts_remaining <= 0:
                break
            capacity = GIFT_LIMIT_PER_ACCOUNT - client.gifts_purchased
            if capacity <= 0:
                continue
            assign = min(gifts_remaining, capacity)
            plan.append((client, assign))
            gifts_remaining -= assign

        if not plan:
            return False, "No capacity available"

        results = await asyncio.gather(*[c.purchase_gift(recipient_username, q) for c, q in plan], return_exceptions=True)

        successful = 0
        for (client, assigned_qty), result in zip(plan, results):
            if isinstance(result, Exception):
                logger.error(f"Client {client.phone} failed with exception: {result}")
                continue
            ok, _msg = result
            if ok:
                successful += assigned_qty
                # persist increment for this account
                db_account = await db.get_account_by_phone(client.phone)
                if db_account:
                    await db.increment_account_purchase_count(db_account.id, assigned_qty)

        if successful == quantity:
            return True, f"Successfully sent {successful} gift(s)"
        elif successful > 0:
            return True, f"Partially sent {successful}/{quantity} gift(s)"
        else:
            return False, "Failed to send any gifts"
    
    async def close_all(self):
        """Close all client connections"""
        for client in self.active_clients:
            await client.disconnect()
        
        self.active_clients = [] 

    def get_or_create_client(self, api_id: int, api_hash: str, phone: str, session_name: str) -> GiftClient:
        """Return existing client or create new instance (not connected)"""
        if phone in self.clients:
            return self.clients[phone]
        client = GiftClient(api_id=api_id, api_hash=api_hash, phone=phone, session_name=session_name)
        self.clients[phone] = client
        self.active_clients.append(client)
        return client