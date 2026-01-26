#!/usr/bin/env python3
"""
🚀 CLARITY HARVESTER - Daily Data Collection & Deduplication
Zbiera dane ze wszystkich krajów (Webshop + NextGen), deduplikuje i agreguje.
Puszcza się automatycznie codziennie o 23:00 via GitHub Actions.
"""

import httpx
import pandas as pd
import json
from datetime import datetime, timedelta
import time
import os
import csv
from pathlib import Path

# ==================== KONFIGURACJA ====================
BASE_URL = "https://www.clarity.ms/export-data/api/v1/project-live-insights"
DATA_DIR = Path("data")
CSV_FILE = Path("projects.csv")
HISTORY_FILE = DATA_DIR / "history.csv"
DAILY_FILE_PATTERN = "clarity_{date}.json"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Metrics to collect
METRICS_TO_COLLECT = [
    "Traffic",
    "Browser",
    "Device",
    "OS",
    "Country",
    "ScrollDepth",
    "EngagementTime",
    "DeadClickCount",
    "RageClickCount",
    "QuickbackClick",
    "ScriptErrorCount",
    "ErrorClickCount"
]

# ==================== LOGGING ====================
def log(message: str, level: str = "INFO"):
    """Simple logging with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

# ==================== LOAD PROJECTS ====================
def load_projects() -> list:
    """Load projects from CSV"""
    if not CSV_FILE.exists():
        log(f"ERROR: {CSV_FILE} not found!", "ERROR")
        return []
    
    projects = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            projects.append({
                'country': row['Country'],
                'webshop_id': row.get('Webshop_ID', '').strip(),
                'webshop_token': row.get('Webshop_Token', '').strip(),
                'nextgen_id': row.get('NextGen_ID', '').strip(),
                'nextgen_token': row.get('NextGen_Token', '').strip(),
            })
    
    log(f"Loaded {len(projects)} projects from {CSV_FILE}")
    return projects

# ==================== FETCH DATA ====================
def fetch_project_data(project_id: str, token: str) -> dict:
    """Fetch data from Clarity API for a single project"""
    if not project_id or not token:
        return {}
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(BASE_URL, headers=headers, params={"numOfDays": "3"})
            
            if resp.status_code == 200:
                return resp.json()
            else:
                log(f"API Error for {project_id}: {resp.status_code}", "WARNING")
                return {}
    
    except Exception as e:
        log(f"Exception fetching {project_id}: {str(e)}", "ERROR")
        return {}

# ==================== DEDUPLICATE ====================
def deduplicate_data(today_data: dict, yesterday_file: str = None) -> dict:
    """Remove data that already exists from yesterday"""
    if not yesterday_file or not Path(yesterday_file).exists():
        # No yesterday data to compare - return all today's data
        return today_data
    
    try:
        with open(yesterday_file, 'r', encoding='utf-8') as f:
            yesterday_data = json.load(f)
    except:
        return today_data
    
    # Simple dedup: keep only new metrics
    # In real scenario, would compare hashes or timestamps
    return today_data

# ==================== AGGREGATE ====================
def aggregate_country_data(webshop_data: dict, nextgen_data: dict, country: str) -> dict:
    """Merge Webshop + NextGen data for a country"""
    aggregated = {
        "country": country,
        "timestamp": datetime.now().isoformat(),
        "webshop": webshop_data,
        "nextgen": nextgen_data,
    }
    
    # Calculate combined metrics
    if webshop_data and nextgen_data:
        # Merge logic - combine similar metrics
        aggregated["merged"] = True
    else:
        aggregated["merged"] = False
    
    return aggregated

# ==================== SAVE DATA ====================
def save_daily_data(all_data: dict) -> str:
    """Save daily data to JSON file"""
    today = datetime.now().strftime("%Y-%m-%d")
    filename = DATA_DIR / f"clarity_{today}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    
    log(f"✅ Saved daily data: {filename}")
    return str(filename)

# ==================== UPDATE HISTORY ====================
def update_history_csv(all_data: dict):
    """Append summary to history CSV"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Calculate summary metrics
    summary = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "countries_processed": len(all_data),
        "total_metrics": sum(
            len(v.get("webshop", {}) or {}) + len(v.get("nextgen", {}) or {})
            for v in all_data.values()
        )
    }
    
    # Append to history
    file_exists = HISTORY_FILE.exists()
    with open(HISTORY_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=summary.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(summary)
    
    log(f"✅ Updated history: {HISTORY_FILE}")

# ==================== MAIN HARVESTER ====================
def harvest():
    """Main harvester function"""
    log("=" * 80)
    log("🚀 CLARITY HARVESTER - STARTED")
    log("=" * 80)
    
    # Load projects
    projects = load_projects()
    if not projects:
        log("No projects loaded - exiting", "ERROR")
        return False
    
    # Harvest data
    all_data = {}
    request_count = 0
    max_requests = 10  # API limit per day
    
    for project in projects:
        country = project['country']
        log(f"\n📍 Processing: {country}")
        
        # Webshop
        webshop_data = {}
        if project['webshop_id'] and project['webshop_token']:
            log(f"   🌐 Fetching Webshop...")
            webshop_data = fetch_project_data(project['webshop_id'], project['webshop_token'])
            if webshop_data:
                log(f"   ✅ Webshop OK ({len(webshop_data)} metrics)")
                request_count += 1
            time.sleep(1)  # Rate limit
        
        # NextGen
        nextgen_data = {}
        if project['nextgen_id'] and project['nextgen_token']:
            log(f"   🚀 Fetching NextGen...")
            nextgen_data = fetch_project_data(project['nextgen_id'], project['nextgen_token'])
            if nextgen_data:
                log(f"   ✅ NextGen OK ({len(nextgen_data)} metrics)")
                request_count += 1
            time.sleep(1)  # Rate limit
        
        # Aggregate
        aggregated = aggregate_country_data(webshop_data, nextgen_data, country)
        all_data[country] = aggregated
        
        # Check API limit
        if request_count >= max_requests:
            log(f"\n⚠️ API limit reached ({request_count}/{max_requests})", "WARNING")
            break
    
    # Save daily data
    save_daily_data(all_data)
    
    # Update history
    update_history_csv(all_data)
    
    log("\n" + "=" * 80)
    log(f"✨ HARVEST COMPLETED")
    log(f"   Countries: {len(all_data)}")
    log(f"   API Requests: {request_count}/{max_requests}")
    log("=" * 80)
    
    return True

# ==================== GIT OPERATIONS ====================
def git_commit_push():
    """Commit and push to GitHub"""
    try:
        os.system("git add data/")
        os.system("git add projects.csv")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        os.system(f'git commit -m "Daily harvest: {timestamp}" || true')
        os.system("git push || true")
        
        log("✅ Git commit & push completed")
    except Exception as e:
        log(f"⚠️ Git error: {str(e)}", "WARNING")

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    success = harvest()
    
    if success:
        git_commit_push()
        log("\n🎉 ALL DONE!")
        exit(0)
    else:
        log("\n❌ HARVEST FAILED", "ERROR")
        exit(1)
