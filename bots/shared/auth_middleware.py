"""
Authentication middleware for FastAPI applications.

Provides JWT-based authentication for API endpoints and dashboard access.
"""
from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bots.shared.auth_service import User, UserRole, get_auth_service
from bots.shared.config import settings
from bots.shared.logger import get_logger

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer()


class AuthMiddleware:
    """Authentication middleware for FastAPI."""

    def __init__(self):
        """Initialize auth middleware."""
        self.auth_service = get_auth_service()

    async def get_current_user(
        self, 
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> User:
        """
        Get current authenticated user from JWT token.
        
        Args:
            credentials: HTTP Bearer credentials
            
        Returns:
            Authenticated user
            
        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Extract token
            token = credentials.credentials
            
            # Validate token and get user
            user = await self.auth_service.validate_token(token)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Rate limiting per user
            await self._enforce_rate_limit(user.user_id)
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error getting current user: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication error",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def get_current_active_user(
        self, 
        current_user: User = Depends(get_current_user)
    ) -> User:
        """
        Get current active user (must be active).
        
        Args:
            current_user: Current user from token
            
        Returns:
            Active user
            
        Raises:
            HTTPException: If user is inactive
        """
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        return current_user

    async def _enforce_rate_limit(self, user_id: str) -> None:
        """Enforce per-user rate limits using Redis counters."""
        per_minute = settings.rate_limit_per_minute
        per_hour = settings.rate_limit_per_hour
        if not per_minute and not per_hour:
            return

        cache = self.auth_service.cache_service
        if per_minute:
            minute_key = f"rate:{user_id}:m"
            count_min = await cache.increment(minute_key, 1, ttl=60)
            if count_min > per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded (per minute)",
                )

        if per_hour:
            hour_key = f"rate:{user_id}:h"
            count_hr = await cache.increment(hour_key, 1, ttl=3600)
            if count_hr > per_hour:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded (per hour)",
                )

    async def get_admin_user(
        self, 
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        """
        Get current admin user (must be admin role).
        
        Args:
            current_user: Current active user
            
        Returns:
            Admin user
            
        Raises:
            HTTPException: If user is not admin
        """
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user

    async def check_permission(
        self, 
        resource: str, 
        action: str,
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        """
        Check user permission for resource/action.
        
        Args:
            resource: Resource name
            action: Action name
            current_user: Current active user
            
        Returns:
            User if permission granted
            
        Raises:
            HTTPException: If permission denied
        """
        has_permission = await self.auth_service.check_permission(
            current_user, resource, action
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied for {action} on {resource}"
            )
        
        return current_user

    def require_permission(self, resource: str, action: str):
        """
        Decorator to require specific permission for endpoint.
        
        Args:
            resource: Resource name
            action: Action name
            
        Returns:
            FastAPI dependency
        """
        async def permission_checker(
            current_user: User = Depends(self.get_current_active_user)
        ) -> User:
            return await self.check_permission(resource, action, current_user)
        
        return permission_checker


# Global middleware instance
auth_middleware = AuthMiddleware()


def get_current_user() -> Callable:
    """Get current user dependency."""
    return auth_middleware.get_current_user


def get_current_active_user() -> Callable:
    """Get current active user dependency."""
    return auth_middleware.get_current_active_user


def get_admin_user() -> Callable:
    """Get admin user dependency."""
    return auth_middleware.get_admin_user


def require_permission(resource: str, action: str) -> Callable:
    """
    Require permission for endpoint.
    
    Args:
        resource: Resource name (e.g., 'dashboard', 'leads')
        action: Action name (e.g., 'read', 'write')
        
    Returns:
        FastAPI dependency
    """
    return auth_middleware.require_permission(resource, action)


# Streamlit authentication helpers
class StreamlitAuth:
    """Authentication helpers for Streamlit dashboard."""

    def __init__(self):
        """Initialize Streamlit auth."""
        self.auth_service = get_auth_service()

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user for Streamlit session."""
        tokens = await self.auth_service.authenticate(email, password)
        if tokens:
            user = await self.auth_service.validate_token(tokens.access_token)
            return user
        return None

    async def get_user_from_token(self, token: str) -> Optional[User]:
        """Get user from JWT token."""
        return await self.auth_service.validate_token(token)

    def check_streamlit_permission(
        self, 
        user: User, 
        resource: str, 
        action: str
    ) -> bool:
        """Check permission for Streamlit interface."""
        import asyncio
        return asyncio.run(
            self.auth_service.check_permission(user, resource, action)
        )
