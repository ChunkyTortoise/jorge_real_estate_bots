"""
Authentication component for Streamlit dashboard.

Provides login/logout functionality and session management.
"""
import streamlit as st
import asyncio
from typing import Optional

from bots.shared.auth_service import get_auth_service, User, UserRole
from bots.shared.logger import get_logger

logger = get_logger(__name__)


def render_login_form() -> Optional[User]:
    """
    Render login form and handle authentication.
    
    Returns:
        Authenticated user if login successful, None otherwise
    """
    st.markdown("""
    <div style="max-width: 400px; margin: 0 auto; padding: 2rem; 
                background: white; border-radius: 10px; 
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
    """, unsafe_allow_html=True)
    
    st.markdown("### 🏠 Jorge's Real Estate AI")
    st.markdown("**Dashboard Login**")
    
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="jorge@realestate.ai")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            if not email or not password:
                st.error("Please enter both email and password")
                return None
            
            try:
                # Authenticate user
                auth_service = get_auth_service()
                tokens = asyncio.run(auth_service.authenticate(email, password))
                
                if tokens:
                    # Get user info
                    user = asyncio.run(auth_service.validate_token(tokens.access_token))
                    if user:
                        # Store in session
                        st.session_state.auth_token = tokens.access_token
                        st.session_state.refresh_token = tokens.refresh_token
                        st.session_state.user = {
                            'user_id': user.user_id,
                            'email': user.email,
                            'name': user.name,
                            'role': user.role.value
                        }
                        st.session_state.must_change_password = user.must_change_password
                        
                        st.success(f"Welcome, {user.name}!")
                        st.rerun()
                        return user
                
                st.error("Invalid email or password")
                return None
                
            except Exception as e:
                logger.exception(f"Login error: {e}")
                st.error("Login failed. Please try again.")
                return None
    
    # Default credentials hint
    st.markdown("---")
    st.info("""
    **Default Admin Credentials:**
    - Email: jorge@realestate.ai
    - Password: admin123
    
    *Change password after first login*
    """)
    
    st.markdown("</div>", unsafe_allow_html=True)
    return None


def check_authentication() -> Optional[User]:
    """
    Check if user is authenticated via session.
    
    Returns:
        Authenticated user if session is valid, None otherwise
    """
    if 'auth_token' not in st.session_state:
        return None
    
    try:
        auth_service = get_auth_service()
        user = asyncio.run(auth_service.validate_token(st.session_state.auth_token))
        
        if user:
            # Update session user info
            st.session_state.user = {
                'user_id': user.user_id,
                'email': user.email,
                'name': user.name,
                'role': user.role.value
            }
            st.session_state.must_change_password = user.must_change_password
            return user
        else:
            # Token expired or invalid, try refresh
            if 'refresh_token' in st.session_state:
                tokens = asyncio.run(auth_service.refresh_token(st.session_state.refresh_token))
                if tokens:
                    user = asyncio.run(auth_service.validate_token(tokens.access_token))
                    if user:
                        # Update session with new tokens
                        st.session_state.auth_token = tokens.access_token
                        st.session_state.refresh_token = tokens.refresh_token
                        st.session_state.user = {
                            'user_id': user.user_id,
                            'email': user.email,
                            'name': user.name,
                            'role': user.role.value
                        }
                        st.session_state.must_change_password = user.must_change_password
                        return user
            
            # Clear invalid session
            clear_session()
            return None
            
    except Exception as e:
        logger.exception(f"Authentication check error: {e}")
        clear_session()
        return None


def clear_session() -> None:
    """Clear authentication session."""
    keys_to_remove = ['auth_token', 'refresh_token', 'user', 'must_change_password']
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]


def render_password_change_form(user: User) -> bool:
    """Render password change form for first-login enforcement."""
    st.warning("Password change required before continuing.")
    with st.form("change_password_form"):
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Change Password", use_container_width=True)

        if submit:
            if not new_password or len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
                return False
            if new_password != confirm_password:
                st.error("Passwords do not match.")
                return False
            auth_service = get_auth_service()
            success = asyncio.run(auth_service.change_password(user.user_id, new_password))
            if success:
                st.session_state.must_change_password = False
                st.success("Password updated. Please continue.")
                st.rerun()
                return True
            st.error("Failed to update password.")
            return False
    return False


def render_user_menu(user: User) -> None:
    """
    Render user menu in sidebar.
    
    Args:
        user: Authenticated user
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 User")
    
    # User info
    role_emoji = {
        'admin': '👑',
        'agent': '🏡', 
        'viewer': '👁️'
    }
    
    emoji = role_emoji.get(user.role.value, '👤')
    st.sidebar.markdown(f"**{emoji} {user.name}**")
    st.sidebar.markdown(f"*{user.role.value.title()}*")
    
    # Logout button
    if st.sidebar.button("Logout", use_container_width=True):
        clear_session()
        st.rerun()


def check_permission(user: User, resource: str, action: str) -> bool:
    """
    Check if user has permission for resource/action.
    
    Args:
        user: User to check
        resource: Resource name
        action: Action name
        
    Returns:
        True if user has permission, False otherwise
    """
    try:
        auth_service = get_auth_service()
        return asyncio.run(auth_service.check_permission(user, resource, action))
    except Exception as e:
        logger.exception(f"Permission check error: {e}")
        return False


def require_permission(user: User, resource: str, action: str) -> bool:
    """
    Require permission and show error if not authorized.
    
    Args:
        user: User to check
        resource: Resource name
        action: Action name
        
    Returns:
        True if user has permission, False otherwise (also shows error)
    """
    has_permission = check_permission(user, resource, action)
    
    if not has_permission:
        st.error(f"🚫 Access Denied: You need {action} permission for {resource}")
        st.info("Contact your administrator to request access.")
        return False
    
    return True


def render_role_badge(user: User) -> None:
    """Render role badge for user."""
    role_colors = {
        'admin': '#dc3545',    # Red
        'agent': '#28a745',    # Green
        'viewer': '#6c757d'    # Gray
    }
    
    role_labels = {
        'admin': '👑 Admin',
        'agent': '🏡 Agent', 
        'viewer': '👁️ Viewer'
    }
    
    color = role_colors.get(user.role.value, '#6c757d')
    label = role_labels.get(user.role.value, user.role.value.title())
    
    st.markdown(f"""
    <span style="
        background-color: {color};
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: bold;
    ">{label}</span>
    """, unsafe_allow_html=True)


def create_user_management_interface() -> None:
    """Create user management interface for admins."""
    st.markdown("### 👥 User Management")
    
    # List existing users
    try:
        auth_service = get_auth_service()
        users = asyncio.run(auth_service.list_users())
        
        if users:
            st.markdown("#### Existing Users")
            for user in users:
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.write(f"**{user.name}**")
                    st.write(f"📧 {user.email}")
                with col2:
                    render_role_badge(user)
                with col3:
                    status = "✅ Active" if user.is_active else "❌ Inactive"
                    st.write(status)
                st.markdown("---")
        
        # Create new user form
        st.markdown("#### Add New User")
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_email = st.text_input("Email")
                new_name = st.text_input("Name")
            with col2:
                new_role = st.selectbox(
                    "Role", 
                    options=['agent', 'viewer', 'admin'],
                    format_func=lambda x: {'agent': '🏡 Agent', 'viewer': '👁️ Viewer', 'admin': '👑 Admin'}[x]
                )
                new_password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Create User"):
                if new_email and new_name and new_password:
                    try:
                        role = UserRole(new_role)
                        user = asyncio.run(auth_service.create_user(
                            email=new_email,
                            password=new_password,
                            name=new_name,
                            role=role
                        ))
                        st.success(f"User {user.name} created successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating user: {str(e)}")
                else:
                    st.error("Please fill in all fields")
    
    except Exception as e:
        st.error(f"Error loading user management: {str(e)}")
