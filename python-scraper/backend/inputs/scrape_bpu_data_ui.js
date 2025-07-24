/**
 * @typedef {import('../../frontend/node_modules/botasaurus-controls/dist/index').Controls} Controls
 */

/**
 * @param {Controls} controls
 */
function getInput(controls) {
    controls
        .section("BPU Login Credentials", (section) => {
            section
                .text('username', {
                    label: 'BPU Username',
                    placeholder: 'Enter your BPU username',
                    isRequired: true,
                    helpText: 'Your BPU account username for mymeter.bpu.com'
                })
                .password('password', {
                    label: 'BPU Password',
                    placeholder: 'Enter your BPU password',
                    isRequired: true,
                    helpText: 'Your BPU account password'
                })
        })
        .section("Data Collection Options", (section) => {
            section
                .switch('include_usage_data', {
                    label: "Include Usage Data",
                    defaultValue: true,
                    helpText: "Extract electricity usage and consumption data"
                })
                .switch('include_billing_data', {
                    label: "Include Billing Data",
                    defaultValue: true,
                    helpText: "Extract billing statements and payment information"
                })
                .switch('include_payment_history', {
                    label: "Include Payment History",
                    defaultValue: true,
                    helpText: "Extract historical payment records"
                })
                .switch('include_meter_readings', {
                    label: "Include Meter Readings",
                    defaultValue: true,
                    helpText: "Extract meter reading history"
                })
        })
        .section("Scraping Configuration", (section) => {
            section
                .numberGreaterThanOrEqualToOne('date_range_days', {
                    label: 'Data Range (Days)',
                    defaultValue: 30,
                    placeholder: 30,
                    helpText: 'Number of days of historical data to collect'
                })
                .choose('output_format', {
                    label: "Output Format",
                    defaultValue: 'json',
                    options: [
                        { value: 'json', label: 'JSON' },
                        { value: 'csv', label: 'CSV' },
                        { value: 'excel', label: 'Excel' }
                    ],
                    helpText: 'Choose the format for downloaded data'
                })
        })
        .section("Advanced Options", (section) => {
            section
                .switch('headless_mode', {
                    label: "Headless Mode",
                    defaultValue: true,
                    helpText: "Run browser in background (faster, but no visual feedback)"
                })
                .numberGreaterThanOrEqualToOne('max_retries', {
                    label: 'Max Retries',
                    defaultValue: 3,
                    placeholder: 3,
                    helpText: 'Maximum number of retry attempts on failure'
                })
                .text('captcha_api_key', {
                    label: 'CAPTCHA API Key (Optional)',
                    placeholder: 'Enter your 2captcha API key',
                    helpText: 'API key for automatic CAPTCHA solving (get from 2captcha.com)'
                })
        })
}
