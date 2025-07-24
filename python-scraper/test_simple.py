#!/usr/bin/env python3
"""
Very simple test to verify Botasaurus is working
"""

from botasaurus.browser import browser, Driver
import time

@browser(
    headless=False,  # Keep visible for debugging
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
)
def test_basic_browsing(driver: Driver, data):
    """Simple test function"""
    
    print("🚀 Testing basic Botasaurus functionality...")
    
    try:
        # Go to Google
        print("📍 Going to Google...")
        driver.get("https://www.google.com")
        time.sleep(2)
        
        # Get current URL
        current_url = driver.current_url
        print(f"✅ Current URL: {current_url}")
        
        # Take a screenshot
        driver.save_screenshot("screenshots/test_google.png")
        print("📸 Screenshot saved")
        
        # Try to find the search box
        if driver.is_element_present('input[name="q"]'):
            print("✅ Found Google search box")
            driver.type('input[name="q"]', "Hello Botasaurus")
            time.sleep(1)
        else:
            print("❌ Could not find search box")
        
        return {
            "status": "success",
            "url": current_url,
            "message": "Basic test completed"
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    print("🧪 Running basic Botasaurus test...")
    
    # Create screenshots directory
    import os
    os.makedirs("screenshots", exist_ok=True)
    
    # Run the test
    results = test_basic_browsing([{}])
    
    if results:
        result = results[0]
        print(f"📊 Result: {result}")
        
        if result.get("status") == "success":
            print("🎉 Basic test passed!")
        else:
            print("❌ Basic test failed")
    else:
        print("❌ No results returned")
