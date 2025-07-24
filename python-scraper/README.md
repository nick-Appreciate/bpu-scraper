# BPU Scraper - Python Version with Botasaurus

A powerful Python-based utility scraper for BPU (Board of Public Utilities) using the Botasaurus framework. This scraper provides advanced anti-detection capabilities and can extract comprehensive utility data including usage, billing, and payment information.

## 🚀 Features

- **Advanced Anti-Detection**: Leverages Botasaurus's sophisticated bot detection evasion
- **Human-Like Behavior**: Realistic browsing patterns, typing delays, and mouse movements
- **CAPTCHA Handling**: Automatic CAPTCHA solving with 2captcha integration
- **Web UI Interface**: User-friendly web interface for non-technical users
- **Comprehensive Data Extraction**: Usage data, billing information, payment history, and meter readings
- **Multiple Output Formats**: JSON, CSV, and Excel export options
- **Supabase Integration**: Automatic data storage and management
- **Error Recovery**: Robust error handling with retry mechanisms

## 📋 Prerequisites

- Python 3.8 or higher
- Chrome/Chromium browser
- BPU account credentials
- (Optional) 2captcha API key for CAPTCHA solving
- (Optional) Supabase account for data storage

## 🛠️ Installation

1. **Clone or create the project directory:**
   ```bash
   mkdir bpu-scraper-python
   cd bpu-scraper-python
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Create necessary directories:**
   ```bash
   mkdir -p output screenshots backend/inputs frontend
   ```

## ⚙️ Configuration

Edit the `.env` file with your credentials:

```env
# BPU Login Credentials
BPU_USERNAME=your_username_here
BPU_PASSWORD=your_password_here

# Supabase Configuration (Optional)
SUPABASE_URL=your_supabase_url_here
SUPABASE_SERVICE_KEY=your_supabase_service_key_here

# CAPTCHA Solving (Optional)
CAPTCHA_API_KEY=your_2captcha_api_key_here

# Scraper Configuration
HEADLESS_MODE=true
MAX_RETRIES=3
```

## 🎯 Usage

### Command Line Interface

**Basic scraping:**
```bash
python main.py
```

**Advanced scraping with all features:**
```bash
python bpu_scraper.py
```

### Web UI Interface

**Start the web server:**
```bash
python ui_scraper.py
```

Then open your browser to `http://localhost:3000` to access the user-friendly web interface.

### Features of Web UI:
- **Credential Management**: Secure input for BPU credentials
- **Data Selection**: Choose which data types to extract
- **Configuration Options**: Customize scraping behavior
- **Real-time Progress**: Monitor scraping progress
- **Data Export**: Download results in multiple formats
- **Task Management**: View and manage scraping tasks

## 📊 Data Extraction

The scraper extracts the following data types:

### Account Information
- Account number
- Service address
- Customer name
- Account status
- Service type

### Usage Data
- Daily/monthly consumption
- kWh usage
- Cost per period
- Rate information
- Meter readings

### Billing Data
- Bill dates and due dates
- Amount due
- Payment status
- Billing periods
- Historical statements

### Payment History
- Payment dates
- Payment amounts
- Payment methods
- Confirmation numbers

### Service Alerts
- System notifications
- Service interruptions
- Account alerts

## 🔧 Advanced Features

### Anti-Detection Measures
- **Realistic Browsing Patterns**: Simulates human browsing behavior
- **Variable Timing**: Random delays between actions
- **Mouse Movement Simulation**: Human-like cursor movements
- **Session Establishment**: Multi-step browsing history
- **Advanced Browser Arguments**: 30+ stealth configuration options

### CAPTCHA Handling
- **Automatic Detection**: Identifies various CAPTCHA types
- **2captcha Integration**: Automatic solving with API
- **Manual Fallback**: User intervention when needed
- **Retry Logic**: Multiple attempts with increasing delays

### Error Recovery
- **Comprehensive Logging**: Detailed error tracking
- **Screenshot Capture**: Visual debugging on failures
- **Retry Mechanisms**: Automatic retry with backoff
- **Graceful Degradation**: Continues on non-critical errors

## 🗄️ Database Integration

### Supabase Setup
1. Create a Supabase project
2. Set up the following tables:

```sql
-- Main scraper data table
CREATE TABLE bpu_scraper_data (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    account_info JSONB,
    usage_data JSONB,
    billing_data JSONB,
    meter_readings JSONB,
    payment_history JSONB,
    service_alerts JSONB,
    scrape_status TEXT,
    url TEXT
);

-- Usage data table
CREATE TABLE bpu_usage_data (
    id SERIAL PRIMARY KEY,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    date TEXT,
    usage_kwh TEXT,
    cost TEXT,
    rate TEXT,
    meter_reading TEXT
);

-- Billing data table
CREATE TABLE bpu_billing_data (
    id SERIAL PRIMARY KEY,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    bill_date TEXT,
    due_date TEXT,
    amount_due TEXT,
    status TEXT,
    bill_period TEXT
);
```

## 🚨 Troubleshooting

### Common Issues

**Login Failures:**
- Verify BPU credentials in `.env` file
- Check for CAPTCHA challenges
- Ensure cookies are enabled

**CAPTCHA Problems:**
- Set up 2captcha API key
- Ensure sufficient account balance
- Try manual mode for testing

**Data Extraction Issues:**
- Check BPU website structure changes
- Review element selectors
- Enable debug mode for detailed logs

**Performance Issues:**
- Adjust retry settings
- Use headless mode
- Optimize browser arguments

### Debug Mode
Enable detailed logging:
```bash
export DEBUG=true
python bpu_scraper.py
```

### Screenshots
Error screenshots are automatically saved to `screenshots/` directory for debugging.

## 📈 Performance Optimization

### Speed Improvements
- **Image Blocking**: Reduces bandwidth by 90%+
- **CSS Blocking**: Faster page loads
- **Parallel Processing**: Multiple concurrent scrapers
- **Caching**: Reduces redundant requests

### Resource Management
- **Memory Optimization**: Efficient browser management
- **Connection Pooling**: Reuse browser instances
- **Cleanup**: Automatic resource cleanup

## 🔒 Security Considerations

- **Credential Protection**: Environment variable storage
- **Session Management**: Secure cookie handling
- **Rate Limiting**: Respectful request timing
- **Error Sanitization**: No sensitive data in logs

## 📝 API Integration

The web UI provides REST API endpoints for integration:

```bash
# Start scraping task
POST /api/scrape
{
    "username": "your_username",
    "password": "your_password",
    "include_usage_data": true,
    "include_billing_data": true
}

# Get task status
GET /api/task/{task_id}

# Download results
GET /api/download/{task_id}?format=json
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is for educational and personal use only. Please respect BPU's terms of service and use responsibly.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review error logs and screenshots
3. Ensure all dependencies are installed
4. Verify configuration settings

## 🔄 Migration from TypeScript Version

This Python version provides equivalent functionality to the original TypeScript scraper with these improvements:

- **Better Anti-Detection**: Botasaurus's advanced evasion techniques
- **Easier Maintenance**: Python's simplicity and readability
- **Built-in UI**: No separate frontend development needed
- **Enhanced Error Handling**: More robust error recovery
- **Flexible Configuration**: Dynamic settings via web interface

The scraper maintains all the sophisticated anti-detection measures from the original while providing a more user-friendly experience.
