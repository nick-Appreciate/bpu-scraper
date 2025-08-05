"""
Test script to isolate CSV parsing and Supabase upload functionality
"""
import os
import csv
import json
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
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
        print("✅ Supabase client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase client: {e}")
        supabase = None
else:
    print("⚠️ Supabase URL or key not provided. Skipping Supabase integration.")
    if not supabase_url:
        print("   - SUPABASE_URL is missing")
    if not supabase_anon_key and not supabase_service_key:
        print("   - Both SUPABASE_ANON_KEY and SUPABASE_SERVICE_KEY are missing")
    supabase = None

def find_latest_csv(download_dir="."):
    """Find the latest usage CSV file in the specified directory."""
    try:
        # Look for CSV files in download directory, prioritize files with 'usage' in name
        csv_files = []
        for file in os.listdir(download_dir):
            if file.endswith('.csv'):
                file_path = os.path.join(download_dir, file)
                csv_files.append({
                    'path': file_path,
                    'modified': os.path.getmtime(file_path),
                    'is_usage': 'usage' in file.lower()
                })
        
        # Sort by modified time (newest first) and prioritize 'usage' files
        if csv_files:
            # First sort by modified time
            csv_files.sort(key=lambda x: x['modified'], reverse=True)
            # Then prioritize 'usage' files
            usage_files = [f for f in csv_files if f['is_usage']]
            
            if usage_files:
                return usage_files[0]['path']
            else:
                return csv_files[0]['path']
        else:
            print(f"No CSV files found in {download_dir}")
            return None
    except Exception as e:
        print(f"Error finding CSV file: {e}")
        return None

def test_csv_parsing_and_upload():
    """Test function to parse a CSV file and upload to Supabase."""
    print("\n🧪 Starting CSV parsing and upload test")
    
    # Use the specific CSV file we found
    csv_file = "../downloads/Usage.csv"
    
    if not csv_file:
        print("❌ No CSV file found for testing")
        return False
    
    print(f"📄 Found CSV file: {csv_file}")
    
    # Read and parse CSV data
    csv_data = []
    parsed_records = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            print(f"📖 Reading file contents...")
            
            # First check if the file has content
            file_content = file.read()
            if not file_content.strip():
                print("❌ CSV file is empty!")
                return False
                
            # Reset file pointer to beginning
            file.seek(0)
            
            # Parse CSV
            csv_reader = csv.DictReader(file)
            headers = csv_reader.fieldnames
            
            if not headers:
                print("❌ No headers found in CSV file!")
                return False
                
            print(f"📋 CSV headers: {headers}")
            
            # Normalize headers to make field access more robust
            normalized_headers = {}
            for header in headers:
                normalized_headers[header.strip().lower()] = header
                
            print(f"🔄 Normalized headers: {normalized_headers}")
            
            # Parse rows
            row_count = 0
            error_count = 0
            for row in csv_reader:
                row_count += 1
                csv_data.append(dict(row))
                
                # Print first few rows
                if row_count <= 3:
                    print(f"Row {row_count}: {dict(row)}")
                
                try:
                    # Handle date parsing with full datetime preservation
                    start_date = None
                    start_date_str = row.get('Start', '')
                    
                    if start_date_str:
                        try:
                            # Try full datetime format
                            start_date = datetime.strptime(start_date_str, '%m/%d/%Y %I:%M:%S %p')
                            if row_count <= 3:
                                print(f"✓ Parsed full datetime: {start_date_str} -> {start_date.isoformat()}")
                        except ValueError:
                            try:
                                # Fallback to date only format
                                start_date = datetime.strptime(start_date_str, '%m/%d/%Y')
                                if row_count <= 3:
                                    print(f"⚠️ Limited precision date: {start_date_str} -> {start_date.isoformat()}")
                            except ValueError:
                                print(f"⚠️ Could not parse date: {start_date_str}")
                    
                    # Handle numeric values
                    ccf_value = None
                    if 'CCF' in row and row['CCF'].strip():
                        try:
                            ccf_value = float(row['CCF'].replace('$', '').replace(',', ''))
                        except (ValueError, TypeError):
                            pass
                    
                    # Handle amount/cost
                    amount_str = row.get('$', '')
                    amount_numeric = None
                    if amount_str and isinstance(amount_str, str):
                        amount_str = amount_str.replace('$', '').replace(',', '')
                        try:
                            amount_numeric = float(amount_str)
                        except (ValueError, TypeError):
                            pass
                    
                    # Create record with exact table structure matching
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
                    
                    # Only add records with required fields
                    if meter_reading['Start'] and meter_reading['Account Number'] and meter_reading['Meter']:
                        parsed_records.append(meter_reading)
                    else:
                        missing = []
                        if not meter_reading['Start']: missing.append('Start')
                        if not meter_reading['Account Number']: missing.append('Account Number')
                        if not meter_reading['Meter']: missing.append('Meter')
                        error_count += 1
                        print(f"⚠️ Record {row_count} missing required fields: {', '.join(missing)}")
                        
                except Exception as e:
                    error_count += 1
                    print(f"❌ Error parsing row {row_count}: {e}")
            
            print(f"📊 Processed {row_count} rows with {error_count} errors")
            print(f"📊 Successfully parsed {len(parsed_records)} valid records")
            
            # Show sample of processed data
            if parsed_records:
                print("\n🔎 Sample of processed data:")
                sample = parsed_records[0]
                for key, value in sample.items():
                    print(f"  {key}: {value}")
            
            # Test Supabase upload if we have records and a client
            if supabase and parsed_records:
                print("\n☁️ Testing Supabase upload...")
                
                # Check a single record first
                try:
                    print(f"🧪 Testing upload with a single record first...")
                    test_record = parsed_records[0]
                    test_result = supabase.table('Meter Readings').upsert([test_record]).execute()
                    print(f"✅ Single record test succeeded: {test_result.data}")
                    
                    # If single record worked, try the batch
                    print(f"📤 Uploading {len(parsed_records)} records to 'Meter Readings' table...")
                    result = supabase.table('Meter Readings').upsert(parsed_records).execute()
                    
                    if result.data:
                        print(f"✅ Successfully uploaded {len(result.data)} records")
                        return True
                    else:
                        print(f"⚠️ No data returned from batch upload")
                        print(f"Response: {result}")
                        return False
                        
                except Exception as e:
                    print(f"❌ Supabase upload error: {e}")
                    print(f"Error type: {type(e).__name__}")
                    import traceback
                    print(traceback.format_exc())
                    return False
            else:
                if not supabase:
                    print("\n⚠️ Supabase client not available for upload test")
                if not parsed_records:
                    print("\n⚠️ No valid records to upload")
                return False
                
    except Exception as e:
        print(f"❌ Error processing CSV: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_csv_parsing_and_upload()
    print(f"\n{'✅ Test completed successfully' if success else '❌ Test failed'}")
