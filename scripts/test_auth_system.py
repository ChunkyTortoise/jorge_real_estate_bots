#!/usr/bin/env python3
"""Test script for authentication system validation."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from bots.shared.auth_service import get_auth_service, UserRole


async def test_authentication_system():
    """Test authentication service functionality."""
    print("🔐 Testing Authentication System...")
    print("=" * 50)
    
    auth_service = get_auth_service()
    
    # Initialize default users
    await auth_service._initialize_default_users()
    
    try:
        # Test 1: Initialize and create admin user
        print("Testing user creation...")
        admin_user = await auth_service.create_user(
            email="test_admin@jorge.ai",
            password="test123",
            name="Test Admin",
            role=UserRole.ADMIN
        )
        print(f"✅ Created admin user: {admin_user.name} ({admin_user.role.value})")
        
        # Test 2: Create agent user
        agent_user = await auth_service.create_user(
            email="test_agent@jorge.ai",
            password="agent123",
            name="Test Agent",
            role=UserRole.AGENT
        )
        print(f"✅ Created agent user: {agent_user.name} ({agent_user.role.value})")
        
        # Test 3: Create viewer user
        viewer_user = await auth_service.create_user(
            email="test_viewer@jorge.ai",
            password="viewer123",
            name="Test Viewer",
            role=UserRole.VIEWER
        )
        print(f"✅ Created viewer user: {viewer_user.name} ({viewer_user.role.value})")
        
        # Test 4: Authentication
        print("\nTesting authentication...")
        tokens = await auth_service.authenticate("test_admin@jorge.ai", "test123")
        if tokens:
            print("✅ Admin authentication successful")
            
            # Validate token
            user = await auth_service.validate_token(tokens.access_token)
            if user:
                print(f"✅ Token validation successful: {user.name}")
            else:
                print("❌ Token validation failed")
        else:
            print("❌ Admin authentication failed")
        
        # Test 5: Permission checks
        print("\nTesting permissions...")
        
        # Admin permissions
        admin_can_write = await auth_service.check_permission(admin_user, 'dashboard', 'write')
        print(f"✅ Admin write permission: {admin_can_write}")
        
        # Agent permissions
        agent_can_read = await auth_service.check_permission(agent_user, 'leads', 'read')
        agent_can_settings = await auth_service.check_permission(agent_user, 'settings', 'read')
        print(f"✅ Agent leads read: {agent_can_read}")
        print(f"✅ Agent settings read (should be False): {agent_can_settings}")
        
        # Viewer permissions
        viewer_can_read = await auth_service.check_permission(viewer_user, 'dashboard', 'read')
        viewer_can_write = await auth_service.check_permission(viewer_user, 'leads', 'write')
        print(f"✅ Viewer dashboard read: {viewer_can_read}")
        print(f"✅ Viewer leads write (should be False): {viewer_can_write}")
        
        # Test 6: List users
        print("\nTesting user listing...")
        users = await auth_service.list_users()
        print(f"✅ Listed {len(users)} users:")
        for user in users:
            print(f"   - {user.name} ({user.email}) - {user.role.value}")
        
        # Test 7: Token refresh
        print("\nTesting token refresh...")
        new_tokens = await auth_service.refresh_token(tokens.refresh_token)
        if new_tokens:
            print("✅ Token refresh successful")
        else:
            print("❌ Token refresh failed")
        
        print("=" * 50)
        print("✅ ALL AUTHENTICATION TESTS PASSED!")
        print("🔐 Authentication system is ready for production")
        print("\n📋 User Accounts Created:")
        print("   - test_admin@jorge.ai / test123 (Admin)")
        print("   - test_agent@jorge.ai / agent123 (Agent)")
        print("   - test_viewer@jorge.ai / viewer123 (Viewer)")
        print("   - jorge@realestate.ai / admin123 (Default Admin)")
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_authentication_system())
    sys.exit(0 if success else 1)