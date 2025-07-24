#!/usr/bin/env python3
"""
BPU Scraper - Python Version using Botasaurus
Migrated from TypeScript to leverage Botasaurus's advanced anti-detection capabilities
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from botasaurus.browser import browser, Driver
from botasaurus.request import request, Request
from botasaurus.soupify import soupify
from botasaurus import bt

# Load environment variables
load_dotenv()

# Configuration
BPU_USERNAME = os.getenv('BPU_USERNAME')
BPU_PASSWORD = os.getenv('BPU_PASSWORD')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
CAPTCHA_API_KEY = os.getenv('CAPTCHA_API_KEY')
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'true').lower() == 'true'
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

class BPUScraper:
    def __init__(self):
        self.supabase: Optional[Client] = None
        self.validate_config()
        self.init_supabase()
    
    def validate_config(self):
        """Validate required environment variables"""
        if not BPU_USERNAME or not BPU_PASSWORD:
            raise ValueError("BPU_USERNAME and BPU_PASSWORD must be set in .env file")
        
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
        
        if not CAPTCHA_API_KEY:
            print("⚠️  CAPTCHA_API_KEY not set - CAPTCHA solving will be disabled")
            print("   Get a 2captcha API key from https://2captcha.com if needed")
    
    def init_supabase(self):
        """Initialize Supabase client"""
        try:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            print("✅ Supabase client initialized")
        except Exception as e:
            print(f"❌ Failed to initialize Supabase: {e}")
            raise

    def handle_post_login_captcha(self, driver: Driver, max_retries: int = 3) -> bool:
        """
        Handle post-login CAPTCHA challenges
        Returns True if handled successfully, False otherwise
        """
        for attempt in range(max_retries):
            try:
                print(f"🔍 CAPTCHA Check Attempt {attempt + 1}/{max_retries}")
                print(f"Current URL: {driver.get_current_url()}")
                print(f"Page title: {driver.get_title()}")
                
                # Check for CAPTCHA-related content
                page_content = driver.get_page_source()
                
                # Look for common CAPTCHA indicators
                captcha_indicators = [
                    "Please provide a valid login captcha",
                    "LoginErrorMessage",
                    "captcha",
                    "recaptcha",
                    "hcaptcha"
                ]
                
                has_captcha = any(indicator.lower() in page_content.lower() 
                                for indicator in captcha_indicators)
                
                if not has_captcha:
                    print("✅ No CAPTCHA detected")
                    return True
                
                print("🤖 CAPTCHA detected, attempting to solve...")
                
                # Take screenshot for debugging
                screenshot_path = f"screenshots/captcha_attempt_{attempt + 1}_{int(time.time())}.png"
                driver.save_screenshot(screenshot_path)
                print(f"📸 Screenshot saved: {screenshot_path}")
                
                # Try to solve reCAPTCHA if present
                if driver.is_element_present('iframe[src*="recaptcha"]'):
                    print("🔄 Attempting to solve reCAPTCHA...")
                    try:
                        # Botasaurus has built-in CAPTCHA solving capabilities
                        driver.solve_recaptcha()
                        time.sleep(2)
                    except Exception as e:
                        print(f"❌ reCAPTCHA solving failed: {e}")
                
                # Check if CAPTCHA was solved
                time.sleep(3)
                new_content = driver.get_page_source()
                if not any(indicator.lower() in new_content.lower() 
                          for indicator in captcha_indicators):
                    print("✅ CAPTCHA solved successfully")
                    return True
                
                print(f"❌ CAPTCHA solving attempt {attempt + 1} failed")
                if attempt < max_retries - 1:
                    print("⏳ Waiting before retry...")
                    time.sleep(3 + (attempt * 2))  # Increasing delay
                
            except Exception as e:
                print(f"❌ Error in CAPTCHA handling attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
        
        print("❌ All CAPTCHA solving attempts failed")
        return False

    
    @browser(
        headless=HEADLESS_MODE,
        block_images=True,  # Reduce bandwidth and improve speed
        max_retry=MAX_RETRIES,
        reuse_driver=True
    )
    def scrape_bpu_data(self, driver: Driver) -> Dict[str, Any]:
        """
        Main scraping function using Botasaurus browser automation
        """
        data = {
            'include_usage_data': True,
            'include_billing_data': True,
            'include_payment_history': True,
            'include_meter_readings': True,
            'date_range_days': 30
        }
        try:
            print("🚀 Starting BPU scraper...")
            
            # Step 1: Establish realistic browsing pattern
            print("🌐 Establishing browsing history...")
            
            # Visit Google first to establish browsing history
            driver.google_get("https://www.google.com")
            driver.sleep(2)
            
            # Navigate to BPU main site
            driver.get("https://www.bpu.com")
            driver.sleep(3)
            
            # Step 2: Navigate to login page
            print("🔐 Navigating to login page...")
            driver.get("https://mymeter.bpu.com/Home/Login")
            
            # Wait for page to load
            driver.wait_for_element("#Username", timeout=30)
            
            # Step 3: Human-like login process
            print("👤 Performing human-like login...")
            
            # Clear and type username with human-like delays
            username_field = driver.get_element("#Username")
            username_field.clear()
            driver.type_human_like(username_field, BPU_USERNAME)
            
            # Clear and type password with human-like delays
            password_field = driver.get_element("#Password")
            password_field.clear()
            driver.type_human_like(password_field, BPU_PASSWORD)
            
            # Human-like pause before clicking login
            driver.sleep(2)
            
            # Click login button
            login_button = driver.get_element("input[type='submit'][value='Login']")
            driver.click_human_like(login_button)
            
            # Step 4: Wait for login response and handle potential CAPTCHA
            print("⏳ Waiting for login response...")
            driver.sleep(5)
            
            # Check for successful login or CAPTCHA challenge
            current_url = driver.get_current_url()
            
            if "Login" in current_url:
                # Still on login page, check for errors or CAPTCHA
                page_content = driver.get_page_source()
                
                if any(error in page_content.lower() for error in ["invalid", "error", "captcha"]):
                    print("🤖 Handling post-login CAPTCHA...")
                    if not self.handle_post_login_captcha(driver):
                        raise Exception("Failed to handle CAPTCHA challenge")
            
            # Step 5: Navigate to dashboard/property selection
            print("🏠 Accessing property selection...")
            
            # Wait for dashboard elements
            driver.wait_for_element("#choosePropertyBtn", timeout=30)
            
            # Click choose property button
            choose_property_btn = driver.get_element("#choosePropertyBtn")
            driver.click_human_like(choose_property_btn)
            
            driver.sleep(3)
            
            # Step 6: Extract utility data
            print("📊 Extracting utility data...")
            
            # Wait for data to load
            driver.wait_for_element(".usage-data, .billing-data, .account-info", timeout=30)
            
            # Extract account information
            account_info = self.extract_account_info(driver)
            
            # Extract usage data
            usage_data = self.extract_usage_data(driver)
            
            # Extract billing data
            billing_data = self.extract_billing_data(driver)
            
            # Combine all data
            scraped_data = {
                "timestamp": datetime.now().isoformat(),
                "account_info": account_info,
                "usage_data": usage_data,
                "billing_data": billing_data,
                "scrape_status": "success"
            }
            
            print("✅ Data extraction completed successfully")
            
            # Step 7: Save to Supabase
            if self.supabase:
                self.save_to_supabase(scraped_data)
            
            return scraped_data
            
        except Exception as e:
            print(f"❌ Scraping failed: {e}")
            
            # Take error screenshot
            error_screenshot = f"screenshots/error_{int(time.time())}.png"
            driver.save_screenshot(error_screenshot)
            print(f"📸 Error screenshot saved: {error_screenshot}")
            
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "scrape_status": "failed"
            }

    def extract_account_info(self, driver: Driver) -> Dict[str, Any]:
        """Extract account information from the page"""
        try:
            account_info = {}
            
            # Extract account number
            if driver.is_element_present(".account-number"):
                account_info["account_number"] = driver.get_text(".account-number")
            
            # Extract service address
            if driver.is_element_present(".service-address"):
                account_info["service_address"] = driver.get_text(".service-address")
            
            # Extract customer name
            if driver.is_element_present(".customer-name"):
                account_info["customer_name"] = driver.get_text(".customer-name")
            
            return account_info
            
        except Exception as e:
            print(f"⚠️  Error extracting account info: {e}")
            return {}

    def extract_usage_data(self, driver: Driver) -> List[Dict[str, Any]]:
        """Extract usage data from the page"""
        try:
            usage_data = []
            
            # Look for usage tables or data containers
            usage_elements = driver.get_elements(".usage-row, .usage-data, .meter-reading")
            
            for element in usage_elements:
                try:
                    usage_entry = {
                        "date": element.get_text(".date, .reading-date"),
                        "usage": element.get_text(".usage, .consumption"),
                        "cost": element.get_text(".cost, .amount")
                    }
                    usage_data.append(usage_entry)
                except:
                    continue
            
            return usage_data
            
        except Exception as e:
            print(f"⚠️  Error extracting usage data: {e}")
            return []

    def extract_billing_data(self, driver: Driver) -> List[Dict[str, Any]]:
        """Extract billing data from the page"""
        try:
            billing_data = []
            
            # Look for billing tables or data containers
            billing_elements = driver.get_elements(".bill-row, .billing-data, .invoice-item")
            
            for element in billing_elements:
                try:
                    billing_entry = {
                        "bill_date": element.get_text(".bill-date, .invoice-date"),
                        "due_date": element.get_text(".due-date"),
                        "amount": element.get_text(".amount, .total"),
                        "status": element.get_text(".status, .payment-status")
                    }
                    billing_data.append(billing_entry)
                except:
                    continue
            
            return billing_data
            
        except Exception as e:
            print(f"⚠️  Error extracting billing data: {e}")
            return []

    def save_to_supabase(self, data: Dict[str, Any]) -> bool:
        """Save scraped data to Supabase"""
        try:
            if not self.supabase:
                print("⚠️  Supabase client not initialized")
                return False
            
            # Insert data into the appropriate table
            result = self.supabase.table('bpu_scraper_data').insert(data).execute()
            
            if result.data:
                print("✅ Data saved to Supabase successfully")
                return True
            else:
                print("❌ Failed to save data to Supabase")
                return False
                
        except Exception as e:
            print(f"❌ Error saving to Supabase: {e}")
            return False

def main():
    """Main function to run the BPU scraper"""
    try:
        scraper = BPUScraper()
        
        # Use Botasaurus to run the scraper properly
        print("🚀 Starting BPU scraper...")
        results = scraper.scrape_bpu_data()
        
        # Results is a list, get the first result
        if results and len(results) > 0:
            result = results[0]
            
            # Save results locally as well
            output_file = f"output/bpu_scraper_results_{int(time.time())}.json"
            bt.write_json(result, output_file)
            print(f"📁 Results saved to: {output_file}")
            
            if result.get("scrape_status") == "success":
                print("🎉 BPU scraping completed successfully!")
            else:
                print("❌ BPU scraping failed. Check the logs and screenshots for details.")
        else:
            print("❌ No results returned from scraper")
            return 1
            
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
