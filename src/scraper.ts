import puppeteer from 'puppeteer-extra';
import RecaptchaPlugin from 'puppeteer-extra-plugin-recaptcha';
import { Browser, Page, ElementHandle } from 'puppeteer';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import * as fs from 'fs/promises';
import * as path from 'path';
import { config } from 'dotenv';
import { parse } from 'csv-parse/sync'; // For parsing CSV data

// Load environment variables from .env file
config();

const BPU_USERNAME = process.env.BPU_USERNAME;
const BPU_PASSWORD = process.env.BPU_PASSWORD;
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY; // Kept for potential other uses, but service key is primary for this script
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
const CAPTCHA_API_KEY = process.env.CAPTCHA_API_KEY; // 2captcha API key

// Configure puppeteer-extra with recaptcha plugin
if (CAPTCHA_API_KEY) {
  puppeteer.use(
    RecaptchaPlugin({
      provider: {
        id: '2captcha',
        token: CAPTCHA_API_KEY
      },
      visualFeedback: true // colorize reCAPTCHAs (violet = detected, green = solved)
    })
  );
  console.log('CAPTCHA solving plugin configured with 2captcha');
} else {
  console.warn('CAPTCHA_API_KEY not set - CAPTCHA solving will be disabled');
}

/**
 * Handle post-login CAPTCHA challenges that may appear after successful login
 * This includes detecting JSON error responses and various CAPTCHA types
 */
async function handlePostLoginCaptcha(page: Page, captchaApiKey?: string, maxRetries: number = 3): Promise<void> {
  let retryCount = 0;
  
  while (retryCount < maxRetries) {
    try {
      // Enhanced page state debugging
      console.log(`🔍 CAPTCHA Check Attempt ${retryCount + 1}/${maxRetries}`);
      console.log(`Current URL: ${page.url()}`);
      console.log(`Page title: ${await page.title()}`);
      
      // Check for CAPTCHA-related content in the page
      const pageContent = await page.content();
      const pageText = await page.evaluate(() => document.body.textContent || '');
      
      // Enhanced debugging - log page state
      const pageState = await page.evaluate(() => ({
        hasLoginForm: !!document.querySelector('#LoginEmail'),
        hasChoosePropertyBtn: !!document.querySelector('#choosePropertyBtn'),
        hasDashboard: !!document.querySelector('.dashboard'),
        hasRecaptcha: !!document.querySelector('iframe[src*="recaptcha"]'),
        bodyClasses: document.body.className,
        visibleText: document.body.textContent?.substring(0, 200) || ''
      }));
      console.log('📊 Page State:', JSON.stringify(pageState, null, 2));
    
    // Check for JSON error responses indicating CAPTCHA requirement
    if (pageContent.includes('Please provide a valid login captcha') ||
        pageContent.includes('LoginErrorMessage') ||
        pageText.includes('Please provide a valid login captcha')) {
      console.log('🚨 Post-login CAPTCHA challenge detected!');
      console.log('The site is requesting CAPTCHA verification after login.');
      
      // Take a screenshot for debugging
      const captchaScreenshotPath = path.join(__dirname, '..', 'screenshots', `captcha_challenge_${Date.now()}.png`);
      await fs.mkdir(path.dirname(captchaScreenshotPath), { recursive: true });
      await page.screenshot({ path: captchaScreenshotPath as `${string}.png`, fullPage: true });
      console.log(`CAPTCHA challenge screenshot saved to ${captchaScreenshotPath}`);
      
      if (!captchaApiKey) {
        console.error('❌ CAPTCHA_API_KEY not configured. Cannot solve CAPTCHA automatically.');
        console.error('💡 To fix this:');
        console.error('   1. Sign up at https://2captcha.com');
        console.error('   2. Add funds to your account ($3 for 1000 CAPTCHAs)');
        console.error('   3. Get your API key from the dashboard');
        console.error('   4. Add CAPTCHA_API_KEY=your_api_key to your .env file or GitHub secrets');
        throw new Error('CAPTCHA challenge detected but no API key configured for solving');
      }
      
      // Try to navigate back to the main page to trigger CAPTCHA display
      console.log('Attempting to navigate to main page to display CAPTCHA...');
      await page.goto('https://mymeter.bpu.com/', { waitUntil: 'networkidle0' });
      
      // Wait with human-like delay
      await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 2000));
      
      // Look for various CAPTCHA types
      const recaptchaElements = await page.$$('iframe[src*="recaptcha"], div[class*="recaptcha"], div[id*="recaptcha"]');
      const hcaptchaElements = await page.$$('iframe[src*="hcaptcha"], div[class*="hcaptcha"], div[id*="hcaptcha"]');
      const captchaImages = await page.$$('img[src*="captcha"], img[alt*="captcha"], img[title*="captcha"]');
      
      let solvingAttempted = false;
      
      if (recaptchaElements.length > 0) {
        console.log(`Found ${recaptchaElements.length} reCAPTCHA element(s), attempting to solve...`);
        try {
          await page.solveRecaptchas();
          console.log('✅ reCAPTCHA solving completed successfully');
          solvingAttempted = true;
        } catch (solveError: any) {
          console.warn(`⚠️ reCAPTCHA solving failed on attempt ${retryCount + 1}:`, solveError.message);
          if (solveError.message?.includes('ERROR_CAPTCHA_UNSOLVABLE')) {
            console.log('💡 CAPTCHA marked as unsolvable by 2captcha - will retry with fresh page');
            retryCount++;
            if (retryCount < maxRetries) {
              console.log(`🔄 Retrying CAPTCHA solving (${retryCount + 1}/${maxRetries})...`);
              await new Promise(resolve => setTimeout(resolve, 3000 + Math.random() * 2000));
              continue;
            }
          }
          throw solveError;
        }
      } else if (hcaptchaElements.length > 0) {
        console.log(`Found ${hcaptchaElements.length} hCaptcha element(s), attempting to solve...`);
        try {
          await page.solveRecaptchas();
          console.log('✅ hCaptcha solving completed successfully');
          solvingAttempted = true;
        } catch (solveError: any) {
          console.warn(`⚠️ hCaptcha solving failed on attempt ${retryCount + 1}:`, solveError.message);
          if (solveError.message?.includes('ERROR_CAPTCHA_UNSOLVABLE')) {
            retryCount++;
            if (retryCount < maxRetries) {
              console.log(`🔄 Retrying CAPTCHA solving (${retryCount + 1}/${maxRetries})...`);
              await new Promise(resolve => setTimeout(resolve, 3000 + Math.random() * 2000));
              continue;
            }
          }
          throw solveError;
        }
      } else if (captchaImages.length > 0) {
        console.log(`Found ${captchaImages.length} image CAPTCHA(s)`);
        console.warn('Image CAPTCHAs require manual handling or specialized solving services');
      } else {
        console.log('No visible CAPTCHA elements found on the page');
        console.log('The CAPTCHA challenge may be triggered by subsequent actions');
      }
      
      if (solvingAttempted) {
        // Wait for CAPTCHA solution to be processed with human-like delay
        const waitTime = 3000 + Math.random() * 2000;
        console.log(`⏳ Waiting ${Math.round(waitTime/1000)}s for CAPTCHA solution to be processed...`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
      }
      
      // Try to proceed with login again if needed
      console.log('Checking if CAPTCHA was solved successfully...');
      const updatedContent = await page.content();
      if (updatedContent.includes('Please provide a valid login captcha')) {
        console.warn('CAPTCHA challenge may still be present after solving attempt');
        retryCount++;
        if (retryCount < maxRetries) {
          console.log(`🔄 CAPTCHA still present, retrying (${retryCount + 1}/${maxRetries})...`);
          await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 1000));
          continue;
        } else {
          console.error('❌ CAPTCHA still present after maximum retries');
          break;
        }
      } else {
        console.log('✅ CAPTCHA appears to have been resolved successfully');
        break; // Success, exit retry loop
      }
      
    } else {
      // Check for standard reCAPTCHA elements even if no error message
      const recaptchaElements = await page.$$('iframe[src*="recaptcha"], div[class*="recaptcha"], div[id*="recaptcha"]');
      if (recaptchaElements.length > 0 && captchaApiKey) {
        console.log(`Found ${recaptchaElements.length} reCAPTCHA element(s), attempting to solve...`);
        try {
          await page.solveRecaptchas();
          console.log('✅ reCAPTCHA solving completed successfully');
          await new Promise(resolve => setTimeout(resolve, 2000));
          break; // Success, exit retry loop
        } catch (solveError: any) {
          console.warn(`⚠️ reCAPTCHA solving failed:`, solveError.message);
          if (solveError.message?.includes('ERROR_CAPTCHA_UNSOLVABLE')) {
            retryCount++;
            if (retryCount < maxRetries) {
              console.log(`🔄 Retrying reCAPTCHA solving (${retryCount + 1}/${maxRetries})...`);
              await new Promise(resolve => setTimeout(resolve, 3000 + Math.random() * 2000));
              continue;
            }
          }
          throw solveError;
        }
      } else {
        console.log('No CAPTCHA challenges detected on post-login page');
        break; // No CAPTCHA found, exit retry loop
      }
    }
    
    } catch (captchaError) {
      console.warn(`Error during post-login CAPTCHA handling (attempt ${retryCount + 1}):`, captchaError);
      // Take a screenshot for debugging
      try {
        const errorScreenshotPath = path.join(__dirname, '..', 'screenshots', `captcha_error_${Date.now()}.png`);
        await fs.mkdir(path.dirname(errorScreenshotPath), { recursive: true });
        await page.screenshot({ path: errorScreenshotPath as `${string}.png`, fullPage: true });
        console.log(`CAPTCHA error screenshot saved to ${errorScreenshotPath}`);
      } catch (screenshotError) {
        console.warn('Could not take CAPTCHA error screenshot:', screenshotError);
      }
      
      retryCount++;
      if (retryCount < maxRetries) {
        console.log(`🔄 Retrying CAPTCHA handling due to error (${retryCount + 1}/${maxRetries})...`);
        await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 1000));
        continue;
      } else {
        console.warn('❌ Maximum CAPTCHA retry attempts reached, continuing with scraper...');
        break;
      }
    }
  }
}

async function scrapeAndUpload(): Promise<void> {
  console.log('BPU Scraper starting...');

  if (!BPU_USERNAME || !BPU_PASSWORD) {
    console.error('BPU username or password not set in .env file.');
    process.exit(1);
  }
  if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
    console.error('Supabase URL or service_role key (SUPABASE_SERVICE_KEY) not set in .env file. The service role key is required for this script to bypass RLS.');
    process.exit(1);
  }
  if (!CAPTCHA_API_KEY) {
    console.warn('CAPTCHA_API_KEY not set in .env file. CAPTCHA solving will be disabled.');
    console.warn('If you encounter CAPTCHA challenges, get a 2captcha API key from https://2captcha.com');
  }

  let browser: Browser | null = null;
  let supabase: SupabaseClient | null = null;

  try {
    // Initialize Supabase client
    supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY!); // Use the service role key
    console.log('Supabase client initialized.');

    // Initialize Puppeteer with advanced anti-bot detection bypass
    console.log('Launching browser with advanced stealth configuration and anti-bot detection bypass...');
    browser = await puppeteer.launch({
      headless: (process.env.HEADLESS_MODE !== 'false'), // Defaults to true, false if 'false'
      // Use persistent user data directory to maintain session across restarts
      userDataDir: process.env.HEADLESS_MODE !== 'false' ? undefined : './browser-data',
      args: [
        '--disable-dev-shm-usage', // Common fix for issues in Docker/CI
        '--no-sandbox',
        '--disable-setuid-sandbox',
        // ADVANCED: Enhanced stealth and anti-detection arguments
        '--disable-blink-features=AutomationControlled',
        '--disable-features=VizDisplayCompositor,VizServiceDisplay,TranslateUI',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-web-security',
        '--disable-ipc-flooding-protection',
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
        '--disable-component-extensions-with-background-pages',
        // CRITICAL: Advanced cookie and session handling
        '--enable-cookies',
        '--allow-running-insecure-content',
        '--disable-site-isolation-trials',
        // ADVANCED: Additional anti-detection measures
        '--disable-features=VizDisplayCompositor,VizServiceDisplay,AudioServiceOutOfProcess',
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
        // ULTRA-ADVANCED: Additional behavioral anti-detection
        '--disable-client-side-phishing-detection',
        '--disable-component-update',
        '--disable-domain-reliability',
        '--disable-features=TranslateUI,BlinkGenPropertyTrees',
        '--disable-ipc-flooding-protection',
        '--disable-renderer-backgrounding',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-breakpad',
        '--disable-component-extensions-with-background-pages',
        '--disable-extensions-http-throttling',
        '--disable-field-trial-config',
        '--disable-back-forward-cache',
        '--disable-logging',
        '--disable-dev-shm-usage',
        '--force-color-profile=srgb',
        '--disable-translate',
        '--disable-notifications',
        '--disable-permissions-api',
        '--disable-web-security',
        '--allow-running-insecure-content',
        '--ignore-certificate-errors',
        '--ignore-ssl-errors',
        '--ignore-certificate-errors-spki-list',
        '--ignore-certificate-errors-skip-list',
        '--disable-dev-tools',
        '--disable-auto-reload',
        '--no-service-autorun',
        '--disable-component-cloud-policy',
        '--disable-accelerated-mjpeg-decode',
        '--disable-accelerated-video-decode',
        '--disable-gpu-memory-buffer-compositor-resources',
        '--disable-gpu-memory-buffer-video-frames'
      ]
    });
    const page: Page = await browser.newPage();
    
    // ADVANCED: Configure sophisticated anti-detection and browser fingerprinting evasion
    console.log('Configuring advanced anti-detection measures and browser fingerprinting evasion...');
    
    // Set realistic user agent with proper OS/browser matching
    await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    await page.setViewport({ width: 1366, height: 768 });
    
    // CRITICAL: Advanced browser fingerprinting evasion with enhanced anti-detection
    await page.evaluateOnNewDocument(() => {
      // Hide webdriver property completely
      Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
      });
      
      // Enhanced navigator properties for better browser mimicking
      Object.defineProperty(navigator, 'platform', {
        get: () => 'MacIntel',
        configurable: true
      });
      
      Object.defineProperty(navigator, 'vendor', {
        get: () => 'Google Inc.',
        configurable: true
      });
      
      Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
        configurable: true
      });
      
      Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
        configurable: true
      });
      
      // Override navigator.cookieEnabled to ensure it returns true
      Object.defineProperty(navigator, 'cookieEnabled', {
        get: () => true,
        configurable: true
      });
      
      // More realistic plugins array
      Object.defineProperty(navigator, 'plugins', {
        get: () => ({
          length: 3,
          0: { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
          1: { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
          2: { name: 'Native Client', filename: 'internal-nacl-plugin' }
        }),
        configurable: true
      });
      
      Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
        configurable: true
      });
      
      Object.defineProperty(navigator, 'language', {
        get: () => 'en-US',
        configurable: true
      });
      
      // Canvas fingerprinting protection - override toDataURL method
      const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
      HTMLCanvasElement.prototype.toDataURL = function(type?: string, quality?: any): string {
        // Add slight randomization to canvas output to prevent fingerprinting
        const context = this.getContext('2d') as CanvasRenderingContext2D | null;
        if (context) {
          const imageData = context.getImageData(0, 0, this.width, this.height);
          // Add minimal noise to prevent exact fingerprinting
          for (let i = 0; i < imageData.data.length; i += 4) {
            if (Math.random() < 0.001) { // Very low probability to avoid visual changes
              imageData.data[i] += Math.floor(Math.random() * 3) - 1;
            }
          }
          context.putImageData(imageData, 0, 0);
        }
        return originalToDataURL.call(this, type, quality);
      };
      
      // WebGL fingerprinting protection
      const getParameter = WebGLRenderingContext.prototype.getParameter;
      WebGLRenderingContext.prototype.getParameter = function(parameter: number) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        if (parameter === 7936) return 'WebKit';
        if (parameter === 7937) return 'WebKit WebGL';
        return getParameter.apply(this, [parameter]);
      };
      
      // Override permissions API to avoid detection
      const originalQuery = window.navigator.permissions.query;
      window.navigator.permissions.query = (parameters: PermissionDescriptor) => (
        parameters.name === 'notifications' ?
          Promise.resolve({ 
            state: Notification.permission,
            name: 'notifications' as PermissionName,
            onchange: null,
            addEventListener: () => {},
            removeEventListener: () => {},
            dispatchEvent: () => false
          } as PermissionStatus) :
          originalQuery(parameters)
      );
      
      // Override chrome runtime to avoid detection
      if ((window as any).chrome) {
        Object.defineProperty((window as any).chrome, 'runtime', {
          get: () => ({
            onConnect: undefined,
            onMessage: undefined,
            sendMessage: undefined,
          }),
          configurable: true
        });
      }
      
      // Override screen properties for consistency
      Object.defineProperty(screen, 'availHeight', {
        get: () => 768,
        configurable: true
      });
      
      Object.defineProperty(screen, 'availWidth', {
        get: () => 1366,
        configurable: true
      });
      
      // Add timezone consistency
      Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', {
        value: function() {
          return {
            locale: 'en-US',
            timeZone: 'America/New_York',
            calendar: 'gregory',
            numberingSystem: 'latn'
          };
        },
        configurable: true
      });
      
      // Initialize localStorage and sessionStorage for session persistence
      try {
        localStorage.setItem('browser_session', 'active');
        localStorage.setItem('session_timestamp', Date.now().toString());
        sessionStorage.setItem('page_loaded', Date.now().toString());
        sessionStorage.setItem('navigation_type', 'navigate');
      } catch (e) {
        // Ignore localStorage errors in some environments
      }
      
      // Override Date.prototype.getTimezoneOffset for consistency
      Date.prototype.getTimezoneOffset = function() {
        return 300; // EST/EDT offset
      };
    });
    
    // CRITICAL: Enhanced cookie handling and session setup with multiple domains
    console.log('Setting up advanced cookie handling and session configuration...');
    
    // Initialize cookies across multiple domain variations for better session persistence
    const cookieDomains = ['.bpu.com', 'mymeter.bpu.com', '.mymeter.bpu.com'];
    for (const domain of cookieDomains) {
      await page.setCookie({
        name: 'session_enabled',
        value: 'true',
        domain: domain,
        httpOnly: false,
        secure: false,
        sameSite: 'Lax'
      });
      
      await page.setCookie({
        name: 'browser_session',
        value: `session_${Date.now()}`,
        domain: domain,
        httpOnly: false,
        secure: false,
        sameSite: 'Lax'
      });
    }
    
    // Set comprehensive HTTP headers mimicking real Chrome browser behavior
    await page.setExtraHTTPHeaders({
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
      'Cache-Control': 'max-age=0',
      'DNT': '1',
      'Connection': 'keep-alive',
      'Upgrade-Insecure-Requests': '1',
      'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
      'Sec-Ch-Ua-Mobile': '?0',
      'Sec-Ch-Ua-Platform': '"macOS"',
      'Sec-Fetch-Dest': 'document',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'same-origin',
      'Sec-Fetch-User': '?1',
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    });
    
    // Add behavioral simulation for human-like interaction patterns
    console.log('Initializing behavioral simulation and human-like interaction patterns...');
    
    // Simulate human-like mouse movements and focus events
    await page.evaluateOnNewDocument(() => {
      // Dispatch realistic browser events
      setTimeout(() => {
        window.dispatchEvent(new Event('focus'));
        document.dispatchEvent(new Event('visibilitychange'));
        
        // Simulate user activity
        const mouseEvent = new MouseEvent('mousemove', {
          bubbles: true,
          cancelable: true,
          clientX: Math.random() * 100 + 50,
          clientY: Math.random() * 100 + 50
        });
        document.dispatchEvent(mouseEvent);
      }, Math.random() * 1000 + 500);
    });
    
    // Add random delays and mouse movements for behavioral realism
    const humanDelay = () => new Promise(resolve => 
      setTimeout(resolve, 1000 + Math.random() * 2000)
    );
    
    // Simulate initial page interaction
    await page.mouse.move(100 + Math.random() * 200, 100 + Math.random() * 200);
    await page.evaluate(() => {
      window.scrollTo(0, Math.random() * 100);
    });
    console.log('Browser launched and new page created.');

    // ULTRA-ADVANCED: Simulate realistic browsing behavior before login
    console.log('🎭 Simulating realistic browsing behavior to bypass behavioral analysis...');
    
    // Step 1: Visit a neutral page first to establish browsing history
    console.log('Establishing browsing history with neutral page visit...');
    await page.goto('https://www.google.com', { waitUntil: 'networkidle0' });
    await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 3000));
    
    // Simulate realistic Google interaction
    await page.mouse.move(200 + Math.random() * 300, 150 + Math.random() * 200);
    await page.evaluate(() => {
      window.scrollTo(0, Math.random() * 200);
      // Simulate realistic user activity
      document.dispatchEvent(new MouseEvent('mousemove', {
        bubbles: true,
        clientX: Math.random() * window.innerWidth,
        clientY: Math.random() * window.innerHeight
      }));
    });
    
    // Step 2: Navigate to BPU main site (not login page directly)
    console.log('Navigating to BPU main site to establish legitimate browsing pattern...');
    await page.goto('https://www.bpu.com/', { waitUntil: 'networkidle0' });
    await new Promise(resolve => setTimeout(resolve, 3000 + Math.random() * 4000));
    
    // Simulate browsing the main site
    await page.mouse.move(300 + Math.random() * 400, 200 + Math.random() * 300);
    await page.evaluate(() => {
      window.scrollTo(0, 100 + Math.random() * 300);
      // Simulate reading behavior with multiple scroll events
      setTimeout(() => window.scrollTo(0, 200 + Math.random() * 200), 1000);
      setTimeout(() => window.scrollTo(0, 300 + Math.random() * 200), 2000);
    });
    
    // Extended delay to simulate human reading time
    await new Promise(resolve => setTimeout(resolve, 5000 + Math.random() * 5000));
    
    // Step 3: Now navigate to login page as a human would
    console.log('🔐 Navigating to BPU login page after establishing browsing pattern...');
    await page.goto('https://mymeter.bpu.com/', { waitUntil: 'networkidle0' });
    
    // Extended delay after page load to simulate human behavior
    await new Promise(resolve => setTimeout(resolve, 3000 + Math.random() * 4000));
    console.log('Login page loaded with realistic browsing simulation.');

    // Wait for login form elements with realistic human-like behavior
    await page.waitForSelector('#LoginEmail', { visible: true });
    await page.waitForSelector('#LoginPassword', { visible: true });
    await page.waitForSelector('button.loginBtn', { visible: true });
    console.log('Login form elements found.');
    
    // ULTRA-ADVANCED: Simulate realistic human interaction patterns
    console.log('🧠 Simulating realistic human interaction patterns...');
    
    // Simulate user examining the page before typing
    await page.mouse.move(400 + Math.random() * 200, 300 + Math.random() * 100);
    await new Promise(resolve => setTimeout(resolve, 1500 + Math.random() * 2000));
    
    // Move mouse to email field area and hover before clicking
    const emailField = await page.$('#LoginEmail');
    if (emailField) {
      const emailBox = await emailField.boundingBox();
      if (emailBox) {
        // Move mouse near the field first
        await page.mouse.move(
          emailBox.x + emailBox.width / 2 + (Math.random() - 0.5) * 20,
          emailBox.y + emailBox.height / 2 + (Math.random() - 0.5) * 10
        );
        await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 1000));
      }
    }
    
    // Click and type username with realistic human patterns
    console.log('Typing username with human-like patterns...');
    await page.click('#LoginEmail');
    await new Promise(resolve => setTimeout(resolve, 200 + Math.random() * 300));
    
    // Type username with variable delays and occasional pauses
    const username = BPU_USERNAME!;
    for (let i = 0; i < username.length; i++) {
      await page.type('#LoginEmail', username[i], { delay: 80 + Math.random() * 120 });
      // Occasional longer pause to simulate thinking
      if (Math.random() < 0.1) {
        await new Promise(resolve => setTimeout(resolve, 300 + Math.random() * 700));
      }
    }
    
    // Pause before moving to password field
    await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 1200));
    
    // Move mouse to password field with realistic movement
    const passwordField = await page.$('#LoginPassword');
    if (passwordField) {
      const passwordBox = await passwordField.boundingBox();
      if (passwordBox) {
        await page.mouse.move(
          passwordBox.x + passwordBox.width / 2 + (Math.random() - 0.5) * 20,
          passwordBox.y + passwordBox.height / 2 + (Math.random() - 0.5) * 10
        );
        await new Promise(resolve => setTimeout(resolve, 300 + Math.random() * 500));
      }
    }
    
    // Click and type password with realistic patterns
    console.log('Typing password with human-like patterns...');
    await page.click('#LoginPassword');
    await new Promise(resolve => setTimeout(resolve, 200 + Math.random() * 400));
    
    // Type password with variable delays
    const password = BPU_PASSWORD!;
    for (let i = 0; i < password.length; i++) {
      await page.type('#LoginPassword', password[i], { delay: 70 + Math.random() * 100 });
      // Occasional pause for complex passwords
      if (Math.random() < 0.08) {
        await new Promise(resolve => setTimeout(resolve, 200 + Math.random() * 500));
      }
    }

    // ULTRA-ADVANCED: Extended human-like delay before login attempt
    console.log('⏳ Simulating human thinking time before login attempt...');
    await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 3000));
    
    // Simulate user reviewing form before submission
    await page.mouse.move(500 + Math.random() * 100, 400 + Math.random() * 100);
    await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 1500));

    // Click login button and wait for navigation
    console.log('Attempting login...');
    console.log('Current page URL before login click:', page.url());

    try {
      // Check if reCAPTCHA is present
      const recaptchaFrame = await page.$('iframe[src*="recaptcha"]');
      if (recaptchaFrame) {
        console.log('reCAPTCHA detected - this may cause login issues in automated environments');
      }

      // Try form submission approach (more reliable than button click)
      await page.evaluate(() => {
        const form = document.querySelector('form') as HTMLFormElement;
        if (form) {
          form.submit();
        } else {
          // Fallback to button click if no form found
          const button = document.querySelector('button.loginBtn') as HTMLButtonElement;
          if (button) {
            button.click();
          }
        }
      });

      // Wait for login success indicators with multiple detection methods
      console.log('Waiting for login success indicators...');
      await page.waitForFunction(
        () => {
          // Check for URL change (most reliable)
          if (window.location.href !== 'https://mymeter.bpu.com/') {
            return true;
          }
          
          // Check for dashboard elements
          if (document.querySelector('#choosePropertyBtn') || 
              document.querySelector('.dashboard') ||
              document.querySelector('[href*="dashboard"]') ||
              document.querySelector('.property-selector') ||
              document.querySelector('#propertySelect')) {
            return true;
          }
          
          // Check if login form disappeared (indicates success)
          const loginForm = document.querySelector('#LoginEmail');
          if (!loginForm || window.getComputedStyle(loginForm).display === 'none') {
            return true;
          }
          
          return false;
        },
        { timeout: 45000 }
      );
      
      console.log('Login successful!');
      console.log('Current page URL after login:', page.url());
      
      // CRITICAL: Debug cookie and session state after login
      console.log('🍪 Debugging cookie and session state after login...');
      const cookies = await page.cookies();
      console.log(`Found ${cookies.length} cookies:`);
      cookies.forEach((cookie, index) => {
        console.log(`  Cookie ${index + 1}: ${cookie.name} = ${cookie.value.substring(0, 50)}${cookie.value.length > 50 ? '...' : ''} (domain: ${cookie.domain})`);
      });
      
      // Check if cookies are enabled in the page context
      const cookieEnabled = await page.evaluate(() => navigator.cookieEnabled);
      console.log(`Navigator.cookieEnabled: ${cookieEnabled}`);
      
      // Check for any cookie-related warnings or errors on the page
      const pageContent = await page.content();
      if (pageContent.includes('enable cookies') || pageContent.includes('cookie') || pageContent.includes('You must enable')) {
        console.warn('⚠️  Page contains cookie-related warnings!');
        const cookieWarnings = await page.evaluate(() => {
          const warnings: string[] = [];
          const elements = document.querySelectorAll('*');
          elements.forEach(el => {
            const text = el.textContent || '';
            if (text.toLowerCase().includes('cookie') || text.toLowerCase().includes('enable cookies')) {
              warnings.push(text.trim());
            }
          });
          return warnings.slice(0, 5); // Limit to first 5 warnings
        });
        console.warn('Cookie-related warnings found:', cookieWarnings);
      }
      
      const postLoginScreenshotPath = path.join(__dirname, '..', 'screenshots', `post_login_success_${Date.now()}.png`);
      // Ensure screenshots directory exists
      await fs.mkdir(path.dirname(postLoginScreenshotPath), { recursive: true });
      await page.screenshot({ path: postLoginScreenshotPath as `${string}.png`, fullPage: true });
      console.log(`Screenshot after successful login saved to ${postLoginScreenshotPath}`);

      // Check for post-login CAPTCHA challenges
      console.log('Checking for post-login CAPTCHA challenges...');
      await handlePostLoginCaptcha(page, CAPTCHA_API_KEY);

      // NEW: Wait for the "Loading Data" page to finish and navigate/update
      if (page.url().includes('/Integration/LoginActions')) {
        console.log('On LoginActions page, waiting for navigation to the actual dashboard...');
        try {
          // This assumes a proper navigation occurs.
          // If it's a client-side update, waitForSelector for a dashboard-specific element is better.
          await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 60000 }); // Wait for the next full navigation
          console.log('Navigated from LoginActions. New URL:', page.url());
        } catch (e) {
          console.warn('Timed out waiting for navigation from LoginActions, will proceed to check for selector. Current URL:', page.url());
          // If waitForNavigation times out, it might be a client-side render.
          // The next waitForSelector will then act as the primary wait.
        }
      }

    } catch (loginError) {
      console.log('Login attempt failed, checking for error messages...');
      
      // Check for actual login error messages (not informational text)
      const errorElements = await page.$$('.alert-danger, .error, .validation-summary-errors, .field-validation-error');
      if (errorElements.length > 0) {
        const errorText = await page.evaluate(() => {
          const errors = document.querySelectorAll('.alert-danger, .error, .validation-summary-errors, .field-validation-error');
          return Array.from(errors)
            .map(el => el.textContent?.trim())
            .filter(Boolean)
            .filter(text => {
              // Filter out informational messages that aren't actual errors
              if (!text) return false;
              const lowerText = text.toLowerCase();
              return !lowerText.includes('remember me') && 
                     !lowerText.includes('keep you logged in') &&
                     !lowerText.includes('public computers');
            });
        });
        
        if (errorText.length > 0) {
          console.error('Actual login error messages found:', errorText);
          throw new Error(`Login failed with errors: ${errorText.join(', ')}`);
        } else {
          console.log('Only informational messages found, not actual errors');
        }
      }
      
      console.error('Error during login attempt:', loginError);
      const loginErrorScreenshotPath = path.join(__dirname, '..', 'screenshots', `login_attempt_error_${Date.now()}.png`);
      // Ensure screenshots directory exists
      await fs.mkdir(path.dirname(loginErrorScreenshotPath), { recursive: true });
      // Attempt to take a screenshot, page might be in a weird state
      try {
        await page.screenshot({ path: loginErrorScreenshotPath as `${string}.png`, fullPage: true });
        console.log(`Screenshot during login error saved to ${loginErrorScreenshotPath}`);
        console.error('Page URL at login error:', page.url());
        console.error('Page HTML at the time of login error:\n', (await page.content()).substring(0, 5000));
      } catch (screenshotError) {
        console.error('Could not take screenshot during login error:', screenshotError);
      }
      throw new Error('Login attempt failed - no navigation or expected elements found');
    }

    // --- 2. Navigate to Data Section (via Choose Property and All Meters) ---
    // Check for and solve any CAPTCHAs before clicking Choose Property
    console.log('Checking for CAPTCHAs before Choose Property click...');
    await handlePostLoginCaptcha(page, CAPTCHA_API_KEY);

    // Click "Choose Property" button
    const choosePropertySelector = 'a#choosePropertyBtn';
    console.log(`Waiting for Choose Property button: ${choosePropertySelector}`);
    try {
      await page.waitForSelector(choosePropertySelector, { visible: true, timeout: 90000 }); // Increased timeout
      console.log('Clicking Choose Property button...');
      await page.click(choosePropertySelector);
      console.log('Clicked "Choose Property". Current URL:', page.url());
    } catch (error) {
      console.error(`Error waiting for or clicking Choose Property button (${choosePropertySelector}):`, error);
      
      // Check for CAPTCHA-related errors and attempt to handle them
      try {
        const pageContent = await page.content();
        const pageText = await page.evaluate(() => document.body.textContent || '');
        
        // Check if this is a CAPTCHA-related error
        if (pageContent.includes('captcha') || pageText.includes('captcha') || 
            pageContent.includes('Please provide a valid login captcha') ||
            pageText.includes('Please provide a valid login captcha') ||
            pageContent.includes('LoginErrorMessage')) {
          console.error('🚨 CAPTCHA challenge detected during Choose Property step!');
          
          // Take a screenshot for debugging
          const screenshotPath = path.join(__dirname, '..', 'screenshots', `chooseProperty_error_${Date.now()}.png`);
          await page.screenshot({ path: screenshotPath as `${string}.png`, fullPage: true });
          console.log(`Screenshot saved to ${screenshotPath}`);
          console.error('Page HTML at the time of error:\n', pageContent.substring(0, 1000));
          
          // Attempt to handle the CAPTCHA challenge
          console.log('Attempting to handle CAPTCHA challenge...');
          await handlePostLoginCaptcha(page, CAPTCHA_API_KEY);
          
          // After CAPTCHA handling, try to wait for the Choose Property button again
          console.log('Retrying Choose Property button after CAPTCHA handling...');
          try {
            await page.waitForSelector(choosePropertySelector, { visible: true, timeout: 30000 });
            console.log('Choose Property button found after CAPTCHA handling, clicking...');
            await page.click(choosePropertySelector);
            console.log('Successfully clicked Choose Property after CAPTCHA handling');
            return; // Success, exit the catch block
          } catch (retryError) {
            console.error('Choose Property button still not available after CAPTCHA handling:', retryError);
          }
        } else {
          // Not a CAPTCHA error, take screenshot for debugging
          const screenshotPath = path.join(__dirname, '..', 'screenshots', `chooseProperty_error_${Date.now()}.png`);
          await page.screenshot({ path: screenshotPath as `${string}.png`, fullPage: true });
          console.log(`Screenshot saved to ${screenshotPath}`);
          console.error('Page HTML at the time of error:\n', pageContent.substring(0, 1000));
        }
      } catch (debugError) {
        console.error('Error during Choose Property error handling:', debugError);
      }
      
      throw error;
    }

    // Click "All Meters"
    const allMetersXPath = "//h2[normalize-space(.)='All Meters']";
    console.log(`Waiting for "All Meters" element (XPath: ${allMetersXPath})`);
    await page.waitForSelector(`xpath/${allMetersXPath}`, { visible: true });
    const allMetersElementHandle = await page.$(`xpath/${allMetersXPath}`);
    if (allMetersElementHandle) {
      console.log('Clicking "All Meters" element...');
      await allMetersElementHandle.click();
      console.log('Clicked "All Meters". Current URL:', page.url());
    } else {
      throw new Error('Could not find "All Meters" element.');
    }

    // --- 3. Navigate to Download Configuration ---
    console.log('Proceeding to click main Data button...');
    const dataButtonSelector = 'span.icon-Data';
    console.log(`Waiting for Data button: ${dataButtonSelector}`);
    await page.waitForSelector(dataButtonSelector, { visible: true, timeout: 60000 });
    console.log('Clicking Data button...');
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 90000 }),
      page.click(dataButtonSelector),
    ]);
    console.log('Clicked "Data" button. Current URL:', page.url());

    // Click the "Download" link/button to go to the download configuration page
    const downloadLinkSelector = 'span.icon-Download.mainButton > a'; // Adjusted selector
    console.log(`Waiting for Download link: ${downloadLinkSelector}`);
    await page.waitForSelector(downloadLinkSelector, { visible: true, timeout: 60000 });
    console.log('Clicking Download link...');
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 90000 }),
      page.click(downloadLinkSelector),
    ]);
    console.log('Clicked "Download" link. Current URL:', page.url());

    // --- 4. Configure Download ---
    // Click "Saved Settings" dropdown
    const savedSettingsDropdownSelector = '#dropdownMenuButton';
    console.log(`Waiting for Saved Settings dropdown: ${savedSettingsDropdownSelector}`);
    await page.waitForSelector(savedSettingsDropdownSelector, { visible: true });
    await page.click(savedSettingsDropdownSelector);
    console.log('Clicked Saved Settings dropdown.');

    // Select "All Water"
    const allWaterOptionSelector = 'a.loadDownloadSavedSetting[data-id="57"]';
    console.log(`Waiting for "All Water" option: ${allWaterOptionSelector}`);
    await page.waitForSelector(allWaterOptionSelector, { visible: true });
    await page.click(allWaterOptionSelector);
    console.log('Selected "All Water". Waiting for settings to apply...');
    await new Promise(resolve => setTimeout(resolve, 5000)); // Wait for any dynamic updates after selection

    // Set Date Range
    const today = new Date();
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(today.getDate() - 7);

    const formatDate = (date: Date) => date.toISOString().split('T')[0]; // YYYY-MM-DD
    const startDateStr = formatDate(oneWeekAgo);
    const endDateStr = formatDate(today);

    console.log(`Setting Start Date to: ${startDateStr}`);
    await page.evaluate((date) => {
      (document.getElementById('DownloadStartDate') as HTMLInputElement).value = date;
    }, startDateStr);

    console.log(`Setting End Date to: ${endDateStr}`);
    await page.evaluate((date) => {
      (document.getElementById('DownloadEndDate') as HTMLInputElement).value = date;
    }, endDateStr);
    console.log('Date range set.');

    // --- 5. Trigger Download ---
    const downloadSubmitButtonSelector = '#downloadSubmit';
    console.log(`Waiting for download submit button: ${downloadSubmitButtonSelector}`);
    await page.waitForSelector(downloadSubmitButtonSelector, { visible: true });

    // Set up download monitoring
    const downloadPath = path.resolve(__dirname, '..', 'downloads');
    await fs.mkdir(downloadPath, { recursive: true });
    console.log(`Configured downloads to be saved in: ${downloadPath}`);
    // Clear any old CSV files in downloads directory
    const files = await fs.readdir(downloadPath);
    for (const file of files as string[]) {
      if (file.endsWith('.csv')) {
        await fs.unlink(path.join(downloadPath, file));
        console.log(`Deleted old CSV: ${file}`);
      }
    }

    // Explicitly set download behavior for the page
    console.log(`Attempting to set download behavior to allow and save to: ${downloadPath}`);
    try {
      const client = await page.target().createCDPSession();
      await client.send('Page.setDownloadBehavior', {
        behavior: 'allow',
        downloadPath: downloadPath,
      });
      console.log('Download behavior set successfully.');
    } catch (cdpError) {
      console.error('Error setting download behavior via CDP:', cdpError);
      // Log and proceed, as the default behavior might still work or other issues might be at play.
    }

    console.log('Clicking download submit button...');
    await page.click(downloadSubmitButtonSelector);
    console.log('Clicked download submit. Taking a screenshot of the page state...');
    const postDownloadClickScreenshotPath = path.join(__dirname, '..', 'screenshots', `post_download_click_${Date.now()}.png`);
    await page.screenshot({ path: postDownloadClickScreenshotPath as `${string}.png`, fullPage: true });
    console.log(`Post-download-click screenshot saved to ${postDownloadClickScreenshotPath}`);

    // Wait for download to complete by checking for a new .csv file
    let downloadedFile = '';
    const downloadTimeout = 90000; // 90 seconds
    const pollInterval = 1000; // 1 second
    let timeWaited = 0;
    while (timeWaited < downloadTimeout) {
      const currentFiles = await fs.readdir(downloadPath);
      console.log(`Polling downloads directory. Files found: ${currentFiles.join(', ') || 'None'}`); // Log current files
      const csvFile = currentFiles.find(file => file.endsWith('.csv'));
      if (csvFile) {
        downloadedFile = path.join(downloadPath, csvFile);
        console.log(`CSV file detected: ${downloadedFile}`);
        break;
      }
      await new Promise(resolve => setTimeout(resolve, pollInterval));
      timeWaited += pollInterval;
    }

    if (!downloadedFile) {
      throw new Error('CSV file download timed out or failed.');
    }

    console.log(`Reading content from ${downloadedFile}...`);
    const csvData = await fs.readFile(downloadedFile, 'utf-8');
    console.log(`Successfully read ${csvData.length} characters from downloaded CSV.`);

    // --- 6. Parse CSV Data ---
    console.log('Parsing CSV data...');
    const records: any[] = parse(csvData, {
      columns: (header: string[]) => {
        console.log('Detected CSV Headers:', header);
        return header.map(h => h.trim()); // Trim header names
      },
      skip_empty_lines: true,
      trim: true,
    });
    console.log(`Parsed ${records.length} records from CSV.`);

    // --- 7. Transform and Prepare Data for Supabase ---
    console.log('Transforming data for Supabase...');
    const dataToUpsert = records.map((record: any) => {
      // Normalize keys (lowercase and trim) for robust access
      const normalizedRecord: {[key: string]: any} = {};
      for (const keyInRecord in record) {
        normalizedRecord[keyInRecord.toLowerCase().trim()] = record[keyInRecord];
      }

      const BPU_ACCOUNT_NUMBER_FALLBACK = process.env.BPU_ACCOUNT_NUMBER;
      const BPU_METER_ID_FALLBACK = process.env.BPU_METER_ID;

      // Extract data using known CSV headers (after normalization)
      const accountNumber = normalizedRecord['account number'] || BPU_ACCOUNT_NUMBER_FALLBACK;
      const meterId = normalizedRecord['meter'] || BPU_METER_ID_FALLBACK;
      const startDateTimeString = normalizedRecord['start'];
      const name = normalizedRecord['name'];
      const location = normalizedRecord['location'];
      const address = normalizedRecord['address'];
      const estimatedIndicator = normalizedRecord['estimated indicator'];
      const ccfValueFromCsv = normalizedRecord['ccf']; // Raw usage string from CSV 'CCF' column
      const costStringFromCsv = normalizedRecord['$']; // Raw cost string from CSV '$' column

      // Validate essential fields for primary key
      if (!accountNumber || !meterId || !startDateTimeString) {
        console.warn(
          `Skipping record due to missing primary key components. ` +
          `Account: ${accountNumber}, Meter: ${meterId}, Start: ${startDateTimeString}. ` +
          `Original record: ${JSON.stringify(record)}`
        );
        return null; // Skip this record
      }

      // Prepare data for Supabase, matching Supabase column names
      const supabaseData = {
        'Start': new Date(startDateTimeString).toISOString(),
        'Account Number': accountNumber,
        'Name': name,
        'Meter': meterId,
        'Location': location,
        'Address': address,
        'Estimated Indicator': estimatedIndicator,
        'CCF': ccfValueFromCsv, // Map raw CSV 'CCF' (usage string) to Supabase 'CCF' (text) column
        '$': costStringFromCsv,   // Map raw CSV '$' (cost string) to Supabase '$' (text) column
        'UOM': 'CCF', // Unit of Measure
        'Usage': ccfValueFromCsv ? parseFloat(ccfValueFromCsv) : null, // Numeric usage to Supabase 'Usage' (numeric) column
        'Cost': costStringFromCsv ? parseFloat(costStringFromCsv.replace('$', '')) : null, // Numeric cost to Supabase 'Cost' (numeric) column
      };
      return supabaseData;
    }).filter(record => record !== null); // Remove null records
    console.log(`Prepared ${dataToUpsert.length} records for upsert.`);

    // --- 8. Upsert Data to Supabase ---
    if (dataToUpsert.length > 0) {
      if (!supabase) {
        throw new Error('Supabase client not initialized before upsert.');
      }
      console.log(`Upserting ${dataToUpsert.length} records to Supabase...`);
      const { data, error: upsertError } = await supabase
        .from('Meter Readings') // Ensure this is your exact table name
        .upsert(dataToUpsert, {
          onConflict: 'Account Number, Meter, Start', 
        });

      if (upsertError) {
        console.error('Error upserting data to Supabase:', upsertError);
      } else {
        console.log('Data upserted successfully to Supabase.');
      }
    } else {
      console.log('No valid data to upsert.');
    }
    console.log('BPU Scraper finished successfully.');
  } finally {
    if (browser) {
      console.log('Closing browser...');
      await browser.close();
    }
  }
}

scrapeAndUpload();
