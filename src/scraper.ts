import puppeteer, { Browser, Page, ElementHandle } from 'puppeteer';
import * as path from 'path';
import * as fs from 'fs/promises';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { config } from 'dotenv';
import { parse } from 'csv-parse/sync'; // For parsing CSV data

// Load environment variables from .env file
config();

const BPU_USERNAME = process.env.BPU_USERNAME;
const BPU_PASSWORD = process.env.BPU_PASSWORD;
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY; // Kept for potential other uses, but service key is primary for this script
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

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

  let browser: Browser | null = null;
  let supabase: SupabaseClient | null = null;

  try {
    // Initialize Supabase client
    supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY!); // Use the service role key
    console.log('Supabase client initialized.');

    // Initialize Puppeteer
    console.log('Launching browser...');
    browser = await puppeteer.launch({
      headless: (process.env.HEADLESS_MODE !== 'false'), // Defaults to true, false if 'false'
      args: [
        '--disable-dev-shm-usage', // Common fix for issues in Docker/CI
        '--no-sandbox',
        '--disable-setuid-sandbox'
      ]
    });
    const page: Page = await browser.newPage();
    console.log('Browser launched and new page created.');

    // --- 1. Login to BPU Portal ---
    console.log('Navigating to BPU login page: https://mymeter.bpu.com/');
    await page.goto('https://mymeter.bpu.com/', { waitUntil: 'networkidle0' });
    console.log('Login page loaded.');

    // Wait for login form elements
    await page.waitForSelector('#LoginEmail', { visible: true });
    await page.waitForSelector('#LoginPassword', { visible: true });
    await page.waitForSelector('button.loginBtn', { visible: true });
    console.log('Login form elements found.');

    // Type credentials
    console.log('Typing username...');
    await page.type('#LoginEmail', BPU_USERNAME!);
    console.log('Typing password...');
    await page.type('#LoginPassword', BPU_PASSWORD!);

    // Click login button and wait for navigation
    console.log('Clicking login button...');
    console.log('Current page URL before login click:', page.url());

    try {
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 90000 }), // Increased timeout, changed to networkidle2
        page.click('button.loginBtn'),
      ]);
      console.log('Login successful, navigated to dashboard/next page.');
      console.log('Current page URL after login and navigation:', page.url());
      const postLoginScreenshotPath = path.join(__dirname, '..', 'screenshots', `post_login_success_${Date.now()}.png`);
      // Ensure screenshots directory exists
      await fs.mkdir(path.dirname(postLoginScreenshotPath), { recursive: true });
      await page.screenshot({ path: postLoginScreenshotPath as `${string}.png`, fullPage: true });
      console.log(`Screenshot after successful login saved to ${postLoginScreenshotPath}`);

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
      console.error('Error during login click or subsequent navigation:', loginError);
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
      throw loginError; // Re-throw the error to stop the script
    }

    // --- 2. Navigate to Data Section (via Choose Property and All Meters) ---
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
      const screenshotPath = path.join(__dirname, '..', 'screenshots', `chooseProperty_error_${Date.now()}.png`);
      await page.screenshot({ path: screenshotPath as `${string}.png`, fullPage: true });
      console.log(`Screenshot saved to ${screenshotPath}`);
      const pageContent = await page.content();
      console.error('Page HTML at the time of error:\n', pageContent.substring(0, 5000));
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
