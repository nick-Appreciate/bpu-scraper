#!/usr/bin/env python3
"""
BPU Scraper with Botasaurus UI Interface
Provides a web-based interface for non-technical users
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv
from botasaurus.browser import browser, Driver
from botasaurus_server.server import Server
from bpu_scraper import BPUScraperAdvanced

# Load environment variables
load_dotenv()

class BPUScraperUI(BPUScraperAdvanced):
    """BPU Scraper with UI interface"""
    
    @browser(
        headless=os.getenv('HEADLESS_MODE', 'true').lower() == 'true',
        block_images=True,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        add_arguments=[
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
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
            '--enable-cookies',
            '--allow-running-insecure-content',
            '--disable-site-isolation-trials',
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
        tiny_profile=True,
        profile="bpu_ui_scraper"
    )
    def scrape_bpu_data_ui(self, driver: Driver, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        UI-friendly version of BPU scraper
        Accepts configuration from web interface
        """
        # Override credentials if provided via UI
        global BPU_USERNAME, BPU_PASSWORD
        
        if data.get('username'):
            BPU_USERNAME = data['username']
        if data.get('password'):
            BPU_PASSWORD = data['password']
        
        # Set scraping options from UI
        scraping_options = {
            'include_usage_data': data.get('include_usage_data', True),
            'include_billing_data': data.get('include_billing_data', True),
            'include_payment_history': data.get('include_payment_history', True),
            'include_meter_readings': data.get('include_meter_readings', True),
            'date_range_days': data.get('date_range_days', 30)
        }
        
        print(f"🎯 Scraping with options: {scraping_options}")
        
        # Call the main scraping function
        return self.scrape_bpu_utility_data(driver, scraping_options)

# Create scraper instance
scraper_ui = BPUScraperUI()

# Add the scraper to Botasaurus server
Server.add_scraper(scraper_ui.scrape_bpu_data_ui)

if __name__ == "__main__":
    # Run the UI server
    print("🌐 Starting BPU Scraper UI...")
    print("📱 Access the web interface at: http://localhost:3000")
    print("🔧 Configure your BPU credentials and scraping options")
    print("📊 View results and download data in various formats")
    
    # This will start the Botasaurus web server
    Server.run()
