#!/usr/bin/env python3
"""
Test script to validate BPU scraper setup and dependencies
"""

import sys
import os
from pathlib import Path

def test_python_version():
    """Test Python version compatibility"""
    print("🐍 Testing Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Requires Python 3.8+")
        return False

def test_dependencies():
    """Test required dependencies"""
    print("\n📦 Testing dependencies...")
    dependencies = [
        'botasaurus',
        'supabase',
        'dotenv'
    ]
    
    missing = []
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"✅ {dep} - Installed")
        except ImportError:
            print(f"❌ {dep} - Missing")
            missing.append(dep)
    
    return len(missing) == 0

def test_environment_file():
    """Test environment file setup"""
    print("\n🔧 Testing environment configuration...")
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if env_example.exists():
        print("✅ .env.example - Found")
    else:
        print("❌ .env.example - Missing")
        return False
    
    if env_file.exists():
        print("✅ .env - Found")
        # Test if required variables are set
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = ['BPU_USERNAME', 'BPU_PASSWORD']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
            print("   Please configure these in your .env file")
        else:
            print("✅ Required environment variables - Configured")
        
        return True
    else:
        print("⚠️  .env - Not found (copy from .env.example and configure)")
        return False

def test_directory_structure():
    """Test required directory structure"""
    print("\n📁 Testing directory structure...")
    required_dirs = [
        'output',
        'screenshots',
        'backend/inputs'
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"✅ {dir_path}/ - Exists")
        else:
            print(f"⚠️  {dir_path}/ - Missing (will be created automatically)")
            # Create the directory
            path.mkdir(parents=True, exist_ok=True)
            print(f"✅ {dir_path}/ - Created")
    
    return all_exist

def test_botasaurus_import():
    """Test Botasaurus specific imports"""
    print("\n🤖 Testing Botasaurus imports...")
    try:
        from botasaurus.browser import browser, Driver
        from botasaurus import bt
        print("✅ Botasaurus browser - Imported successfully")
        
        try:
            from botasaurus_server.server import Server
            print("✅ Botasaurus server - Imported successfully")
        except ImportError:
            print("⚠️  Botasaurus server - Not available (UI features disabled)")
        
        return True
    except ImportError as e:
        print(f"❌ Botasaurus import failed: {e}")
        return False

def test_supabase_import():
    """Test Supabase imports"""
    print("\n🗄️  Testing Supabase imports...")
    try:
        from supabase import create_client, Client
        print("✅ Supabase client - Imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Supabase import failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 BPU Scraper Setup Validation")
    print("=" * 40)
    
    tests = [
        test_python_version,
        test_dependencies,
        test_environment_file,
        test_directory_structure,
        test_botasaurus_import,
        test_supabase_import
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 40)
    print("📊 Test Summary:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All tests passed ({passed}/{total})")
        print("\n🚀 Your BPU scraper is ready to use!")
        print("\nNext steps:")
        print("1. Configure your .env file with BPU credentials")
        print("2. Run: python main.py (for CLI)")
        print("3. Run: python ui_scraper.py (for web UI)")
    else:
        print(f"⚠️  {passed}/{total} tests passed")
        print("\n🔧 Please fix the issues above before running the scraper")
        
        if passed >= total - 1:
            print("\n💡 Most tests passed - you can likely proceed with minor fixes")

if __name__ == "__main__":
    main()
