from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer
import secrets
import hashlib
import hmac
from telegram_bot.core.config import settings
from telegram_bot.core.constants import CACHE_TIMEOUTS
import jwt
import pyotp
from fastapi.security import HTTPBearer
from telegram_bot.core.cache import cache_service 
from telegram_bot.core.cache import cache_service as cache


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")




security = HTTPBearer()

class SecurityManager:
    """Enhanced security manager"""
    
    def __init__(self):
        self.cache = cache_service
        self._rate_limits = {
            'default': (100, 60),  # 100 requests per minute
            'auth': (5, 60),       # 5 login attempts per minute
            'payment': (10, 60)    # 10 payment attempts per minute
        }
        
    async def rate_limit(
        self,
        key: str,
        limit_type: str = 'default'
    ) -> bool:
        """Check rate limit"""
        rate_key = f"rate_limit:{limit_type}:{key}"
        
        # Get current count
        count = await self.cache.get(rate_key) or 0
        limit, period = self._rate_limits.get(limit_type, (100, 60))
        
        if count >= limit:
            return False
            
        # Increment counter
        pipe = self.cache.redis.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, period)
        await pipe.execute()
        
        return True
        
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta if expires_delta
            else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        
        return jwt.encode(
            to_encode,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM
        )
        
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY.get_secret_value(),
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials"
            )
            
    def hash_password(self, password: str) -> str:
        """Hash password"""
        return bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt()
        ).decode()
        
    def verify_password(
        self,
        plain_password: str,
        hashed_password: str
    ) -> bool:
        """Verify password"""
        return bcrypt.checkpw(
            plain_password.encode(),
            hashed_password.encode()
        )
        
    async def generate_2fa_secret(self, user_id: int) -> str:
        """Generate 2FA secret"""
        secret = pyotp.random_base32()
        await self.cache.set(
            f"2fa_secret:{user_id}",
            secret,
            timeout=300  # 5 minutes
        )
        return secret
        
    def verify_2fa_code(
        self,
        secret: str,
        code: str
    ) -> bool:
        """Verify 2FA code"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
        
    async def block_ip(
        self,
        ip: str,
        duration: int = 3600
    ) -> None:
        """Block IP address"""
        await self.cache.set(
            f"blocked_ip:{ip}",
            datetime.utcnow().isoformat(),
            timeout=duration
        )
        
    async def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return await self.cache.exists(f"blocked_ip:{ip}")
        
    def validate_request_signature(
        self,
        signature: str,
        data: Dict[str, Any],
        secret: str
    ) -> bool:
        """Validate request signature"""
        import hmac
        import hashlib
        
        # Create signature
        message = '&'.join(f"{k}={v}" for k, v in sorted(data.items()))
        expected = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)

# Create global instance
security_manager = SecurityManager()

async def get_current_user(
    token: str = Security(security)
) -> Dict[str, Any]:
    """Get current user from token"""
    return security_manager.verify_token(token.credentials)

__all__ = [
    'security_manager',
    'get_current_user',
    'OAuth2PasswordBearer'
]

class RoleChecker:
    """Role-based access control checker"""
    
    def __init__(self, required_roles: List[str]):
        self.required_roles = required_roles
    
    async def __call__(self, user: Dict = Security(get_current_user)) -> bool:
        if not user.get('roles'):
            return False
        return any(role in user['roles'] for role in self.required_roles)

class PermissionChecker:
    """Permission-based access control checker"""
    
    def __init__(self, required_permission: str):
        self.required_permission = required_permission
    
    async def __call__(self, user: Dict = Security(get_current_user)) -> bool:
        if not user.get('permissions'):
            return False
        return self.required_permission in user['permissions']

class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_strong_password(length: int = 12) -> str:
        """Generate strong random password"""
        import string
        alphabet = string.ascii_letters + string.digits + string.punctuation
        while True:
            password = ''.join(secrets.choice(alphabet) for _ in range(length))
            if (any(c.islower() for c in password)
                    and any(c.isupper() for c in password)
                    and any(c.isdigit() for c in password)
                    and any(c in string.punctuation for c in password)):
                return password
    
    @staticmethod
    def hash_data(data: str) -> str:
        """Hash data using SHA-256"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def generate_random_token(length: int = 32) -> str:
        """Generate random secure token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def sanitize_input(value: str) -> str:
        """Sanitize input string"""
        import html
        return html.escape(value)

class AdminRequired:
    """Admin role requirement decorator"""
    
    def __init__(self):
        self.checker = RoleChecker(['ADMIN'])
    
    async def __call__(self, user: Dict = Security(get_current_user)) -> bool:
        return await self.checker(user)

class ModeratorRequired:
    """Moderator role requirement decorator"""
    
    def __init__(self):
        self.checker = RoleChecker(['ADMIN', 'MODERATOR'])
    
    async def __call__(self, user: Dict = Security(get_current_user)) -> bool:
        return await self.checker(user)

class RateLimiter:
    """Rate limiting helper"""
    
    def __init__(
        self,
        requests: int,
        window: int
    ):
        self.requests = requests
        self.window = window
    
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed"""
        current = await cache.get(f"rate_limit:{key}")
        if not current:
            await cache.set(f"rate_limit:{key}", 1, timeout=self.window)
            return True
        
        if int(current) >= self.requests:
            return False
            
        await cache.increment(f"rate_limit:{key}")
        return True

class IPBanManager:
    """IP ban management"""
    
    @staticmethod
    async def ban_ip(ip: str, reason: str, duration: int = 86400) -> None:
        """Ban IP address"""
        await cache.set(
            f"banned_ip:{ip}",
            {
                'reason': reason,
                'banned_at': datetime.utcnow().isoformat(),
                'duration': duration
            },
            timeout=duration
        )
    
    @staticmethod
    async def unban_ip(ip: str) -> None:
        """Unban IP address"""
        await cache.delete(f"banned_ip:{ip}")
    
    @staticmethod
    async def is_banned(ip: str) -> bool:
        """Check if IP is banned"""
        return await cache.exists(f"banned_ip:{ip}")
    
    @staticmethod
    async def get_ban_info(ip: str) -> Optional[Dict]:
        """Get IP ban information"""
        return await cache.get(f"banned_ip:{ip}")

class TwoFactorAuth:
    """Two-factor authentication helper"""
    
    @staticmethod
    async def generate_code(user_id: int) -> str:
        """Generate 2FA code"""
        code = ''.join(secrets.choice('0123456789') for _ in range(6))
        
        await cache.set(
            f"2fa_code:{user_id}",
            {
                'code': code,
                'attempts': 0,
                'generated_at': datetime.utcnow().isoformat()
            },
            timeout=300  # 5 minutes
        )
        
        return code
    
    @staticmethod
    async def verify_code(user_id: int, code: str) -> bool:
        """Verify 2FA code"""
        stored = await cache.get(f"2fa_code:{user_id}")
        if not stored:
            return False
            
        # Increment attempts
        stored['attempts'] += 1
        await cache.set(f"2fa_code:{user_id}", stored, timeout=300)
        
        # Check attempts
        if stored['attempts'] >= 3:
            await cache.delete(f"2fa_code:{user_id}")
            return False
            
        return stored['code'] == code

# Create utility instances
security_utils = SecurityUtils()
rate_limiter = RateLimiter(100, 60)  # 100 requests per minute
ip_ban_manager = IPBanManager()
two_factor_auth = TwoFactorAuth()

# Additional exports
__all__ += [
    'RoleChecker',
    'PermissionChecker',
    'SecurityUtils',
    'AdminRequired',
    'ModeratorRequired',
    'RateLimiter',
    'IPBanManager',
    'TwoFactorAuth',
    'security_utils',
    'rate_limiter',
    'ip_ban_manager',
    'two_factor_auth'
]