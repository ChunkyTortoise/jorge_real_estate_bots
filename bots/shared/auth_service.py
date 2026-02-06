"""
Authentication and Authorization Service for Jorge Real Estate AI Dashboard.

Provides secure multi-user access control with role-based permissions.

Features:
- JWT-based authentication
- Role-based access control (Admin, Agent, Viewer)
- Session management
- User management
- Security validation
"""
import os
import secrets
import jwt
import hashlib
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

from sqlalchemy import select

from bots.shared.logger import get_logger
from bots.shared.cache_service import get_cache_service
from database.session import AsyncSessionFactory
from database.models import UserModel, SessionModel

logger = get_logger(__name__)


class UserRole(Enum):
    """User roles for access control."""
    ADMIN = "admin"          # Full system access
    AGENT = "agent"          # Agent dashboard access
    VIEWER = "viewer"        # Read-only access


@dataclass
class User:
    """User model."""
    user_id: str
    email: str
    name: str
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    password_hash: Optional[str] = None
    must_change_password: bool = False


@dataclass
class AuthToken:
    """Authentication token."""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


@dataclass
class Permission:
    """Permission model."""
    resource: str
    action: str
    allowed: bool


class AuthService:
    """
    Authentication and authorization service.
    
    Provides secure multi-user access with JWT tokens and role-based permissions.
    """

    def __init__(self):
        """Initialize authentication service."""
        self.cache_service = get_cache_service()
        self.secret_key = self._get_secret_key()
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
        
        # Initialize password context
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Initialize default admin user if needed
        # Note: This will be called asynchronously when first method is called
        
        logger.info("AuthService initialized")

    def _get_secret_key(self) -> str:
        """Get JWT secret key from environment or generate one."""
        secret = os.getenv("JWT_SECRET")
        if not secret:
            logger.warning("JWT_SECRET not set, using default (not for production!)")
            secret = "jorge_real_estate_ai_default_secret_change_in_production"
        return secret

    async def _initialize_default_users(self) -> None:
        """Initialize default admin user for first-time setup."""
        try:
            # Check if any users exist
            users = await self.list_users()
            if not users:
                # Generate a secure random password or use env var
                default_password = os.getenv("ADMIN_DEFAULT_PASSWORD") or secrets.token_urlsafe(16)
                admin_user = await self.create_user(
                    email="jorge@realestate.ai",
                    password=default_password,
                    name="Jorge (Admin)",
                    role=UserRole.ADMIN,
                    must_change_password=True
                )
                logger.info(f"Created default admin user: {admin_user.email}")
                if not os.getenv("ADMIN_DEFAULT_PASSWORD"):
                    logger.warning(f"Generated admin password (change on first login): {default_password}")
                
        except Exception as e:
            logger.exception(f"Error initializing default users: {e}")

    async def create_user(
        self, 
        email: str, 
        password: str, 
        name: str, 
        role: UserRole,
        must_change_password: bool = False
    ) -> User:
        """
        Create a new user.
        
        Args:
            email: User email (unique identifier)
            password: Plain text password (will be hashed)
            name: User display name
            role: User role for permissions
            
        Returns:
            Created user (without password hash)
        """
        try:
            # Check if user already exists
            existing_user = await self.get_user_by_email(email)
            if existing_user:
                raise ValueError(f"User with email {email} already exists")
            
            # Hash password
            password_hash = self._hash_password(password)
            
            # Create user
            user = User(
                user_id=f"user_{int(datetime.now().timestamp())}_{hash(email) % 10000}",
                email=email.lower().strip(),
                name=name.strip(),
                role=role,
                created_at=datetime.now(),
                password_hash=password_hash,
                must_change_password=must_change_password
            )
            
            # Store user (without password in cache key)
            await self._store_user(user)
            
            # Return user without password hash
            user_response = User(
                user_id=user.user_id,
                email=user.email,
                name=user.name,
                role=user.role,
                created_at=user.created_at,
                last_login=user.last_login,
                is_active=user.is_active,
                must_change_password=user.must_change_password
            )
            
            logger.info(f"Created user: {user.email} with role {user.role.value}")
            return user_response
            
        except Exception as e:
            logger.exception(f"Error creating user: {e}")
            raise

    async def authenticate(self, email: str, password: str) -> Optional[AuthToken]:
        """
        Authenticate user and return JWT tokens.
        
        Args:
            email: User email
            password: Plain text password
            
        Returns:
            JWT tokens if authentication successful, None otherwise
        """
        try:
            # Get user by email
            user = await self.get_user_by_email(email, include_password=True)
            if not user or not user.is_active:
                logger.warning(f"Authentication failed - user not found or inactive: {email}")
                return None
            
            # Verify password
            if not self._verify_password(password, user.password_hash):
                logger.warning(f"Authentication failed - invalid password: {email}")
                return None
            
            # Update last login
            user.last_login = datetime.now(timezone.utc)
            await self._store_user(user)
            
            # Generate tokens
            tokens = await self._generate_tokens(user)
            refresh_expires = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)
            await self._store_session(user.user_id, tokens.refresh_token, refresh_expires)
            
            logger.info(f"User authenticated successfully: {user.email}")
            return tokens
            
        except Exception as e:
            logger.exception(f"Error during authentication: {e}")
            return None

    async def validate_token(self, token: str) -> Optional[User]:
        """
        Validate JWT token and return user.
        
        Args:
            token: JWT access token
            
        Returns:
            User if token is valid, None otherwise
        """
        try:
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Extract user info
            user_id = payload.get("user_id")
            if not user_id:
                return None
            
            # Get user
            user = await self.get_user_by_id(user_id)
            if not user or not user.is_active:
                return None
            
            return user
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error validating token: {e}")
            return None

    async def check_permission(
        self, 
        user: User, 
        resource: str, 
        action: str
    ) -> bool:
        """
        Check if user has permission for resource/action.
        
        Args:
            user: User to check permissions for
            resource: Resource name (e.g., 'dashboard', 'leads', 'conversations')
            action: Action name (e.g., 'read', 'write', 'delete')
            
        Returns:
            True if user has permission, False otherwise
        """
        try:
            # Admin has all permissions
            if user.role == UserRole.ADMIN:
                return True
            
            # Define role-based permissions
            permissions = {
                UserRole.AGENT: {
                    'dashboard': ['read'],
                    'leads': ['read', 'write'],
                    'conversations': ['read', 'write'],
                    'commission': ['read'],
                    'performance': ['read'],
                    'settings': []  # No settings access
                },
                UserRole.VIEWER: {
                    'dashboard': ['read'],
                    'leads': ['read'],
                    'conversations': ['read'],
                    'commission': [],  # No commission access
                    'performance': ['read'],
                    'settings': []  # No settings access
                }
            }
            
            # Check permission
            role_permissions = permissions.get(user.role, {})
            resource_actions = role_permissions.get(resource, [])
            
            return action in resource_actions
            
        except Exception as e:
            logger.exception(f"Error checking permissions: {e}")
            return False

    async def refresh_token(self, refresh_token: str) -> Optional[AuthToken]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: JWT refresh token
            
        Returns:
            New tokens if refresh successful, None otherwise
        """
        try:
            # Decode refresh token
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if it's a refresh token
            if payload.get("token_type") != "refresh":
                return None

            # Validate session exists
            session_ok = await self._session_exists(refresh_token)
            if not session_ok:
                return None
            
            # Get user
            user_id = payload.get("user_id")
            user = await self.get_user_by_id(user_id)
            if not user or not user.is_active:
                return None
            
            # Generate new tokens
            tokens = await self._generate_tokens(user)
            refresh_expires = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)
            await self._store_session(user.user_id, tokens.refresh_token, refresh_expires)
            return tokens
            
        except jwt.ExpiredSignatureError:
            logger.warning("Refresh token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid refresh token: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error refreshing token: {e}")
            return None

    async def list_users(self) -> List[User]:
        """List all users (without password hashes)."""
        try:
            async with AsyncSessionFactory() as session:
                result = await session.execute(select(UserModel))
                models = result.scalars().all()
                users = [self._user_from_model(m) for m in models]

            user_ids = [u.user_id for u in users]
            await self.cache_service.set("auth:user_list", user_ids, ttl=3600 * 24)
            for user in users:
                await self._cache_user(user)

            return users
            
        except Exception as e:
            logger.exception(f"Error listing users: {e}")
            user_keys = await self.cache_service.get("auth:user_list") or []
            users = []
            for user_id in user_keys:
                user = await self.get_user_by_id(user_id)
                if user:
                    users.append(user)
            return users

    async def get_user_by_email(
        self, 
        email: str, 
        include_password: bool = False
    ) -> Optional[User]:
        """Get user by email."""
        try:
            async with AsyncSessionFactory() as session:
                stmt = select(UserModel).where(UserModel.email == email.lower())
                result = await session.execute(stmt)
                model = result.scalars().first()
                if not model:
                    return None
                user = self._user_from_model(model, include_password=include_password)
                await self._cache_user(user)
                return user
            
        except Exception as e:
            logger.exception(f"Error getting user by email: {e}")
            cache_key = f"auth:user:email:{email.lower()}"
            user_data = await self.cache_service.get(cache_key)
            if not user_data:
                return None
            user = User(**user_data)
            if not include_password:
                user.password_hash = None
            return user

    async def get_user_by_id(self, user_id: str, include_password: bool = False) -> Optional[User]:
        """Get user by ID."""
        try:
            async with AsyncSessionFactory() as session:
                model = await session.get(UserModel, user_id)
                if not model:
                    return None
                user = self._user_from_model(model, include_password=include_password)
                await self._cache_user(user)
                return user
            
        except Exception as e:
            logger.exception(f"Error getting user by ID: {e}")
            cache_key = f"auth:user:id:{user_id}"
            user_data = await self.cache_service.get(cache_key)
            if not user_data:
                return None
            user = User(**user_data)
            user.password_hash = None
            return user

    async def _store_user(self, user: User) -> None:
        """Store user in cache/database."""
        try:
            async with AsyncSessionFactory() as session:
                stmt = select(UserModel).where(UserModel.id == user.user_id)
                result = await session.execute(stmt)
                existing = result.scalars().first()
                if existing:
                    existing.email = user.email.lower()
                    existing.name = user.name
                    existing.role = user.role.value
                    existing.password_hash = user.password_hash or existing.password_hash
                    existing.is_active = user.is_active
                    existing.last_login = user.last_login
                    existing.must_change_password = user.must_change_password
                    if hasattr(existing, "updated_at"):
                        existing.updated_at = datetime.now(timezone.utc)
                else:
                    session.add(
                        UserModel(
                            id=user.user_id,
                            email=user.email.lower(),
                            name=user.name,
                            role=user.role.value,
                            password_hash=user.password_hash or "",
                            is_active=user.is_active,
                            must_change_password=user.must_change_password,
                            created_at=user.created_at,
                            last_login=user.last_login,
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                await session.commit()

            await self._cache_user(user)

            user_list = await self.cache_service.get("auth:user_list") or []
            if user.user_id not in user_list:
                user_list.append(user.user_id)
                await self.cache_service.set("auth:user_list", user_list, ttl=3600 * 24)
            
        except Exception as e:
            logger.exception(f"Error storing user: {e}")
            raise

    async def _cache_user(self, user: User) -> None:
        """Store user in cache only."""
        email_key = f"auth:user:email:{user.email.lower()}"
        await self.cache_service.set(
            email_key,
            asdict(user),
            ttl=3600 * 24
        )
        id_key = f"auth:user:id:{user.user_id}"
        user_data_no_password = asdict(user)
        user_data_no_password.pop('password_hash', None)
        await self.cache_service.set(
            id_key,
            user_data_no_password,
            ttl=3600 * 24
        )

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt via passlib."""
        # Truncate password to 72 bytes for bcrypt compatibility
        if len(password.encode('utf-8')) > 72:
            password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        return self.pwd_context.hash(password)

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return self.pwd_context.verify(password, password_hash)

    def _hash_token(self, token: str) -> str:
        """Hash refresh token for storage."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _user_from_model(self, model: UserModel, include_password: bool = False) -> User:
        """Convert ORM model to User dataclass."""
        user = User(
            user_id=model.id,
            email=model.email,
            name=model.name,
            role=UserRole(model.role),
            created_at=model.created_at,
            last_login=model.last_login,
            is_active=model.is_active,
            password_hash=model.password_hash if include_password else None,
            must_change_password=bool(model.must_change_password),
        )
        return user

    async def _store_session(self, user_id: str, refresh_token: str, expires_at: datetime) -> None:
        """Persist refresh token session."""
        token_hash = self._hash_token(refresh_token)
        async with AsyncSessionFactory() as session:
            session.add(
                SessionModel(
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                )
            )
            await session.commit()

    async def _session_exists(self, refresh_token: str) -> bool:
        """Check if refresh token session exists and is valid."""
        token_hash = self._hash_token(refresh_token)
        async with AsyncSessionFactory() as session:
            stmt = select(SessionModel).where(SessionModel.token_hash == token_hash)
            result = await session.execute(stmt)
            session_row = result.scalars().first()
            if not session_row:
                return False
            if session_row.expires_at < datetime.now(timezone.utc):
                await session.delete(session_row)
                await session.commit()
                return False
            return True

    async def change_password(self, user_id: str, new_password: str) -> bool:
        """Change a user's password and clear must_change_password flag."""
        try:
            new_hash = self._hash_password(new_password)
            async with AsyncSessionFactory() as session:
                stmt = select(UserModel).where(UserModel.id == user_id)
                result = await session.execute(stmt)
                model = result.scalars().first()
                if not model:
                    return False
                model.password_hash = new_hash
                model.must_change_password = False
                if hasattr(model, "updated_at"):
                    model.updated_at = datetime.now(timezone.utc)
                await session.commit()
            # Refresh cache
            user = await self.get_user_by_id(user_id, include_password=True)
            if user:
                await self._store_user(user)
            return True
        except Exception as e:
            logger.exception(f"Error changing password: {e}")
            return False

    async def _generate_tokens(self, user: User) -> AuthToken:
        """Generate JWT access and refresh tokens."""
        now = datetime.now(timezone.utc)
        
        # Access token payload
        access_payload = {
            "user_id": user.user_id,
            "email": user.email,
            "role": user.role.value,
            "token_type": "access",
            "exp": now + timedelta(minutes=self.access_token_expire_minutes),
            "iat": now
        }
        
        # Refresh token payload
        refresh_payload = {
            "user_id": user.user_id,
            "token_type": "refresh",
            "exp": now + timedelta(days=self.refresh_token_expire_days),
            "iat": now
        }
        
        # Generate tokens
        access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
        
        return AuthToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_expire_minutes * 60,
            token_type="Bearer"
        )


# Global service instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get global auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
