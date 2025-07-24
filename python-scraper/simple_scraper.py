#!/usr/bin/env python3
"""
Simple BPU Scraper using Botasaurus
No classes, just a straightforward function-based approach
"""

import os
import time
import random
import csv
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from botasaurus import bt
from botasaurus.browser import browser, Driver
from twocaptcha import TwoCaptcha
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Get credentials from environment
BPU_USERNAME = os.getenv('BPU_USERNAME')
BPU_PASSWORD = os.getenv('BPU_PASSWORD')
CAPTCHA_API_KEY = os.getenv('CAPTCHA_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# Initialize 2captcha solver if API key is available
solver = None
if CAPTCHA_API_KEY:
    solver = TwoCaptcha(CAPTCHA_API_KEY)
    print(f"✅ 2captcha initialized with API key: {CAPTCHA_API_KEY[:8]}...")
else:
    print("⚠️ No CAPTCHA_API_KEY found - CAPTCHA solving disabled")

# Initialize Supabase client if URL and key are available
# Prefer SERVICE_KEY (bypasses RLS) over ANON_KEY for data uploads
supabase = None
supabase_key_type = None

if SUPABASE_URL:
    # Try service key first (bypasses RLS policies)
    if SUPABASE_SERVICE_KEY:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            supabase_key_type = "service"
            print(f"✅ Supabase initialized with URL: {SUPABASE_URL[:20]}...")
            print(f"✅ Using service key: {SUPABASE_SERVICE_KEY[:8]}... (bypasses RLS)")
        except Exception as e:
            print(f"❌ Failed to initialize Supabase with service key: {e}")
            supabase = None
    
    # Fallback to anon key if service key not available
    if not supabase and SUPABASE_ANON_KEY:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            supabase_key_type = "anon"
            print(f"✅ Supabase initialized with URL: {SUPABASE_URL[:20]}...")
            print(f"⚠️ Using anon key: {SUPABASE_ANON_KEY[:8]}... (subject to RLS policies)")
        except Exception as e:
            print(f"❌ Failed to initialize Supabase with anon key: {e}")
            supabase = None

if not supabase:
    print("⚠️ Supabase client not initialized - upload disabled")
    if not SUPABASE_URL:
        print("   Missing SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY and not SUPABASE_ANON_KEY:
        print("   Missing both SUPABASE_SERVICE_KEY and SUPABASE_ANON_KEY")
    elif not SUPABASE_SERVICE_KEY:
        print("   Missing SUPABASE_SERVICE_KEY (recommended for data uploads)")
    elif not SUPABASE_ANON_KEY:
        print("   Missing SUPABASE_ANON_KEY")

def detect_captcha(driver: Driver):
    """Detect if CAPTCHA is present on the page"""
    captcha_indicators = [
        # reCAPTCHA indicators
        'iframe[src*="recaptcha"]',
        '.g-recaptcha',
        '#recaptcha',
        '[data-sitekey]',
        # hCaptcha indicators
        'iframe[src*="hcaptcha"]',
        '.h-captcha',
        # Generic CAPTCHA indicators
        '[id*="captcha"]',
        '[class*="captcha"]',
        'img[src*="captcha"]'
    ]
    
    for selector in captcha_indicators:
        if driver.is_element_present(selector):
            print(f"🤖 CAPTCHA detected: {selector}")
            return True
    
    # Check page content for CAPTCHA-related text
    page_text = driver.page_html.lower()
    captcha_text_indicators = [
        'captcha',
        'verify you are human',
        'prove you are not a robot',
        'security check',
        'please complete the security check'
    ]
    
    for text in captcha_text_indicators:
        if text in page_text:
            print(f"🤖 CAPTCHA detected in page text: {text}")
            return True
    
    return False

def solve_recaptcha(driver: Driver, max_retries=3):
    """Solve reCAPTCHA using 2captcha service"""
    if not solver:
        print("❌ No 2captcha solver available - cannot solve CAPTCHA")
        return False
    
    try:
        # Look for reCAPTCHA site key
        site_key_selectors = [
            '[data-sitekey]',
            '.g-recaptcha[data-sitekey]',
            'iframe[src*="recaptcha"]'
        ]
        
        site_key = None
        for selector in site_key_selectors:
            if driver.is_element_present(selector):
                if 'iframe' in selector:
                    # Extract site key from iframe src
                    iframe_src = driver.get_attribute_value(selector, 'src')
                    if 'k=' in iframe_src:
                        site_key = iframe_src.split('k=')[1].split('&')[0]
                else:
                    site_key = driver.get_attribute_value(selector, 'data-sitekey')
                break
        
        if not site_key:
            print("❌ Could not find reCAPTCHA site key")
            return False
        
        print(f"🔑 Found reCAPTCHA site key: {site_key[:20]}...")
        
        # Solve CAPTCHA with retries
        for attempt in range(max_retries):
            try:
                print(f"🧩 Solving reCAPTCHA (attempt {attempt + 1}/{max_retries})...")
                
                result = solver.recaptcha(
                    sitekey=site_key,
                    url=driver.current_url,
                    version='v2'
                )
                
                if result and 'code' in result:
                    captcha_response = result['code']
                    print(f"✅ CAPTCHA solved successfully: {captcha_response[:20]}...")
                    
                    # Inject the solution into the page
                    inject_script = f"""
                    // Set the reCAPTCHA response
                    if (typeof grecaptcha !== 'undefined') {{
                        var textareas = document.querySelectorAll('textarea[name="g-recaptcha-response"]');
                        for (var i = 0; i < textareas.length; i++) {{
                            textareas[i].value = '{captcha_response}';
                            textareas[i].style.display = 'block';
                        }}
                        
                        // Trigger callback if available
                        var recaptchaElement = document.querySelector('.g-recaptcha');
                        if (recaptchaElement && recaptchaElement.dataset.callback) {{
                            var callbackName = recaptchaElement.dataset.callback;
                            if (typeof window[callbackName] === 'function') {{
                                window[callbackName]('{captcha_response}');
                            }}
                        }}
                        
                        console.log('reCAPTCHA response injected successfully');
                        return true;
                    }} else {{
                        console.log('grecaptcha not available');
                        return false;
                    }}
                    """
                    
                    injection_result = driver.run_js(inject_script)
                    if injection_result:
                        print("✅ CAPTCHA response injected successfully")
                        time.sleep(2)  # Wait for response to be processed
                        return True
                    else:
                        print("⚠️ Failed to inject CAPTCHA response")
                        
                else:
                    print(f"❌ CAPTCHA solving failed: {result}")
                    
            except Exception as e:
                print(f"❌ CAPTCHA solving error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 3 + random.uniform(0, 2)  # 3-5 second wait
                    print(f"⏳ Waiting {wait_time:.1f}s before retry...")
                    time.sleep(wait_time)
        
        print(f"❌ Failed to solve CAPTCHA after {max_retries} attempts")
        return False
        
    except Exception as e:
        print(f"❌ CAPTCHA solving error: {e}")
        return False

def handle_captcha_if_present(driver: Driver):
    """Check for and handle CAPTCHA if present"""
    if detect_captcha(driver):
        print("🤖 CAPTCHA detected - attempting to solve...")
        driver.save_screenshot("screenshots/captcha_detected.png")
        
        if solve_recaptcha(driver):
            print("✅ CAPTCHA solved successfully")
            driver.save_screenshot("screenshots/captcha_solved.png")
            time.sleep(2)  # Wait for page to process
            return True
        else:
            print("❌ Failed to solve CAPTCHA")
            driver.save_screenshot("screenshots/captcha_failed.png")
            return False
    
    return True  # No CAPTCHA present

def human_like_mouse_movement(driver: Driver, selector: str):
    """Simulate human-like mouse movement to element"""
    try:
        # Get element using Botasaurus
        if not driver.is_element_present(selector):
            print(f"⚠️ Element {selector} not found for mouse movement")
            return False
            
        # Use JavaScript to simulate realistic mouse movement and hover
        mouse_script = f"""
        var element = document.querySelector('{selector}');
        if (element) {{
            var rect = element.getBoundingClientRect();
            var x = rect.left + (rect.width / 2) + (Math.random() * 20 - 10);
            var y = rect.top + (rect.height / 2) + (Math.random() * 10 - 5);
            
            // Dispatch mouseover event
            var mouseOverEvent = new MouseEvent('mouseover', {{
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': x,
                'clientY': y
            }});
            element.dispatchEvent(mouseOverEvent);
            
            // Dispatch mouseenter event
            var mouseEnterEvent = new MouseEvent('mouseenter', {{
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': x,
                'clientY': y
            }});
            element.dispatchEvent(mouseEnterEvent);
            
            // Add visual focus effect
            element.style.outline = '2px solid rgba(0, 123, 255, 0.3)';
            setTimeout(function() {{
                element.style.outline = '';
            }}, 200);
            
            return true;
        }}
        return false;
        """
        
        result = driver.run_js(mouse_script)
        if result:
            print(f"🖱️ Mouse moved to {selector}")
            time.sleep(random.uniform(0.1, 0.3))  # Small delay after mouse movement
            return True
        else:
            print(f"⚠️ Mouse movement failed for {selector}")
            return False
            
    except Exception as e:
        print(f"❌ Mouse movement error for {selector}: {e}")
        return False

@browser(
    profile="nicholas",
    tiny_profile=True,
    headless=os.getenv('HEADLESS_MODE', 'false').lower() == 'true',
)
def scrape_bpu(driver: Driver, data):
    """Simple BPU scraper function"""
    
    print("🚀 Starting BPU scraper...")
    
    # Check if we have credentials
    if not BPU_USERNAME or not BPU_PASSWORD:
        print("❌ BPU_USERNAME and BPU_PASSWORD must be set in .env file")
        return {"error": "Missing credentials"}
    
    try:
        # Step 1: Visit Google first (human-like behavior)
        print("🌐 Visiting Google first...")
        driver.get("https://www.google.com")
        time.sleep(2)
        
        # Step 2: Go to BPU main site
        print("🏢 Navigating to BPU main site...")
        driver.get("https://www.bpu.com")
        time.sleep(3)
        
        # Step 3: Go to login page
        print("🔐 Going to BPU login page...")
        driver.google_get("https://mymeter.bpu.com")
        time.sleep(3)

        # Step 4: Check if we need to login or if we're already logged in
        print("🔍 Checking current page status...")
        current_url = driver.current_url
        print(f"📍 Current URL before login: {current_url}")

        # Check if we're already on the dashboard/data page (session persistence)
        if '/Dashboard' in current_url or driver.is_element_present('#choosePropertyBtn') or driver.is_element_present('a.dashboard-data'):
            print("✅ Already logged in! Site redirected directly to dashboard/data page")
            print("🚀 Skipping login and proceeding to data extraction...")
        else:
            print("🔑 Login required - proceeding with login form...")
            
            # Perform login process
            login_result = perform_login(driver, BPU_USERNAME, BPU_PASSWORD)
            if "error" in login_result:
                return login_result
        
        print("🚀 Proceeding to post-login navigation...")
        
        # Take a screenshot of current state
        driver.save_screenshot("screenshots/post_login_state.png")
        print("📸 Post-login state screenshot: screenshots/post_login_state.png")
        
        # Step 6: Proceed directly to post-login navigation
        current_url = driver.current_url
        print(f"📍 Current URL: {current_url}")
        
        # Step 7: Navigate to Choose Property
        print("🏠 Clicking Choose Property button...")
        try:
            # Wait for and click the Choose Property button (skip CAPTCHA check since we're already logged in)
            print("🔍 Looking for Choose Property button...")
            choose_property_btn = driver.wait_for_element("#choosePropertyBtn")
            print("✅ Choose Property button found")
            
            human_like_mouse_movement(driver, "#choosePropertyBtn")
            time.sleep(random.uniform(1, 2))
            
            driver.click("#choosePropertyBtn")
            print("✅ Clicked Choose Property button")
            time.sleep(3)
            
        except Exception as e:
            print(f"❌ Error clicking Choose Property: {e}")
            
            # Log the error and continue
            print(f"❌ Choose Property button not found or clickable: {e}")
            driver.save_screenshot(f"screenshots/chooseProperty_error_{int(time.time())}.png")
            raise e
        
        # Step 8: Click "All Meters"
        print("⚡ Clicking All Meters...")
        try:
            # Use JavaScript to find and click the element containing "All Meters" text
            all_meters_script = """
            var elements = document.querySelectorAll('h2, h3, h4, span, div, a');
            var allMetersElement = null;
            for (var i = 0; i < elements.length; i++) {
                if (elements[i].textContent && elements[i].textContent.includes('All Meters')) {
                    allMetersElement = elements[i];
                    break;
                }
            }
            return allMetersElement ? true : false;
            """
            
            found = driver.run_js(all_meters_script)
            if found:
                print("✅ All Meters element found via JavaScript")
                # Click using JavaScript
                click_script = """
                var elements = document.querySelectorAll('h2, h3, h4, span, div, a');
                for (var i = 0; i < elements.length; i++) {
                    if (elements[i].textContent && elements[i].textContent.includes('All Meters')) {
                        elements[i].click();
                        return true;
                    }
                }
                return false;
                """
                clicked = driver.run_js(click_script)
                if clicked:
                    print("✅ Clicked All Meters via JavaScript")
                    time.sleep(5)  # Wait for navigation
                else:
                    print("❌ Failed to click All Meters")
                    return {"error": "Failed to click All Meters"}
            else:
                print("❌ All Meters element not found")
                driver.save_screenshot("screenshots/all_meters_not_found.png")
                return {"error": "All Meters element not found"}
        
        except Exception as e:
            print(f"❌ Error clicking All Meters: {e}")
            raise e
        
        # Step 9: Navigate to Data Section
        print("📊 Clicking Data button...")
        try:
            # Updated selector based on actual DOM structure
            data_button = driver.wait_for_element("a.dashboard-data")
            print("✅ Data button found")
            
            human_like_mouse_movement(driver, "a.dashboard-data")
            time.sleep(random.uniform(1, 2))
            driver.click("a.dashboard-data")
            print("✅ Clicked Data button")
            time.sleep(5)  # Wait for navigation
            
        except Exception as e:
            print(f"❌ Error clicking Data button: {e}")
        # Step 10: Click Download Link
        print("💾 Clicking Download link...")
        try:
            # Use the exact selector from working TypeScript version
            download_link = driver.wait_for_element("span.icon-Download.mainButton > a")
            print("✅ Download link found")
            
            human_like_mouse_movement(driver, "span.icon-Download.mainButton > a")
            time.sleep(random.uniform(1, 2))
            driver.click("span.icon-Download.mainButton > a")
            print("✅ Clicked Download link")
            time.sleep(5)  # Wait for navigation
            
        except Exception as e:
            print(f"❌ Error clicking Download link: {e}")
            raise e
        
        # Step 11: Set Date Range
        print("📅 Setting date range...")
        try:
            from datetime import datetime, timedelta
            
            # Use current date (July 24, 2025) as provided by user
            today = datetime(2025, 7, 24)
            one_week_ago = today - timedelta(days=7)
            
            # Use ISO format (YYYY-MM-DD) like the working TypeScript version
            start_date_str = one_week_ago.strftime('%Y-%m-%d')  # Should be 2025-07-17
            end_date_str = today.strftime('%Y-%m-%d')  # Should be 2025-07-24
            
            print(f"📅 Setting Start Date to: {start_date_str} (1 week before today)")
            # Use JavaScript to set date value directly (like TypeScript version)
            start_date_script = f"""
            var startDateInput = document.getElementById('DownloadStartDate');
            if (startDateInput) {{
                startDateInput.value = '{start_date_str}';
                return true;
            }}
            return false;
            """
            
            if driver.run_js(start_date_script):
                print(f"✅ Start date set successfully: {start_date_str}")
            else:
                print(f"⚠️ Failed to set start date")
            
            print(f"📅 Setting End Date to: {end_date_str} (today)")
            # Use JavaScript to set date value directly (like TypeScript version)
            end_date_script = f"""
            var endDateInput = document.getElementById('DownloadEndDate');
            if (endDateInput) {{
                endDateInput.value = '{end_date_str}';
                return true;
            }}
            return false;
            """
            
            if driver.run_js(end_date_script):
                print(f"✅ End date set successfully: {end_date_str}")
            else:
                print(f"⚠️ Failed to set end date")
            
            print("✅ Date range set successfully")
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error setting date range: {e}")
            raise e
        
        # Step 12: Create downloads directory and clear old files
        print("📁 Preparing downloads directory...")
        downloads_dir = "downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Clear any old CSV files
        try:
            for filename in os.listdir(downloads_dir):
                if filename.endswith('.csv'):
                    file_path = os.path.join(downloads_dir, filename)
                    os.remove(file_path)
                    print(f"🗑️ Deleted old CSV: {filename}")
        except Exception as e:
            print(f"⚠️ Error clearing old CSV files: {e}")
        
        # Step 13: Trigger Download
        print("🚀 Triggering CSV download...")
        try:
            # Use the exact button selector provided by user: <button id="downloadSubmit" type="button" class="btn btn-primary">Download</button>
            download_submit_btn = driver.wait_for_element("button#downloadSubmit")
            print("✅ Download submit button found")
            
            human_like_mouse_movement(driver, "button#downloadSubmit")
            time.sleep(random.uniform(1, 2))
            driver.click("button#downloadSubmit")
            print("✅ Clicked download submit button")
            
            # Take screenshot after download click
            screenshot_path = f"screenshots/post_download_click_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            print(f"📸 Post-download screenshot: {screenshot_path}")
            
        except Exception as e:
            print(f"❌ Error triggering download: {e}")
            raise e
        
        # Step 14: Wait for CSV download to complete
        print("⏳ Waiting for CSV download to complete...")
        downloaded_file = None
        download_timeout = 90  # 90 seconds
        poll_interval = 1  # 1 second
        time_waited = 0
        
        # Check both local downloads directory and system Downloads folder
        system_downloads_dir = os.path.expanduser("~/Downloads")
        search_directories = [downloads_dir, system_downloads_dir]
        
        while time_waited < download_timeout:
            try:
                for search_dir in search_directories:
                    if not os.path.exists(search_dir):
                        print(f"⚠️ Directory does not exist: {search_dir}")
                        continue
                        
                    current_files = os.listdir(search_dir)
                    dir_name = "local" if search_dir == downloads_dir else "system"
                    print(f"📂 Polling {dir_name} downloads directory ({search_dir}). Files found: {', '.join(current_files) if current_files else 'None'}")
                    
                    # Look for CSV files, prioritizing recent usage files
                    csv_files = [f for f in current_files if f.endswith('.csv')]
                    usage_csv_files = [f for f in csv_files if 'usage' in f.lower()]
                    
                    print(f"🔍 Found {len(csv_files)} CSV files: {csv_files}")
                    print(f"🎯 Found {len(usage_csv_files)} usage CSV files: {usage_csv_files}")
                    
                    target_file = None
                    if usage_csv_files:
                        # Sort by modification time, get most recent
                        usage_files_with_time = [(f, os.path.getmtime(os.path.join(search_dir, f))) for f in usage_csv_files]
                        usage_files_with_time.sort(key=lambda x: x[1], reverse=True)
                        target_file = usage_files_with_time[0][0]
                        print(f"📈 Selected most recent usage file: {target_file}")
                    elif csv_files:
                        # Fallback to any CSV file
                        csv_files_with_time = [(f, os.path.getmtime(os.path.join(search_dir, f))) for f in csv_files]
                        csv_files_with_time.sort(key=lambda x: x[1], reverse=True)
                        target_file = csv_files_with_time[0][0]
                        print(f"📄 Selected most recent CSV file: {target_file}")
                    
                    if target_file:
                        downloaded_file = os.path.join(search_dir, target_file)
                        print(f"✅ CSV file detected: {downloaded_file}")
                        # Verify file exists and is readable
                        if os.path.exists(downloaded_file):
                            file_size = os.path.getsize(downloaded_file)
                            print(f"📊 File size: {file_size} bytes")
                            if file_size > 0:
                                print(f"🎉 Valid CSV file found, breaking out of polling loop")
                                break
                            else:
                                print(f"⚠️ File is empty, continuing to poll...")
                                target_file = None
                                downloaded_file = None
                        else:
                            print(f"❌ File path doesn't exist: {downloaded_file}")
                            target_file = None
                            downloaded_file = None
                
                if downloaded_file:
                    break
                    
            except Exception as e:
                print(f"⚠️ Error checking downloads directories: {e}")
            
            time.sleep(poll_interval)
            time_waited += poll_interval
        
        if not downloaded_file:
            raise Exception("CSV file download timed out or failed")
        
        # Step 15: Read and parse CSV data
        print(f"📖 Reading CSV content from {downloaded_file}...")
        csv_data = []
        parsed_usage_data = []
        
        try:
            print(f"📖 Attempting to read CSV file: {downloaded_file}")
            print(f"📊 File exists: {os.path.exists(downloaded_file)}")
            print(f"📊 File size: {os.path.getsize(downloaded_file)} bytes")
            
            with open(downloaded_file, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                headers = csv_reader.fieldnames
                print(f"📊 CSV headers: {headers}")
                
                # Parse CSV rows with TypeScript-matching logic
                for row_num, row in enumerate(csv_reader):
                    if row_num < 5:  # Show first 5 rows for debugging
                        print(f"  Row {row_num + 1}: {dict(row)}")
                    
                    # Normalize keys (lowercase and trim) for robust access - matching TypeScript
                    normalized_record = {}
                    for key, value in row.items():
                        if key:  # Skip None keys
                            normalized_key = key.lower().strip()
                            normalized_record[normalized_key] = value
                    
                    # Extract data using known CSV headers (after normalization) - matching TypeScript
                    account_number = normalized_record.get('account number', '')
                    meter_id = normalized_record.get('meter', '')
                    start_date_time_string = normalized_record.get('start', '')
                    name = normalized_record.get('name', '')
                    location = normalized_record.get('location', '')
                    address = normalized_record.get('address', '')
                    estimated_indicator = normalized_record.get('estimated indicator', '')
                    ccf_value_from_csv = normalized_record.get('ccf', '')  # Raw usage string from CSV 'CCF' column
                    cost_string_from_csv = normalized_record.get('$', '')  # Raw cost string from CSV '$' column
                    
                    # Validate essential fields for primary key - matching TypeScript
                    if not account_number or not meter_id or not start_date_time_string:
                        print(f"⚠️ Skipping record due to missing primary key components. "
                              f"Account: {account_number}, Meter: {meter_id}, Start: {start_date_time_string}. "
                              f"Original record: {dict(row)}")
                        continue  # Skip this record
                    
                    # Parse date - matching TypeScript logic
                    try:
                        # TypeScript uses: new Date(startDateTimeString).toISOString()
                        # Handle various date formats that might come from CSV
                        if '/' in start_date_time_string:
                            # Format like "07/17/2025 12:00:00 AM"
                            date_part = start_date_time_string.split(' ')[0]  # Get just the date part
                            parsed_date = datetime.strptime(date_part, '%m/%d/%Y')
                        else:
                            # Try parsing as-is
                            parsed_date = datetime.fromisoformat(start_date_time_string.replace('Z', '+00:00'))
                        
                        start_iso = parsed_date.isoformat()
                    except (ValueError, TypeError) as e:
                        print(f"⚠️ Error parsing date '{start_date_time_string}': {e}")
                        start_iso = datetime.now().isoformat()
                    
                    # Parse numeric values - matching TypeScript logic
                    usage_numeric = None
                    cost_numeric = None
                    
                    # Usage: ccfValueFromCsv ? parseFloat(ccfValueFromCsv) : null
                    if ccf_value_from_csv:
                        try:
                            usage_numeric = float(ccf_value_from_csv)
                        except (ValueError, TypeError):
                            usage_numeric = None
                    
                    # Cost: costStringFromCsv ? parseFloat(costStringFromCsv.replace('$', '')) : null
                    if cost_string_from_csv:
                        try:
                            cost_numeric = float(cost_string_from_csv.replace('$', ''))
                        except (ValueError, TypeError):
                            cost_numeric = None
                    
                    # Prepare data for Supabase, matching Supabase column names - EXACTLY like TypeScript
                    supabase_data = {
                        'Start': start_iso,
                        'Account Number': account_number,
                        'Name': name,
                        'Meter': meter_id,
                        'Location': location,
                        'Address': address,
                        'Estimated Indicator': estimated_indicator,
                        'CCF': ccf_value_from_csv,  # Map raw CSV 'CCF' (usage string) to Supabase 'CCF' (text) column
                        '$': cost_string_from_csv,   # Map raw CSV '$' (cost string) to Supabase '$' (text) column
                        'UOM': 'CCF',  # Unit of Measure
                        'Usage': usage_numeric,  # Numeric usage to Supabase 'Usage' (numeric) column
                        'Cost': cost_numeric     # Numeric cost to Supabase 'Cost' (numeric) column
                    }
                    
                    parsed_usage_data.append(supabase_data)
                    csv_data.append(dict(row))  # Keep original format too
                
                print(f"📈 Parsed {len(parsed_usage_data)} usage records")
                
                # Deduplicate records based on (Account Number, Meter, Start) - matching TypeScript logic
                print(f"🔄 Deduplicating records before upload...")
                unique_records = {}
                for record in parsed_usage_data:
                    # Create unique key from primary key components
                    unique_key = (record['Account Number'], record['Meter'], record['Start'])
                    if unique_key not in unique_records:
                        unique_records[unique_key] = record
                    else:
                        print(f"⚠️ Duplicate record found and skipped: {unique_key}")
                
                # Convert back to list
                parsed_usage_data = list(unique_records.values())
                print(f"✅ After deduplication: {len(parsed_usage_data)} unique records")
                    
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            csv_data = [f"Error reading CSV: {str(e)}"]
            parsed_usage_data = []
        
        # Step 16: Upload data to Supabase
        supabase_upload_success = False
        if supabase and parsed_usage_data:
            try:
                print(f"☁️ Uploading {len(parsed_usage_data)} records to Supabase...")
                print(f"📊 Sample record structure: {parsed_usage_data[0] if parsed_usage_data else 'None'}")
                
                # Upload to 'Meter Readings' table (matching TypeScript scraper)
                # Use same conflict resolution as TypeScript: 'Account Number, Meter, Start'
                result = supabase.table('Meter Readings').upsert(
                    parsed_usage_data,
                    on_conflict='Account Number,Meter,Start'
                ).execute()
                
                print(f"📤 Supabase response: {result}")
                
                if result.data:
                    print(f"✅ Successfully uploaded {len(result.data)} records to Supabase")
                    print(f"📋 Uploaded records: {result.data[:2] if len(result.data) > 0 else 'None'}...")
                    supabase_upload_success = True
                else:
                    print("⚠️ Supabase upload returned no data")
                    print(f"📋 Full result object: {vars(result) if hasattr(result, '__dict__') else result}")
                    
            except Exception as e:
                print(f"❌ Error uploading to Supabase: {e}")
                print(f"📋 Error type: {type(e).__name__}")
                import traceback
                print(f"📋 Full traceback: {traceback.format_exc()}")
        elif not supabase:
            print("⚠️ Supabase not configured - skipping upload")
            print(f"   SUPABASE_URL present: {bool(SUPABASE_URL)}")
            print(f"   SUPABASE_SERVICE_KEY present: {bool(SUPABASE_SERVICE_KEY)}")
            print(f"   SUPABASE_ANON_KEY present: {bool(SUPABASE_ANON_KEY)}")
            print(f"   Key type used: {supabase_key_type if supabase else 'None'}")
        elif not parsed_usage_data:
            print("⚠️ No parsed data to upload to Supabase")
        
        # Extract account information from current page
        print("📋 Extracting account information...")
        account_info = []
        try:
            # Look for account details on the current page
            account_selectors = ['.account-info', '.user-info', '[data-account]', '.profile-info', '.account-details']
            for selector in account_selectors:
                if driver.is_element_present(selector):
                    elements = driver.select_all(selector)
                    for elem in elements[:5]:  # Limit to first 5 elements
                        text = driver.get_text(elem).strip() if elem else ''
                        if text and len(text) > 3:  # Only meaningful text
                            account_info.append(text)
                    break  # Stop after finding first matching selector
        except Exception as e:
            print(f"⚠️ Error extracting account info: {e}")
        
        # Step 16: Take a screenshot of the final page
        screenshot_path = f"screenshots/final_page_{int(time.time())}.png"
        driver.save_screenshot(screenshot_path)
        print(f"📸 Screenshot saved: {screenshot_path}")
        
        # Prepare results
        results = {
            "scrape_status": "success",
            "timestamp": time.time(),
            "url": driver.current_url,
            "account_info": account_info,
            "csv_data": csv_data,
            "parsed_usage_data": parsed_usage_data,
            "csv_file_path": downloaded_file,
            "screenshot": screenshot_path,
            "supabase_upload_success": supabase_upload_success,
            "records_uploaded": len(parsed_usage_data) if supabase_upload_success else 0
        }
        
        print("✅ Scraping completed successfully!")
        return results
        
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        
        # Take error screenshot
        try:
            error_screenshot = f"screenshots/error_{int(time.time())}.png"
            driver.save_screenshot(error_screenshot)
            print(f"📸 Error screenshot: {error_screenshot}")
        except:
            pass
        
        return {
            "scrape_status": "error",
            "error": str(e),
            "timestamp": time.time(),
            "url": driver.current_url if driver else "unknown"
        }

if __name__ == "__main__":
    # Run the scraper
    print("🎯 Running simple BPU scraper...")
    
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)
    
    # Run scraper with empty data (Botasaurus requirement)
    results = scrape_bpu([{}])
    
    # Save results
    if results:
        result = results[0]  # Get first result
        output_file = f"output/simple_scraper_results_{int(time.time())}.json"
        bt.write_json(result, output_file)
        print(f"💾 Results saved to: {output_file}")
        
        if result.get("scrape_status") == "success":
            print("🎉 BPU scraping completed successfully!")
            print(f"📊 Found {len(result.get('usage_data', []))} usage data points")
        else:
            print("❌ Scraping failed - check the error details above")
    else:
        print("❌ No results returned")
