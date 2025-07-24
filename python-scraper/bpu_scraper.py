#!/usr/bin/env python3
"""
Enhanced BPU Scraper with Botasaurus advanced features
Includes human-like interactions, CAPTCHA handling, and robust error recovery
"""

import os
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from botasaurus.browser import browser, Driver
from botasaurus import bt

# Load environment variables
load_dotenv()

# Configuration
BPU_USERNAME = os.getenv('BPU_USERNAME')
BPU_PASSWORD = os.getenv('BPU_PASSWORD')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
CAPTCHA_API_KEY = os.getenv('CAPTCHA_API_KEY')
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'true').lower() == 'true'

class BPUScraperAdvanced:
    def __init__(self):
        self.supabase: Optional[Client] = None
        self.init_supabase()
    
    def init_supabase(self):
        """Initialize Supabase client"""
        if SUPABASE_URL and SUPABASE_SERVICE_KEY:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
                print("✅ Supabase client initialized")
            except Exception as e:
                print(f"❌ Failed to initialize Supabase: {e}")

    def human_like_typing(self, driver: Driver, element, text: str):
        """Type text with human-like delays and occasional pauses"""
        element.clear()
        
        for i, char in enumerate(text):
            element.send_keys(char)
            
            # Variable typing speed (80-200ms per character)
            delay = random.uniform(0.08, 0.2)
            
            # Occasional thinking pauses (10% chance)
            if random.random() < 0.1:
                delay += random.uniform(0.3, 0.7)
            
            time.sleep(delay)

    def human_like_mouse_movement(self, driver: Driver, element):
        """Simulate human-like mouse movement to element"""
        try:
            # Get element location and size
            location = element.location
            size = element.size
            
            # Calculate random point within element bounds
            x = location['x'] + random.randint(5, size['width'] - 5)
            y = location['y'] + random.randint(5, size['height'] - 5)
            
            # Move mouse to element (Botasaurus handles this automatically)
            driver.execute_script(f"""
                var element = arguments[0];
                var event = new MouseEvent('mouseover', {{
                    'view': window,
                    'bubbles': true,
                    'cancelable': true,
                    'clientX': {x},
                    'clientY': {y}
                }});
                element.dispatchEvent(event);
            """, element)
            
            # Small delay for hover effect
            time.sleep(random.uniform(0.1, 0.3))
            
        except Exception as e:
            print(f"⚠️  Mouse movement simulation failed: {e}")

    def simulate_realistic_browsing(self, driver: Driver):
        """Simulate realistic browsing pattern before login"""
        print("🌐 Simulating realistic browsing pattern...")
        
        # Step 1: Visit Google with realistic interaction
        driver.get("https://www.google.com")
        time.sleep(random.uniform(2, 4))
        
        # Simulate some scrolling
        driver.execute_script("window.scrollTo(0, 200);")
        time.sleep(random.uniform(1, 2))
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(random.uniform(1, 2))
        
        # Step 2: Navigate to BPU main site
        driver.get("https://www.bpu.com")
        time.sleep(random.uniform(3, 5))
        
        # Simulate reading the page
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(random.uniform(2, 3))
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(random.uniform(1, 2))

    def handle_captcha_challenge(self, driver: Driver) -> bool:
        """Handle various types of CAPTCHA challenges"""
        print("🤖 Detecting and handling CAPTCHA challenges...")
        
        try:
            # Check for reCAPTCHA
            if driver.is_element_present('iframe[src*="recaptcha"]'):
                print("🔄 reCAPTCHA detected, attempting to solve...")
                
                if CAPTCHA_API_KEY:
                    try:
                        # Botasaurus can integrate with CAPTCHA solving services
                        driver.execute_script("""
                            // Wait for reCAPTCHA to be ready
                            setTimeout(function() {
                                var recaptcha = document.querySelector('.g-recaptcha');
                                if (recaptcha) {
                                    recaptcha.click();
                                }
                            }, 1000);
                        """)
                        
                        # Wait for CAPTCHA to be solved
                        time.sleep(10)
                        
                        # Check if solved
                        if driver.execute_script("return grecaptcha.getResponse() !== ''"):
                            print("✅ reCAPTCHA solved successfully")
                            return True
                        
                    except Exception as e:
                        print(f"❌ reCAPTCHA solving failed: {e}")
                
                else:
                    print("⚠️  CAPTCHA_API_KEY not set, manual intervention may be required")
                    if not HEADLESS_MODE:
                        input("Please solve the CAPTCHA manually and press Enter to continue...")
                        return True
            
            # Check for hCaptcha
            elif driver.is_element_present('iframe[src*="hcaptcha"]'):
                print("🔄 hCaptcha detected...")
                # Similar handling for hCaptcha
                
            # Check for image-based CAPTCHA
            elif driver.is_element_present('img[src*="captcha"], .captcha-image'):
                print("🔄 Image CAPTCHA detected...")
                # Handle image CAPTCHA
                
            return False
            
        except Exception as e:
            print(f"❌ Error in CAPTCHA handling: {e}")
            return False

    @browser(
        headless=HEADLESS_MODE,
        block_images=True,
        block_images_and_css=False,  # Keep CSS for proper interaction
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        window_size=(1366, 768),
        add_arguments=[
            # Core stability arguments
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            
            # Advanced anti-detection
            '--disable-blink-features=AutomationControlled',
            '--disable-features=VizDisplayCompositor,VizServiceDisplay,TranslateUI,AudioServiceOutOfProcess',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-web-security',
            '--disable-ipc-flooding-protection',
            
            # Browser behavior
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-default-apps',
            '--disable-popup-blocking',
            '--disable-prompt-on-repost',
            '--disable-hang-monitor',
            '--disable-sync',
            '--metrics-recording-only',
            '--no-pings',
            '--password-store=basic',
            '--use-mock-keychain',
            
            # Cookie and session handling
            '--enable-cookies',
            '--allow-running-insecure-content',
            '--disable-site-isolation-trials',
            
            # Additional stealth measures
            '--disable-client-side-phishing-detection',
            '--disable-component-update',
            '--disable-domain-reliability',
            '--disable-background-networking',
            '--disable-background-sync',
            '--disable-device-discovery-notifications',
            '--disable-gpu',
            '--disable-gpu-sandbox',
            '--disable-software-rasterizer',
            '--disable-extensions',
            '--disable-plugins-discovery',
            '--disable-preconnect',
            '--disable-print-preview',
            '--hide-scrollbars',
            '--mute-audio',
            '--no-zygote',
            '--disable-accelerated-2d-canvas',
            '--disable-accelerated-jpeg-decoding',
        ],
        max_retry=3,
        reuse_driver=True,
        tiny_profile=True,
        profile="bpu_scraper"
    )
    def scrape_bpu_utility_data(self, driver: Driver, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Advanced BPU scraping with human-like behavior and robust error handling
        """
        try:
            print("🚀 Starting advanced BPU scraper...")
            
            # Validate credentials
            if not BPU_USERNAME or not BPU_PASSWORD:
                raise ValueError("BPU credentials not configured")
            
            # Step 1: Establish realistic browsing session
            self.simulate_realistic_browsing(driver)
            
            # Step 2: Navigate to login page with Google referrer
            print("🔐 Navigating to login page...")
            driver.google_get("https://mymeter.bpu.com/Home/Login")
            
            # Wait for login form to load
            driver.wait_for_element("#Username", timeout=30)
            
            # Step 3: Enhanced cookie and session setup
            print("🍪 Setting up session cookies...")
            
            # Set essential cookies for session persistence
            cookies = [
                {"name": "session_id", "value": f"bpu_session_{int(time.time())}", "domain": ".bpu.com"},
                {"name": "user_pref", "value": "en-US", "domain": ".mymeter.bpu.com"},
            ]
            
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except:
                    pass  # Some cookies may not be settable
            
            # Step 4: Human-like login process
            print("👤 Performing human-like login...")
            
            # Focus and interact with username field
            username_field = driver.get_element("#Username")
            self.human_like_mouse_movement(driver, username_field)
            username_field.click()
            time.sleep(random.uniform(0.5, 1.0))
            
            # Type username with human-like behavior
            self.human_like_typing(driver, username_field, BPU_USERNAME)
            
            # Tab to password field or click it
            password_field = driver.get_element("#Password")
            self.human_like_mouse_movement(driver, password_field)
            password_field.click()
            time.sleep(random.uniform(0.5, 1.0))
            
            # Type password with human-like behavior
            self.human_like_typing(driver, password_field, BPU_PASSWORD)
            
            # Human-like pause before submission (simulate user review)
            time.sleep(random.uniform(2, 5))
            
            # Submit form
            login_button = driver.get_element("input[type='submit'][value='Login']")
            self.human_like_mouse_movement(driver, login_button)
            login_button.click()
            
            # Step 5: Handle post-login challenges
            print("⏳ Handling post-login response...")
            time.sleep(5)
            
            current_url = driver.get_current_url()
            page_content = driver.get_page_source()
            
            # Check for CAPTCHA or errors
            if "Login" in current_url or any(indicator in page_content.lower() 
                                           for indicator in ["captcha", "invalid", "error"]):
                print("🤖 Post-login challenge detected...")
                
                # Handle CAPTCHA if present
                if not self.handle_captcha_challenge(driver):
                    # Take screenshot for debugging
                    driver.save_screenshot(f"screenshots/login_challenge_{int(time.time())}.png")
                    
                    if not HEADLESS_MODE:
                        input("Please resolve any challenges manually and press Enter to continue...")
                
                # Retry login button if still on login page
                if "Login" in driver.get_current_url():
                    login_button = driver.get_element("input[type='submit'][value='Login']")
                    login_button.click()
                    time.sleep(5)
            
            # Step 6: Navigate to property selection
            print("🏠 Accessing property dashboard...")
            
            # Wait for dashboard to load
            driver.wait_for_element("#choosePropertyBtn, .dashboard, .property-select", timeout=30)
            
            # Click choose property button
            if driver.is_element_present("#choosePropertyBtn"):
                choose_btn = driver.get_element("#choosePropertyBtn")
                self.human_like_mouse_movement(driver, choose_btn)
                choose_btn.click()
                time.sleep(3)
            
            # Step 7: Extract comprehensive utility data
            print("📊 Extracting utility data...")
            
            # Wait for data to load
            driver.wait_for_element(".usage-data, .billing-info, .account-summary", timeout=30)
            
            # Extract all available data
            scraped_data = {
                "timestamp": datetime.now().isoformat(),
                "account_info": self.extract_account_info(driver),
                "usage_data": self.extract_usage_data(driver),
                "billing_data": self.extract_billing_data(driver),
                "meter_readings": self.extract_meter_readings(driver),
                "payment_history": self.extract_payment_history(driver),
                "service_alerts": self.extract_service_alerts(driver),
                "scrape_status": "success",
                "url": driver.get_current_url()
            }
            
            print("✅ Data extraction completed successfully")
            
            # Save to Supabase if configured
            if self.supabase:
                self.save_to_supabase(scraped_data)
            
            return scraped_data
            
        except Exception as e:
            print(f"❌ Scraping failed: {e}")
            
            # Comprehensive error logging
            error_data = {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "url": driver.get_current_url() if driver else "unknown",
                "page_title": driver.get_title() if driver else "unknown",
                "scrape_status": "failed"
            }
            
            # Take error screenshot
            try:
                driver.save_screenshot(f"screenshots/error_{int(time.time())}.png")
            except:
                pass
            
            return error_data

    def extract_account_info(self, driver: Driver) -> Dict[str, Any]:
        """Extract comprehensive account information"""
        account_info = {}
        
        selectors = {
            "account_number": [".account-number", "#accountNumber", ".acct-num"],
            "service_address": [".service-address", "#serviceAddress", ".address"],
            "customer_name": [".customer-name", "#customerName", ".name"],
            "account_status": [".account-status", "#accountStatus", ".status"],
            "service_type": [".service-type", "#serviceType", ".utility-type"]
        }
        
        for field, selector_list in selectors.items():
            for selector in selector_list:
                try:
                    if driver.is_element_present(selector):
                        account_info[field] = driver.get_text(selector).strip()
                        break
                except:
                    continue
        
        return account_info

    def extract_usage_data(self, driver: Driver) -> List[Dict[str, Any]]:
        """Extract detailed usage data"""
        usage_data = []
        
        try:
            # Look for usage tables
            usage_rows = driver.get_elements(".usage-row, .consumption-row, tr.usage")
            
            for row in usage_rows:
                try:
                    usage_entry = {
                        "date": self.safe_get_text(row, ".date, .period, .reading-date"),
                        "usage_kwh": self.safe_get_text(row, ".usage, .kwh, .consumption"),
                        "cost": self.safe_get_text(row, ".cost, .amount, .charge"),
                        "rate": self.safe_get_text(row, ".rate, .price-per-kwh"),
                        "meter_reading": self.safe_get_text(row, ".reading, .meter-value")
                    }
                    
                    # Only add if we have meaningful data
                    if any(usage_entry.values()):
                        usage_data.append(usage_entry)
                        
                except Exception as e:
                    print(f"⚠️  Error extracting usage row: {e}")
                    continue
            
        except Exception as e:
            print(f"⚠️  Error extracting usage data: {e}")
        
        return usage_data

    def extract_billing_data(self, driver: Driver) -> List[Dict[str, Any]]:
        """Extract comprehensive billing information"""
        billing_data = []
        
        try:
            # Look for billing tables
            billing_rows = driver.get_elements(".bill-row, .invoice-row, tr.billing")
            
            for row in billing_rows:
                try:
                    billing_entry = {
                        "bill_date": self.safe_get_text(row, ".bill-date, .invoice-date, .date"),
                        "due_date": self.safe_get_text(row, ".due-date, .payment-due"),
                        "amount_due": self.safe_get_text(row, ".amount, .total, .balance"),
                        "status": self.safe_get_text(row, ".status, .payment-status"),
                        "bill_period": self.safe_get_text(row, ".period, .billing-period")
                    }
                    
                    if any(billing_entry.values()):
                        billing_data.append(billing_entry)
                        
                except Exception as e:
                    print(f"⚠️  Error extracting billing row: {e}")
                    continue
            
        except Exception as e:
            print(f"⚠️  Error extracting billing data: {e}")
        
        return billing_data

    def extract_meter_readings(self, driver: Driver) -> List[Dict[str, Any]]:
        """Extract meter reading history"""
        meter_data = []
        
        try:
            meter_rows = driver.get_elements(".meter-row, .reading-row, tr.meter")
            
            for row in meter_rows:
                try:
                    meter_entry = {
                        "reading_date": self.safe_get_text(row, ".date, .reading-date"),
                        "meter_reading": self.safe_get_text(row, ".reading, .value"),
                        "reading_type": self.safe_get_text(row, ".type, .reading-type"),
                        "multiplier": self.safe_get_text(row, ".multiplier, .factor")
                    }
                    
                    if any(meter_entry.values()):
                        meter_data.append(meter_entry)
                        
                except Exception as e:
                    continue
            
        except Exception as e:
            print(f"⚠️  Error extracting meter readings: {e}")
        
        return meter_data

    def extract_payment_history(self, driver: Driver) -> List[Dict[str, Any]]:
        """Extract payment history"""
        payment_data = []
        
        try:
            payment_rows = driver.get_elements(".payment-row, .transaction-row, tr.payment")
            
            for row in payment_rows:
                try:
                    payment_entry = {
                        "payment_date": self.safe_get_text(row, ".date, .payment-date"),
                        "amount": self.safe_get_text(row, ".amount, .payment-amount"),
                        "method": self.safe_get_text(row, ".method, .payment-method"),
                        "confirmation": self.safe_get_text(row, ".confirmation, .reference")
                    }
                    
                    if any(payment_entry.values()):
                        payment_data.append(payment_entry)
                        
                except Exception as e:
                    continue
            
        except Exception as e:
            print(f"⚠️  Error extracting payment history: {e}")
        
        return payment_data

    def extract_service_alerts(self, driver: Driver) -> List[str]:
        """Extract service alerts and notifications"""
        alerts = []
        
        try:
            alert_elements = driver.get_elements(".alert, .notification, .message, .warning")
            
            for alert in alert_elements:
                try:
                    alert_text = alert.get_text().strip()
                    if alert_text and len(alert_text) > 10:  # Filter out empty or very short alerts
                        alerts.append(alert_text)
                except:
                    continue
            
        except Exception as e:
            print(f"⚠️  Error extracting service alerts: {e}")
        
        return alerts

    def safe_get_text(self, parent_element, selector: str) -> str:
        """Safely extract text from an element"""
        try:
            element = parent_element.find_element("css selector", selector)
            return element.text.strip()
        except:
            return ""

    def save_to_supabase(self, data: Dict[str, Any]) -> bool:
        """Save scraped data to Supabase with error handling"""
        try:
            if not self.supabase:
                return False
            
            # Insert into main table
            result = self.supabase.table('bpu_scraper_data').insert(data).execute()
            
            if result.data:
                print("✅ Data saved to Supabase successfully")
                
                # Also save individual data types to separate tables if needed
                self.save_usage_data_to_supabase(data.get('usage_data', []))
                self.save_billing_data_to_supabase(data.get('billing_data', []))
                
                return True
            else:
                print("❌ Failed to save data to Supabase")
                return False
                
        except Exception as e:
            print(f"❌ Error saving to Supabase: {e}")
            return False

    def save_usage_data_to_supabase(self, usage_data: List[Dict[str, Any]]):
        """Save usage data to separate table"""
        try:
            if usage_data and self.supabase:
                for entry in usage_data:
                    entry['scraped_at'] = datetime.now().isoformat()
                
                self.supabase.table('bpu_usage_data').insert(usage_data).execute()
                print(f"✅ Saved {len(usage_data)} usage records to Supabase")
        except Exception as e:
            print(f"⚠️  Error saving usage data: {e}")

    def save_billing_data_to_supabase(self, billing_data: List[Dict[str, Any]]):
        """Save billing data to separate table"""
        try:
            if billing_data and self.supabase:
                for entry in billing_data:
                    entry['scraped_at'] = datetime.now().isoformat()
                
                self.supabase.table('bpu_billing_data').insert(billing_data).execute()
                print(f"✅ Saved {len(billing_data)} billing records to Supabase")
        except Exception as e:
            print(f"⚠️  Error saving billing data: {e}")

# Main execution function
def run_bpu_scraper():
    """Run the BPU scraper"""
    scraper = BPUScraperAdvanced()
    
    # Execute the scraping
    result = scraper.scrape_bpu_utility_data({})
    
    # Save results locally
    timestamp = int(time.time())
    output_file = f"output/bpu_scraper_results_{timestamp}.json"
    bt.write_json(result, output_file)
    
    print(f"📁 Results saved to: {output_file}")
    
    return result

if __name__ == "__main__":
    run_bpu_scraper()
