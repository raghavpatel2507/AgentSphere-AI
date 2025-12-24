
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config.database import async_engine
from src.core.state.models import User
from src.core.auth.security import get_password_hash, verify_password
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """
    Service for handling user authentication and registration.
    """
    
    @staticmethod
    async def authenticate_user(email: str, password: str):
        """
        Authenticate a user by email and password.
        Returns the User object if successful, None otherwise.
        """
        async with AsyncSession(async_engine) as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            
            if not user:
                return None
                
            if not verify_password(password, user.password_hash):
                return None
                
            return user

    @staticmethod
    async def register_user(email: str, password: str, full_name: str = None):
        """
        Register a new user.
        """
        async with AsyncSession(async_engine) as session:
            # Check if user exists
            result = await session.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                raise ValueError("User with this email already exists.")
            
            # Create user
            hashed_pw = get_password_hash(password)
            new_user = User(
                email=email,
                password_hash=hashed_pw,
                full_name=full_name
            )
            
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            logger.info(f"Registered new user: {email}")
            return new_user
