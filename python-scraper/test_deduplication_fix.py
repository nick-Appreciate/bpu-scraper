#!/usr/bin/env python3
"""
Test script to verify the deduplication fix works correctly.
This will process the existing downloaded CSV file and show how many unique records we get.
"""

import csv
import os
from datetime import datetime
import glob

def test_deduplication_fix():
    # Find the most recent downloaded CSV file
    downloads_dir = os.path.expanduser("~/Downloads")
    csv_files = glob.glob(os.path.join(downloads_dir, "Usage*.csv"))
    
    if not csv_files:
        print("❌ No usage CSV files found in Downloads directory")
        return
    
    # Get the most recent file
    latest_file = max(csv_files, key=os.path.getmtime)
    print(f"📁 Processing file: {latest_file}")
    print(f"📊 File size: {os.path.getsize(latest_file)} bytes")
    
    parsed_usage_data = []
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            headers = csv_reader.fieldnames
            print(f"📊 CSV headers: {headers}")
            
            # Parse CSV rows with the FIXED logic
            for row_num, row in enumerate(csv_reader):
                if row_num < 3:  # Show first 3 rows for debugging
                    print(f"  Row {row_num + 1}: {dict(row)}")
                
                # Normalize keys (lowercase and trim) for robust access
                normalized_record = {}
                for key, value in row.items():
                    if key:  # Skip None keys
                        normalized_key = key.lower().strip()
                        normalized_record[normalized_key] = value
                
                # Extract data using known CSV headers
                account_number = normalized_record.get('account number', '')
                meter_id = normalized_record.get('meter', '')
                start_date_time_string = normalized_record.get('start', '')
                name = normalized_record.get('name', '')
                location = normalized_record.get('location', '')
                address = normalized_record.get('address', '')
                
                # Validate essential fields
                if not account_number or not meter_id or not start_date_time_string:
                    continue
                
                # Parse date with FIXED logic - preserve full datetime
                try:
                    if '/' in start_date_time_string:
                        # Format like "07/17/2025 12:00:00 AM" - preserve FULL datetime including time
                        parsed_date = datetime.strptime(start_date_time_string, '%m/%d/%Y %I:%M:%S %p')
                    else:
                        # Try parsing as-is
                        parsed_date = datetime.fromisoformat(start_date_time_string.replace('Z', '+00:00'))
                    
                    start_iso = parsed_date.isoformat()
                except (ValueError, TypeError) as e:
                    print(f"⚠️ Error parsing date '{start_date_time_string}': {e}")
                    continue
                
                # Create record
                supabase_data = {
                    'Start': start_iso,
                    'Account Number': account_number,
                    'Name': name,
                    'Meter': meter_id,
                    'Location': location,
                    'Address': address,
                }
                
                parsed_usage_data.append(supabase_data)
            
            print(f"📈 Total parsed records: {len(parsed_usage_data)}")
            
            # Test deduplication logic
            print(f"🔄 Testing deduplication...")
            unique_records = {}
            duplicates_found = 0
            
            for record in parsed_usage_data:
                # Create unique key from primary key components
                unique_key = (record['Account Number'], record['Meter'], record['Start'])
                if unique_key not in unique_records:
                    unique_records[unique_key] = record
                else:
                    duplicates_found += 1
                    if duplicates_found <= 5:  # Show first 5 duplicates
                        print(f"⚠️ Duplicate found: {unique_key}")
            
            print(f"✅ After deduplication: {len(unique_records)} unique records")
            print(f"📊 Duplicates removed: {duplicates_found}")
            
            # Show sample of unique timestamps to verify hourly readings are preserved
            print(f"\n📅 Sample timestamps to verify hourly readings:")
            sample_records = list(unique_records.values())[:10]
            for i, record in enumerate(sample_records):
                print(f"  {i+1}. Account: {record['Account Number']}, Meter: {record['Meter']}, Time: {record['Start']}")
            
            # Group by account and meter to show hourly readings per meter
            meter_readings = {}
            for record in unique_records.values():
                key = (record['Account Number'], record['Meter'])
                if key not in meter_readings:
                    meter_readings[key] = []
                meter_readings[key].append(record['Start'])
            
            print(f"\n📊 Readings per meter (showing first 3 meters):")
            for i, (meter_key, timestamps) in enumerate(list(meter_readings.items())[:3]):
                account, meter = meter_key
                print(f"  Meter {i+1}: Account {account}, Meter {meter} → {len(timestamps)} readings")
                # Show first few timestamps for this meter
                for j, ts in enumerate(sorted(timestamps)[:5]):
                    print(f"    {j+1}. {ts}")
                if len(timestamps) > 5:
                    print(f"    ... and {len(timestamps) - 5} more readings")
            
    except Exception as e:
        print(f"❌ Error processing file: {e}")

if __name__ == "__main__":
    test_deduplication_fix()
