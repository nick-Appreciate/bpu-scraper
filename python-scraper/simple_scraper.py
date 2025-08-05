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

# Initialize 2captcha solver if API key is available
solver = None
if CAPTCHA_API_KEY:
    solver = TwoCaptcha(CAPTCHA_API_KEY)
    print(f"✅ 2captcha initialized with API key: {CAPTCHA_API_KEY[:8]}...")
else:
    print("⚠️ No CAPTCHA_API_KEY found - CAPTCHA solving disabled")

# Initialize Supabase client (if needed)
supabase = None
supabase_url = os.environ.get('SUPABASE_URL')
supabase_anon_key = os.environ.get('SUPABASE_ANON_KEY')
supabase_service_key = os.environ.get('SUPABASE_SERVICE_KEY')

print(f"Supabase URL available: {bool(supabase_url)}")
print(f"Supabase anon key available: {bool(supabase_anon_key)}")
print(f"Supabase service key available: {bool(supabase_service_key)}")

# Try service key first (can bypass RLS policies), then fallback to anon key
supabase_key = supabase_service_key or supabase_anon_key
key_type = "SERVICE KEY" if supabase_service_key and supabase_key == supabase_service_key else "ANON KEY"

if supabase_url and supabase_key:
    try:
        print(f"Initializing Supabase client with URL: {supabase_url}")
        # Mask key for security in logs
        masked_key = supabase_key[:5] + "*****" + supabase_key[-5:] if len(supabase_key) > 10 else "*****"
        print(f"Using {key_type}: {masked_key}")
        supabase = create_client(supabase_url, supabase_key)
        print("\u2705 Supabase client initialized successfully")
    except Exception as e:
        print(f"\u274c Failed to initialize Supabase client: {e}")
        supabase = None
else:
    print("\u26a0\ufe0f Supabase URL or key not provided. Skipping Supabase integration.")
    if not supabase_url:
        print("   - SUPABASE_URL is missing")
    if not supabase_anon_key and not supabase_service_key:
        print("   - Both SUPABASE_ANON_KEY and SUPABASE_SERVICE_KEY are missing")

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

def perform_login(driver: Driver, username: str, password: str):
    """Handle the login process on the BPU website with improved form detection"""
    print("🔑 Performing login...")
    
    try:
        # Debug current page state
        print("📊 Analyzing login page state...")
        driver.save_screenshot("screenshots/login_page_state.png")
        print(f"📍 Current URL: {driver.current_url}")
        
        # Use specific selectors for BPU login form
        username_field = '#LoginEmail'
        password_field = '#LoginPassword'
        submit_button = 'button.btn-primary.loginBtn'
        
        # Check if the specific BPU form elements are present
        if driver.is_element_present(username_field) and driver.is_element_present(password_field) and driver.is_element_present(submit_button):
            print(f"✅ Found BPU login form elements with specific selectors")
        else:
            print("⚠️ BPU specific login form elements not found, trying alternative detection...")
            print("⚠️ Standard login form not detected, trying alternative approach...")
            
            # Look for any form with password fields
            login_form_script = """
            // Find form with password input
            var forms = document.querySelectorAll('form');
            var loginForm = null;
            
            for (var i = 0; i < forms.length; i++) {
                if (forms[i].querySelector('input[type="password"]')) {
                    loginForm = forms[i];
                    break;
                }
            }
            
            if (loginForm) {
                // Find username/email field (usually the text/email input before password)
                var possibleUserFields = loginForm.querySelectorAll('input[type="text"], input[type="email"]');
                var userField = possibleUserFields.length > 0 ? possibleUserFields[0] : null;
                
                // Find password field
                var passField = loginForm.querySelector('input[type="password"]');
                
                // Find submit button
                var submitButton = loginForm.querySelector('input[type="submit"], button[type="submit"], button:not([type])');
                
                return {
                    hasLoginForm: true,
                    userFieldId: userField ? userField.id : '',
                    userFieldName: userField ? userField.name : '',
                    passwordFieldId: passField ? passField.id : '',
                    passwordFieldName: passField ? passField.name : '',
                    submitButtonExists: !!submitButton
                };
            }
            
            return { hasLoginForm: false };
            """
            
            form_detection_result = driver.run_js(login_form_script)
            print(f"🔍 Form detection result: {form_detection_result}")
            
            if isinstance(form_detection_result, dict) and form_detection_result.get('hasLoginForm'):
                # If the username field has an ID, use it
                if form_detection_result.get('userFieldId'):
                    username_field = f"#{form_detection_result['userFieldId']}"
                # Otherwise use name attribute
                elif form_detection_result.get('userFieldName'):
                    username_field = f"input[name=\"{form_detection_result['userFieldName']}\"]"
                
                # If the password field has an ID, use it
                if form_detection_result.get('passwordFieldId'):
                    password_field = f"#{form_detection_result['passwordFieldId']}"
                # Otherwise use name attribute
                elif form_detection_result.get('passwordFieldName'):
                    password_field = f"input[name=\"{form_detection_result['passwordFieldName']}\"]"
                
                print(f"✅ Detected form fields - Username: {username_field}, Password: {password_field}")
        
        # If we still can't find the form, try navigating to login page explicitly
        if not username_field or not password_field:
            print("⚠️ Login form not found, trying to navigate to login page...")
            driver.google_get("https://mymeter.bpu.com/login")
            time.sleep(3)
            
            # Retry form detection
            for selector in possible_username_selectors:
                if driver.is_element_present(selector):
                    username_field = selector
                    print(f"✅ Found username field after navigation: {selector}")
                    break
            
            for selector in possible_password_selectors:
                if driver.is_element_present(selector):
                    password_field = selector
                    print(f"✅ Found password field after navigation: {selector}")
                    break
        
        # If still no form, give up
        if not username_field or not password_field:
            print("❌ Login form not found even after trying multiple approaches")
            driver.save_screenshot("screenshots/login_form_not_found.png")
            
            # Print page HTML for debugging
            print("📄 Saving page HTML for debugging...")
            with open("screenshots/login_page_html.txt", "w", encoding="utf-8") as f:
                f.write(driver.page_html)
            
            return {"error": "Login form not found"}
        
        # Check for CAPTCHA before entering credentials
        handle_captcha_if_present(driver)
        
        # Clear and enter username with human-like typing
        print(f"👤 Entering username: {username[:3]}***...")
        
        # First try using Botasaurus clear and type methods
        try:
            driver.clear(username_field)
            time.sleep(random.uniform(0.3, 0.7))
            
            # Type username with random delays between characters
            for char in username:
                driver.type(username_field, char)
                time.sleep(random.uniform(0.05, 0.15))  # Random delay between keystrokes
        except Exception as e:
            print(f"⚠️ Standard typing method failed: {e}, trying JavaScript...")
            # Fallback to JavaScript if Botasaurus methods fail
            user_script = f"""
            var userField = document.querySelector('{username_field}');
            if (userField) {{
                userField.value = '{username}';
                return true;
            }}
            return false;
            """
            
            if driver.run_js(user_script):
                print("✅ Username entered via JavaScript")
            else:
                print("❌ Failed to enter username via JavaScript")
        
        time.sleep(random.uniform(0.8, 1.2))  # Pause between fields
        
        # Clear and enter password with human-like typing
        print("🔒 Entering password: ********")
        try:
            driver.clear(password_field)
            time.sleep(random.uniform(0.3, 0.7))
            
            # Type password with random delays between characters
            for char in password:
                driver.type(password_field, char)
                time.sleep(random.uniform(0.05, 0.15))  # Random delay between keystrokes
        except Exception as e:
            print(f"⚠️ Standard typing method failed: {e}, trying JavaScript...")
            # Fallback to JavaScript if Botasaurus methods fail
            pass_script = f"""
            var passField = document.querySelector('{password_field}');
            if (passField) {{
                passField.value = '{password}';
                return true;
            }}
            return false;
            """
            if driver.run_js(pass_script):
                print("✅ Password entered via JavaScript")
            else:
                print("❌ Failed to enter password via JavaScript")
        
        # Take a screenshot before clicking login (for debugging)
        driver.save_screenshot("screenshots/pre_login_click.png")
        
        # We already have the submit button selector, just verify it's still present
        if not driver.is_element_present(submit_button):
            print("⚠️ Login button not found with specific selector, trying alternative methods...")
            find_button_script = """
            var buttons = document.querySelectorAll('button, input[type="submit"]');
            for (var i = 0; i < buttons.length; i++) {
                var text = buttons[i].textContent || buttons[i].value || '';
                if (/log.?in|sign.?in|submit|enter/i.test(text)) {
                    return buttons[i].outerHTML;
                }
            }
            return '';
            """
            button_html = driver.run_js(find_button_script)
            if button_html:
                print(f"✅ Found button by text: {button_html[:50]}...")
                # Try to submit the form directly
                submit_form_script = """
                var form = document.querySelector('form');
                if (form) {
                    form.submit();
                    return true;
                }
                return false;
                """
                if driver.run_js(submit_form_script):
                    submit_button = 'form' # Just a placeholder, we already submitted
                    print("✅ Submitted form directly via JavaScript")
        
        # Click the login button if found
        if submit_button:
            print("👆 Clicking login button...")
            # Only attempt mouse movement if it's an actual element (not our placeholder)
            if submit_button != 'form':
                human_like_mouse_movement(driver, submit_button)
                time.sleep(random.uniform(0.3, 0.7))
                driver.click(submit_button)
            print("✅ Login form submitted")
        else:
            print("❌ Could not find submit button, trying form submission...")
            # Last resort - try to submit any form with password field
            form_submit_script = """
            var form = document.querySelector('form:has(input[type="password"])');
            if (form) {
                form.submit();
                return true;
            }
            return false;
            """
            if driver.run_js(form_submit_script):
                print("✅ Form submitted via JavaScript")
            else:
                print("❌ Could not submit form")
                driver.save_screenshot("screenshots/submit_button_not_found.png")
                return {"error": "Could not find login button or submit form"}
        
        # Wait for login to process
        print("⏳ Waiting for login process...")
        time.sleep(10)  # Increased initial wait time
        
        # Check if login was successful by looking for dashboard elements
        login_timeout = 60  # Extended timeout to 60 seconds
        poll_interval = 3  # 3 seconds between checks
        login_wait_time = 0
        login_success = False
        
        while login_wait_time < login_timeout:
            current_url = driver.current_url
            print(f"📍 Current URL: {current_url}")
            driver.save_screenshot(f"screenshots/login_wait_{login_wait_time}.png")
            
            # More comprehensive check for successful login indicators
            success_indicators = [
                '/Dashboard' in current_url,
                'MyAccount' in current_url,
                'Account' in current_url,
                driver.is_element_present('#choosePropertyBtn'),
                driver.is_element_present('a.dashboard-data'),
                driver.is_element_present('.dashboard'),
                driver.is_element_present('.account-info'),
                driver.is_element_present('.user-account'),
                driver.is_element_present('.account-dashboard'),
                driver.is_element_present('a[href*="Logout"]'),
                'Welcome' in driver.page_html and 'Account' in driver.page_html,
                'mymeter.bpu.com/Home/Dashboard' in current_url
            ]
            
            if any(success_indicators):
                print("✅ Login successful!")
                login_success = True
                break
                
            # Check for login failure indicators
            failure_indicators = [
                driver.is_element_present('.validation-summary-errors'),
                driver.is_element_present('#login-error-message'),
                'error' in driver.current_url.lower(),
                'invalid' in driver.page_html.lower() and 'password' in driver.page_html.lower()
            ]
            
            if any(failure_indicators):
                # Try to get specific error message
                error_selectors = [
                    '.validation-summary-errors', '#login-error-message',
                    '.error-message', '.alert-danger', '.alert-error'
                ]
                
                error_text = "Unknown login error"
                for selector in error_selectors:
                    if driver.is_element_present(selector):
                        error_text = driver.get_text(selector)
                        break
                
                print(f"❌ Login failed: {error_text}")
                driver.save_screenshot("screenshots/login_failed.png")
                return {"error": f"Login failed: {error_text}"}
            
            # Check for redirection URLs that indicate success despite CAPTCHA warnings
            redirect_success_urls = [
                'Integration/LoginActions' in current_url,
                'ProcessLogin' in current_url,
                'Auth' in current_url
            ]
            
            # If we're at a redirect URL that suggests successful form submission
            if any(redirect_success_urls) and login_wait_time < 15:
                print(f"⏳ At login processing URL: {current_url} - continuing to wait...")
                time.sleep(poll_interval)
                login_wait_time += poll_interval
                continue
            
            # Check for CAPTCHA again - may appear after login attempt
            if detect_captcha(driver):
                # If we're already at a page that suggests successful login processing
                # but still seeing CAPTCHA, we'll just try to continue
                if any(redirect_success_urls) and login_wait_time >= 15:
                    print("⚠️ CAPTCHA detected but login appears to be processing - assuming success")
                    print("✅ Continuing with the workflow despite CAPTCHA warning")
                    login_success = True
                    break
                
                print("🤖 CAPTCHA detected during login - attempting to solve...")
                captcha_result = handle_captcha_if_present(driver)
                if captcha_result:
                    print("✅ CAPTCHA handled during login - retrying login...")
                    # Re-submit the form
                    if submit_button and submit_button != 'form':
                        driver.click(submit_button)
                    else:
                        driver.run_js("""
                        var form = document.querySelector('form');
                        if (form) { form.submit(); return true; }
                        return false;
                        """)
                else:
                    # If we've been waiting more than 30 seconds and seem to be on a post-login page
                    if login_wait_time > 30 and not current_url.endswith('/login') and not current_url.endswith('/'):
                        print("⚠️ CAPTCHA detection issue but login may have succeeded - continuing workflow")
                        login_success = True
                        break
                    else:
                        print("❌ Failed to handle CAPTCHA during login")
                        driver.save_screenshot("screenshots/login_captcha_failed.png")
                        return {"error": "Failed to handle CAPTCHA during login"}
            
            time.sleep(poll_interval)
            login_wait_time += poll_interval
            print(f"⏳ Waiting for login response... {login_wait_time}/{login_timeout}s")
        
        if not login_success:
            print("❌ Login timed out")
            driver.save_screenshot("screenshots/login_timeout.png")
            return {"error": "Login timed out"}
        
        print("✅ Login process complete")
        return {"success": True}
        
    except Exception as e:
        print(f"❌ Login error: {e}")
        driver.save_screenshot("screenshots/login_error.png")
        return {"error": f"Login error: {str(e)}"}

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
            # Take screenshot before looking for the button
            driver.save_screenshot("screenshots/before_choose_property.png")
            print("📸 Saved screenshot: screenshots/before_choose_property.png")
            
            # First check if we can find the button with CSS selector
            property_btn_selectors = ["#choosePropertyBtn", ".choosePropertyBtn", "button:contains('Choose Property')", "a.btn-primary", "button.btn-primary"]
            
            property_btn_found = False
            chosen_selector = None
            
            for selector in property_btn_selectors:
                if driver.is_element_present(selector):
                    print(f"✅ Found Choose Property button with selector: {selector}")
                    chosen_selector = selector
                    property_btn_found = True
                    break
            
            # If not found via CSS, try JavaScript approach
            if not property_btn_found:
                print("🔍 Choose Property button not found with CSS selectors, trying JavaScript...")
                find_btn_script = """
                var buttons = document.querySelectorAll('button, a.btn, .btn, a[class*="btn"]');
                for (var i = 0; i < buttons.length; i++) {
                    var text = buttons[i].textContent || '';
                    if (text.includes('Choose Property') || text.includes('Select Property') || 
                        text.includes('Property') || text.includes('Select Meter') || text.includes('Choose')) {
                        return buttons[i].outerHTML;
                    }
                }
                return '';
                """
                btn_html = driver.run_js(find_btn_script)
                
                if btn_html:
                    print(f"✅ Found button via JavaScript: {btn_html[:50]}...")
                    click_script = """
                    var buttons = document.querySelectorAll('button, a.btn, .btn, a[class*="btn"]');
                    for (var i = 0; i < buttons.length; i++) {
                        var text = buttons[i].textContent || '';
                        if (text.includes('Choose Property') || text.includes('Select Property') || 
                            text.includes('Property') || text.includes('Select Meter') || text.includes('Choose')) {
                            buttons[i].click();
                            return true;
                        }
                    }
                    return false;
                    """
                    if driver.run_js(click_script):
                        print("✅ Clicked Choose Property button via JavaScript")
                        property_btn_found = True
            
            # If found via CSS selector, click with mouse movement
            if property_btn_found and chosen_selector:
                # Add a slight delay before clicking
                time.sleep(random.uniform(1.5, 2.5))
                
                # Try with human-like mouse movement
                human_like_mouse_movement(driver, chosen_selector)
                time.sleep(random.uniform(0.8, 1.2))
                
                driver.click(chosen_selector)
                print("✅ Clicked Choose Property button")
            
            # Wait longer after clicking the button
            print("⏳ Waiting for property selection page to load...")
            time.sleep(5)
            
            # Take screenshot after clicking
            driver.save_screenshot("screenshots/after_choose_property.png")
            print("📸 Saved screenshot: screenshots/after_choose_property.png")
            
            # If we still haven't clicked successfully
            if not property_btn_found:
                print("❌ Choose Property button not found with any method")
                driver.save_screenshot("screenshots/choose_property_not_found.png")
                return {"error": "Choose Property button not found"}
            
        except Exception as e:
            print(f"❌ Error with Choose Property: {e}")
            driver.save_screenshot(f"screenshots/chooseProperty_error_{int(time.time())}.png")
            # Continue anyway, as we might already be on the right page
            print("⚠️ Continuing despite property selection error...")
        
        # Step 8: Select "All Meters" from the property selection
        print("⚡ Looking for All Meters option using sequential approach...")
        
        # Take screenshot to see what page we're on
        driver.save_screenshot("screenshots/before_meters_selection.png")
        print("📸 Saved screenshot: screenshots/before_meters_selection.png")
        
        try:
            # Wait for the page to be fully loaded
            time.sleep(3)
            
            # Step 1: Look for a search box and try to search for "All Meters"
            search_script = """
            var searchInputs = document.querySelectorAll('input[type="search"], input[placeholder*="search"], input[placeholder*="filter"], .search-input');
            if (searchInputs.length > 0) {
                var searchInput = searchInputs[0];
                searchInput.value = "All Meters";
                searchInput.dispatchEvent(new Event('input', { bubbles: true }));
                searchInput.dispatchEvent(new Event('change', { bubbles: true }));
                return {found: true, element: searchInput.outerHTML};
            }
            return {found: false};
            """
            
            search_result = driver.run_js(search_script)
            if search_result and search_result.get('found', False):
                print(f"✅ Found and filled search input: {search_result.get('element', '')[:50]}...")
                time.sleep(1.5)
            
            # Step 2: Try to click a clearly visible "All Meters" option with simple direct approach
            print("🔍 Looking for visible All Meters option...")
            
            simple_all_meters_script = """
            function findAllMetersElement() {
                var allTexts = [];
                var elements = document.querySelectorAll('*');
                var allMetersElements = [];
                
                for (var i = 0; i < elements.length; i++) {
                    var el = elements[i];
                    if (!el || !el.textContent) continue;
                    
                    var text = el.textContent.trim();
                    if (text === "All Meters" || text === "All meters" || text === "ALL METERS") {
                        // Check if element is visible
                        if (el.offsetParent !== null && 
                            el.style.display !== 'none' && 
                            el.style.visibility !== 'hidden') {
                            
                            allMetersElements.push({
                                element: el,
                                html: el.outerHTML.substring(0, 100),
                                isClickable: (el.tagName === 'A' || 
                                              el.tagName === 'BUTTON' || 
                                              el.onclick !== null || 
                                              el.parentElement.onclick !== null)
                            });
                        }
                    }
                }
                
                // If found, return the most clickable element
                if (allMetersElements.length > 0) {
                    // Prefer clickable elements first
                    var clickable = allMetersElements.filter(e => e.isClickable);
                    var target = clickable.length > 0 ? clickable[0].element : allMetersElements[0].element;
                    target.click();
                    return {
                        clicked: true,
                        html: target.outerHTML.substring(0, 100)
                    };
                }
                
                return {clicked: false};
            }
            
            return findAllMetersElement();
            """
            
            direct_result = driver.run_js(simple_all_meters_script)
            all_meters_found = False
            
            if direct_result and direct_result.get('clicked', False):
                print(f"✅ Directly clicked All Meters element: {direct_result.get('html', '')[:50]}...")
                time.sleep(2)  # Wait after click
                driver.save_screenshot("screenshots/after_direct_meters_click.png")
                all_meters_found = True
            
            # Step 3: If direct approach failed, try clicking on list items with meter or all text
            if not all_meters_found:
                print("🔍 Direct approach failed, trying to find list items or select options...")
                
                list_items_script = """
                // Try to find list items, select options, or links with meter-related text
                var candidates = [];
                
                // Look for select elements with "all meters" option
                var selects = document.querySelectorAll('select');
                for (var i = 0; i < selects.length; i++) {
                    var select = selects[i];
                    for (var j = 0; j < select.options.length; j++) {
                        var option = select.options[j];
                        var text = option.textContent.toLowerCase().trim();
                        if (text.includes('all') && (text.includes('meter') || j === 0)) {
                            candidates.push({
                                element: option,
                                select: select,
                                type: 'option',
                                text: text,
                                score: text === 'all meters' ? 10 : (text.includes('meter') ? 5 : 1)
                            });
                        }
                    }
                }
                
                // Look for list items with "all" in them
                var items = document.querySelectorAll('li, a, div[role="option"], .dropdown-item');
                for (var k = 0; k < items.length; k++) {
                    var item = items[k];
                    if (item.offsetParent === null) continue; // Skip if not visible
                    
                    var itemText = item.textContent.toLowerCase().trim();
                    if ((itemText.includes('all') && (itemText.includes('meter') || itemText === 'all')) ||
                        (itemText === 'all')) {
                        candidates.push({
                            element: item,
                            type: 'item',
                            text: itemText,
                            score: itemText === 'all meters' ? 10 : 
                                  (itemText.includes('meter') ? 5 : 
                                  (itemText === 'all' ? 3 : 1))
                        });
                    }
                }
                
                // Sort by score (highest first)
                candidates.sort(function(a, b) { return b.score - a.score; });
                
                // Try to click the best candidate
                if (candidates.length > 0) {
                    var bestCandidate = candidates[0];
                    console.log('Best candidate:', bestCandidate.text, bestCandidate.score, bestCandidate.type);
                    
                    if (bestCandidate.type === 'option') {
                        bestCandidate.select.value = bestCandidate.element.value;
                        bestCandidate.select.dispatchEvent(new Event('change', { bubbles: true }));
                        return { clicked: true, type: 'select', text: bestCandidate.text };
                    } else {
                        bestCandidate.element.click();
                        return { clicked: true, type: 'item', text: bestCandidate.text };
                    }
                }
                
                return { clicked: false };
            """
            
            list_result = driver.run_js(list_items_script)
            if list_result and list_result.get('clicked', False):
                print(f"✅ Clicked on {list_result.get('type', 'element')} with text: {list_result.get('text', '')}")
                time.sleep(2)
                driver.save_screenshot("screenshots/after_list_item_click.png")
                all_meters_found = True
            
            # Step 4: Final attempt - try setting focus on a table and pressing keyboard shortcut
            if not all_meters_found:
                print("🔍 Trying keyboard shortcut approach...")
                
                keyboard_script = """
                // Try to focus on any tables or lists first
                var tables = document.querySelectorAll('table, ul, select, [role="listbox"], [role="grid"]');
                var focused = false;
                
                // Try to focus on a table or list element
                for (var i = 0; i < tables.length; i++) {
                    try {
                        tables[i].focus();
                        focused = true;
                        break;
                    } catch (e) { /* continue */ }
                }
                
                // If we found something to focus on, try pressing HOME key (often selects first element)
                if (focused) {
                    // Create a keyboard event for HOME key
                    var homeEvent = new KeyboardEvent('keydown', {
                        key: 'Home',
                        code: 'Home',
                        keyCode: 36,
                        which: 36,
                        bubbles: true
                    });
                    
                    document.activeElement.dispatchEvent(homeEvent);
                    
                    // Click the first visible option synchronously
                    var firstOptions = document.querySelectorAll('tr:first-child, li:first-child, option:first-child');
                    for (var j = 0; j < firstOptions.length; j++) {
                        if (firstOptions[j].offsetParent !== null) {
                            firstOptions[j].click();
                            break;
                        }
                    }
                    
                    return {pressed: true};
                }
                
                return {pressed: false};
                """
                
                keyboard_result = driver.run_js(keyboard_script)
                if keyboard_result and keyboard_result.get('pressed', False):
                    print("✅ Used keyboard navigation to select first item (likely All Meters)")
                    time.sleep(2)
                    driver.save_screenshot("screenshots/after_keyboard_selection.png")
                    all_meters_found = True
            
            # Step 5: Last resort - assume we're already on the right page or try to click generic buttons
            if not all_meters_found:
                print("🔍 Trying generic selection buttons as last resort...")
                
                generic_buttons_script = """
                // Try clicking any buttons that look like "Select", "Choose", "Continue", etc.
                var buttonLabels = ['select', 'choose', 'continue', 'next', 'submit', 'apply'];
                var buttons = document.querySelectorAll('button, input[type="button"], a.btn, [role="button"]');
                
                for (var i = 0; i < buttons.length; i++) {
                    var btn = buttons[i];
                    if (btn.offsetParent === null) continue; // Skip if not visible
                    
                    var text = (btn.textContent || '').toLowerCase().trim();
                    for (var j = 0; j < buttonLabels.length; j++) {
                        if (text.includes(buttonLabels[j])) {
                            btn.click();
                            return {clicked: true, text: text};
                        }
                    }
                }
                
                // Last resort - try clicking anything that looks clickable
                var clickables = document.querySelectorAll('a, button, [role="button"], [onclick]');
                for (var k = 0; k < Math.min(clickables.length, 5); k++) { // Try first 5 only
                    if (clickables[k].offsetParent !== null) {
                        clickables[k].click();
                        return {clicked: true, text: clickables[k].textContent || 'unknown button'};
                    }
                }
                
                return {clicked: false};
                """
                
                generic_result = driver.run_js(generic_buttons_script)
                if generic_result and generic_result.get('clicked', False):
                    print(f"✅ Clicked on generic button: {generic_result.get('text', 'unknown')}")
                    time.sleep(2)
                    driver.save_screenshot("screenshots/after_generic_button.png")
                    all_meters_found = True
            
            # Step 6: Final attempt - try the generic "Choose" button if visible
            if not all_meters_found:
                print("🔍 Trying generic 'Choose' button as last resort...")
                
                final_attempt = driver.run_js("""
                var buttons = document.querySelectorAll('button, a.btn, input[type="button"], div[role="button"]');
                for (var i = 0; i < buttons.length; i++) {
                    var btn = buttons[i];
                    if (btn.offsetParent !== null) { // Check if visible
                        var text = btn.textContent.toLowerCase();
                        if (text.includes('choose') || text.includes('select') || text.includes('continue') || text.includes('next')) {
                            btn.click();
                            return {clicked: true, text: btn.textContent};
                        }
                    }
                }
                return {clicked: false};
                """)
                
                if final_attempt and final_attempt.get('clicked', False):
                    print(f"✅ Clicked on generic button as last resort: {final_attempt.get('text', '')}")
                    all_meters_found = True
            
            # Take a screenshot after the meter selection attempt
            driver.save_screenshot("screenshots/after_meters_selection.png")
            print("📸 Saved screenshot: screenshots/after_meters_selection.png")
            
            # Wait a moment for any page transitions after meter selection
            time.sleep(3)
            
            if not all_meters_found:
                print("⚠️ Could not find meters selection, but continuing workflow...")
                # Continue anyway - we might already be on the right page
        
        except Exception as e:
            print(f"⚠️ Error during meter selection: {e}")
            driver.save_screenshot("screenshots/meter_selection_error.png")
            print("📸 Error screenshot saved: screenshots/meter_selection_error.png")
            # Continue anyway - we might be able to proceed
        
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
        
        # Step 11: Set Date Range - Floating 2-week period from today back
        print("📅 Setting date range for 2-week period...")
        try:
            from datetime import datetime, timedelta
            
            # Take screenshot before setting date range
            driver.save_screenshot("screenshots/before_date_setting.png")
            print("📸 Saved screenshot before setting date range")
            
            # Use actual current date instead of hardcoded value
            today = datetime.now()
            two_weeks_ago = today - timedelta(days=14)
            
            # Format dates in multiple formats to try
            start_iso = two_weeks_ago.strftime('%Y-%m-%d')  # YYYY-MM-DD
            end_iso = today.strftime('%Y-%m-%d')
            
            start_mdy = two_weeks_ago.strftime('%m/%d/%Y')  # MM/DD/YYYY
            end_mdy = today.strftime('%m/%d/%Y')
            
            print(f"📆 Setting date range: {start_mdy} to {end_mdy} (2-week period)")
            
            # Simple focused script to find and set date inputs
            date_script = f"""
            // Get date input elements by common selector patterns
            var startDateInputs = [
                document.querySelector('#StartDateView'),
                document.querySelector('[name="StartDateView"]'),
                document.querySelector('input[id*="start"]'),
                document.querySelector('input[name*="start"]'),
                document.querySelector('input[placeholder*="Start"]'),
                document.querySelector('input.date-picker:first-of-type'),
                document.querySelector('input[type="date"]:first-of-type')
            ].filter(Boolean);
            
            var endDateInputs = [
                document.querySelector('#EndDateView'),
                document.querySelector('[name="EndDateView"]'),
                document.querySelector('input[id*="end"]'),
                document.querySelector('input[name*="end"]'),
                document.querySelector('input[placeholder*="End"]'),
                document.querySelector('input.date-picker:nth-of-type(2)'),
                document.querySelector('input[type="date"]:nth-of-type(2)')
            ].filter(Boolean);
            
            // Try to identify the best inputs
            var startInput = startDateInputs.length > 0 ? startDateInputs[0] : null;
            var endInput = endDateInputs.length > 0 ? endDateInputs[0] : null;
            
            // If we couldn't find specifically labeled inputs, try to find any date inputs
            if (!startInput || !endInput) {{
                var dateInputs = document.querySelectorAll('input[type="date"], input.date-picker, input[id*="date"], input[name*="date"]');
                if (dateInputs.length >= 2) {{
                    // Assume first is start, second is end
                    startInput = startInput || dateInputs[0];
                    endInput = endInput || dateInputs[1];
                }}
            }}
            
            // Try setting values with different date formats
            var setStart = false;
            var setEnd = false;
            var startFormats = ['{start_iso}', '{start_mdy}'];
            var endFormats = ['{end_iso}', '{end_mdy}'];
            
            // Try to set start date
            if (startInput) {{
                for (var i = 0; i < startFormats.length; i++) {{
                    try {{
                        startInput.value = startFormats[i];
                        startInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        startInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        setStart = true;
                        break;
                    }} catch (e) {{}}
                }}
            }}
            
            // Try to set end date
            if (endInput) {{
                for (var i = 0; i < endFormats.length; i++) {{
                    try {{
                        endInput.value = endFormats[i];
                        endInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        endInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        setEnd = true;
                        break;
                    }} catch (e) {{}}
                }}
            }}
            
            return {{
                startSet: setStart,
                endSet: setEnd,
                startValue: startInput ? startInput.value : null,
                endValue: endInput ? endInput.value : null,
                startId: startInput ? (startInput.id || startInput.name || 'unknown') : null,
                endId: endInput ? (endInput.id || endInput.name || 'unknown') : null,
                numStartInputs: startDateInputs.length,
                numEndInputs: endDateInputs.length
            }};
            """
            
            # Execute the date setting script
            date_result = driver.run_js(date_script)
            
            if date_result:
                if date_result.get('startSet') and date_result.get('endSet'):
                    print(f"✅ Successfully set date range: {date_result.get('startValue')} to {date_result.get('endValue')}")
                elif date_result.get('startSet'):
                    print(f"✅ Set start date ({date_result.get('startValue')}) but couldn't set end date")
                    # Try a fallback for end date if needed
                elif date_result.get('endSet'):
                    print(f"✅ Set end date ({date_result.get('endValue')}) but couldn't set start date")
                    # Try a fallback for start date if needed
                else:
                    print(f"⚠️ Failed to set date range inputs (found {date_result.get('numStartInputs')} start inputs, {date_result.get('numEndInputs')} end inputs)")
                    # Fallback approach if both failed
                    # Try to use tab navigation or other approach
            else:
                print("⚠️ Date range setting script returned no result")
            
            # Click the search or apply button after setting dates
            button_script = """
            // Try to find and click the search/apply button
            var buttonLabels = ['search', 'apply', 'submit', 'go', 'run', 'update', 'continue'];
            var buttons = document.querySelectorAll('button, input[type="submit"], input[type="button"], a.btn');
            
            for (var i = 0; i < buttons.length; i++) {
                var button = buttons[i];
                if (button.offsetParent === null) continue; // Skip if not visible
                
                var buttonText = (button.textContent || button.value || '').toLowerCase();
                for (var j = 0; j < buttonLabels.length; j++) {
                    if (buttonText.includes(buttonLabels[j])) {
                        button.click();
                        return { clicked: true, text: buttonText };
                    }
                }
            }
            
            return { clicked: false };
            """
            
            # Execute the button click script
            button_result = driver.run_js(button_script)
            if button_result and button_result.get('clicked'):
                print(f"✅ Clicked on button: {button_result.get('text')}")
            
            driver.save_screenshot("screenshots/after_date_setting.png")
            print("📸 Saved screenshot after setting date range")
            
            time.sleep(2)  # Wait for any page updates
            
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
                        continue
                        
                    current_files = os.listdir(search_dir)
                    dir_name = "local" if search_dir == downloads_dir else "system"
                    print(f"📂 Polling {dir_name} downloads directory ({search_dir}). Files found: {', '.join(current_files) if current_files else 'None'}")
                    
                    # Look for CSV files, prioritizing recent usage files
                    csv_files = [f for f in current_files if f.endswith('.csv')]
                    usage_csv_files = [f for f in csv_files if 'usage' in f.lower()]
                    
                    target_file = None
                    if usage_csv_files:
                        # Sort by modification time, get most recent
                        usage_files_with_time = [(f, os.path.getmtime(os.path.join(search_dir, f))) for f in usage_csv_files]
                        usage_files_with_time.sort(key=lambda x: x[1], reverse=True)
                        target_file = usage_files_with_time[0][0]
                    elif csv_files:
                        # Fallback to any CSV file
                        csv_files_with_time = [(f, os.path.getmtime(os.path.join(search_dir, f))) for f in csv_files]
                        csv_files_with_time.sort(key=lambda x: x[1], reverse=True)
                        target_file = csv_files_with_time[0][0]
                    
                    if target_file:
                        downloaded_file = os.path.join(search_dir, target_file)
                        print(f"✅ CSV file detected: {downloaded_file}")
                        break
                
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
            with open(downloaded_file, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                headers = csv_reader.fieldnames
                print(f"📊 CSV headers: {headers}")
                
                # Normalize headers to make field access more robust
                normalized_headers = {}
                if headers:
                    for header in headers:
                        normalized_headers[header.strip().lower()] = header
                
                # Parse CSV rows
                for row_num, row in enumerate(csv_reader):
                    if row_num < 5:  # Show first 5 rows for debugging
                        print(f"  Row {row_num + 1}: {dict(row)}")
                    
                    # Store original row format for backup
                    csv_data.append(dict(row))
                    
                    # Now create a properly formatted record for Supabase that matches the table structure
                    try:
                        # Handle date parsing - preserve full datetime for multiple readings per day
                        start_date = None
                        start_date_str = row.get('Start', '')
                        
                        if start_date_str:
                            try:
                                # Try to parse full datetime (MM/DD/YYYY HH:MM:SS AM/PM)
                                # This format preserves the hour which is essential for hourly readings
                                start_date = datetime.strptime(start_date_str, '%m/%d/%Y %I:%M:%S %p')
                                if row_num < 2:  # Log example of successful full datetime parsing
                                    print(f"✓ Parsed full datetime: {start_date_str} -> {start_date.isoformat()}")
                            except ValueError:
                                try:
                                    # Fallback to date only - but note this loses hourly precision
                                    start_date = datetime.strptime(start_date_str, '%m/%d/%Y')
                                    if row_num < 2:
                                        print(f"⚠️ Limited precision date parsing: {start_date_str} -> {start_date.isoformat()}")
                                except ValueError:
                                    print(f"⚠️ Could not parse date: {start_date_str}")
                        
                        # Handle numeric values
                        ccf_value = None
                        if 'CCF' in row and row['CCF'].strip():
                            try:
                                ccf_value = float(row['CCF'].replace('$', '').replace(',', ''))
                            except (ValueError, TypeError):
                                pass
                        
                        # Amount/cost parsing
                        amount_str = row.get('$', '')
                        amount_numeric = None
                        if amount_str and isinstance(amount_str, str):
                            # Remove $ and commas, then convert to float
                            amount_str = amount_str.replace('$', '').replace(',', '')
                            try:
                                amount_numeric = float(amount_str)
                            except (ValueError, TypeError):
                                pass
                        
                        # Create record matching exactly the Supabase "Meter Readings" table structure
                        # Note: Don't include 'amount_numeric' as it's a generated column in the database
                        meter_reading = {
                            'Start': start_date.isoformat() if start_date else None,
                            'Account Number': row.get('Account Number', ''),
                            'Name': row.get('Name', ''),
                            'Meter': row.get('Meter', ''),
                            'Location': int(row.get('Location', 0)) if row.get('Location', '').isdigit() else None,
                            'Address': row.get('Address', ''),
                            'Estimated Indicator': row.get('Estimated Indicator', ''),
                            'CCF': ccf_value,
                            '$': row.get('$', ''),
                            'Usage': ccf_value  # Use CCF as Usage
                        }
                        
                        # Only add records that have the minimum required fields
                        if meter_reading['Start'] and meter_reading['Account Number'] and meter_reading['Meter']:
                            parsed_usage_data.append(meter_reading)
                        
                    except Exception as e:
                        print(f"⚠️ Error parsing row {row_num}: {e}")
                
                print(f"📈 Parsed {len(parsed_usage_data)} usage records")
                    
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            csv_data = [f"Error reading CSV: {str(e)}"]
            parsed_usage_data = []
        
        # Step 16: Upload data to Supabase
        supabase_upload_success = False
        if supabase and parsed_usage_data:
            try:
                print(f"☁️ Uploading {len(parsed_usage_data)} records to 'Meter Readings' table")
                
                # Check if we're using the service key or anon key
                key_type = "ANON KEY" if "anon" in os.environ.get('SUPABASE_ANON_KEY', '').lower() else "SERVICE KEY"
                print(f"🔑 Using Supabase {key_type} for authentication")
                
                # Print first record for debugging (redact sensitive data)
                if parsed_usage_data:
                    sample_record = parsed_usage_data[0].copy()
                    # Redact any sensitive data
                    if 'Account Number' in sample_record:
                        sample_record['Account Number'] = sample_record['Account Number'][:4] + '****'
                    print(f"📝 Sample record structure: {sample_record}")
                
                try:
                    # Try using service key if available (bypasses RLS policies)
                    service_key = os.environ.get('SUPABASE_SERVICE_KEY')
                    if service_key:
                        print("🔑 Found SUPABASE_SERVICE_KEY, using it for upload (bypasses RLS)")
                        # Create a new client with the service key
                        service_client = create_client(os.environ.get('SUPABASE_URL'), service_key)
                        result = service_client.table('Meter Readings').upsert(parsed_usage_data).execute()
                    else:
                        # Fall back to regular key
                        result = supabase.table('Meter Readings').upsert(parsed_usage_data).execute()
                    
                    if result.data:
                        print(f"✅ Successfully uploaded {len(result.data)} records to Supabase")
                    else:
                        print(f"❌ No data returned from Supabase upload")
                        print(f"Full response: {result}")
                        
                except Exception as e:
                    print(f"❌ Failed to upload data to Supabase: {e}")
                    print(f"Error type: {type(e).__name__}")
                    # Print traceback for more detailed error information
                    import traceback
                    print("Detailed error information:")
                    print(traceback.format_exc())
                    
            except Exception as e:
                print(f"❌ Error uploading to Supabase: {e}")
        elif not supabase:
            print("⚠️ Supabase not configured - skipping upload")
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
