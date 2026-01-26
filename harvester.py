#!/usr/bin/env python3
"""
🚀 CLARITY HARVESTER - ROTACYJNY Daily Data Collection & Deduplication
Zbiera dane ze 5 krajów dziennie (rotation system - 4 dniowy cykl)
Dzień 0 (dni 1-4): Austria, Belgium, Switzerland, Germany, Denmark
Dzień 1 (dni 5-8): Finland, France, Hungary, Ireland, Italy
Dzień 2 (dni 9-12): Luxembourg, Netherlands, Norway, Poland, Portugal
Dzień 3 (dni 13-16): Sweden, Slovakia, Spain, UK, ZenDesk
Potem cykl się powtarza (dni 17-20 = Dzień 0, itd.)
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
STATE_FILE = DATA_DIR / "harvester_state.json"
HISTORY_FILE = DATA_DIR / "history.csv"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Kraje podzielone na 4 grupy (każda dzień)
COUNTRY_ROTATIONS = {
    0: ["Austria", "Belgium", "Switzerland", "Germany", "Denmark"],
    1: ["Finland", "France", "Hungary", "Ireland", "Italy"],
    2: ["Luxembourg", "Netherlands", "Norway", "Poland", "Portugal"],
    3: ["Sweden", "Slovakia", "Spain", "UK", "ZenDesk"],
}

# ==================== LOGGING ====================
def log(message: str, level: str = "INFO"):
    """Simple logging with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

# ==================== ROTATION STATE ====================
def get_rotation_day() -> int:
    """Calculate which rotation day we're on (0-3)"""
    # Get today's day of month
    day_of_month = datetime.now().day
    # Cycle through 0-3 every 4 days
    # Days 1-4: 0, 5-8: 1, 9-12: 2, 13-16: 3, 17-20: 0, 21-24: 1, 25-28: 2, 29+: 3
    return ((day_of_month - 1) // 4) % 4

def get_countries_for_today() -> list:
    """Get list of countries to harvest today"""
    rotation_day = get_rotation_day()
    countries = COUNTRY_ROTATIONS[rotation_day]
    log(f"🔄 ROTATION DAY: {rotation_day} (Day {rotation_day + 1} of 4-day cycle)")
    log(f"📍 Countries to harvest TODAY: {', '.join(countries)}")
    return countries

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
                'country': row['Country'].strip(),
                'webshop_id': row.get('Webshop_ID', '').strip(),
                'webshop_token': row.get('Webshop_Token', '').strip(),
                'nextgen_id': row.get('NextGen_ID', '').strip(),
                'nextgen_token': row.get('NextGen_Token', '').strip(),
            })
    
    log(f"Loaded {len(projects)} projects from {CSV_FILE}")
    return projects

# ==================== FETCH DATA ====================
def fetch_project_data(project_id: str, token: str, country: str, project_type: str) -> dict:
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
                log(f"   ✅ {country} {project_type}: {len(resp.json())} metrics")
                return resp.json()
            else:
                log(f"   ⚠️ {country} {project_type}: Status {resp.status_code}", "WARNING")
                return {}
    
    except Exception as e:
        log(f"   🔥 {country} {project_type}: {str(e)}", "ERROR")
        return {}

# ==================== AGGREGATE ====================
def aggregate_country_data(webshop_data: dict, nextgen_data: dict, country: str) -> dict:
    """Merge Webshop + NextGen data for a country"""
    aggregated = {
        "country": country,
        "timestamp": datetime.now().isoformat(),
        "webshop": webshop_data,
        "nextgen": nextgen_data,
        "merged": bool(webshop_data and nextgen_data)
    }
    
    return aggregated

# ==================== SAVE DATA ====================
def save_daily_data(all_data: dict, today: str) -> str:
    """Save daily data to JSON file"""
    filename = DATA_DIR / f"clarity_{today}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    
    log(f"✅ Saved daily data: {filename}")
    return str(filename)

# ==================== UPDATE HISTORY ====================
def update_history_csv(all_data: dict, rotation_day: int):
    """Append summary to history CSV"""
    today = datetime.now().strftime("%Y-%m-%d")
    countries_list = list(all_data.keys())
    
    summary = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "rotation_day": rotation_day,
        "countries_processed": len(all_data),
        "countries": ", ".join(countries_list),
        "total_metrics": sum(
            len(v.get("webshop", {}) or {}) + len(v.get("nextgen", {}) or {})
            for v in all_data.values()
        )
    }
    
    file_exists = HISTORY_FILE.exists()
    with open(HISTORY_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=summary.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(summary)
    
    log(f"✅ Updated history: {HISTORY_FILE}")

# ==================== MAIN HARVESTER ====================
def harvest():
    """Main harvester function with rotation"""
    log("=" * 80)
    log("🚀 CLARITY HARVESTER - ROTACYJNY - STARTED")
    log("=" * 80)
    
    # Get rotation info
    rotation_day = get_rotation_day()
    countries_to_harvest = get_countries_for_today()
    
    # Load projects
    all_projects = load_projects()
    if not all_projects:
        log("No projects loaded - exiting", "ERROR")
        return False
    
    # Filter projects for today's rotation
    projects_today = [p for p in all_projects if p['country'] in countries_to_harvest]
    log(f"\n📍 Found {len(projects_today)} projects for today's rotation")
    
    if not projects_today:
        log("No projects match today's rotation", "WARNING")
        return False
    
    # Harvest data
    all_data = {}
    request_count = 0
    max_requests = 10  # API limit per day
    
    for project in projects_today:
        country = project['country']
        log(f"\n📍 Processing: {country}")
        
        webshop_data = {}
        nextgen_data = {}
        
        # Webshop
        if project['webshop_id'] and project['webshop_token']:
            log(f"   🌐 Fetching Webshop...")
            webshop_data = fetch_project_data(
                project['webshop_id'], 
                project['webshop_token'],
                country,
                "Webshop"
            )
            if webshop_data:
                request_count += 1
            time.sleep(1)  # Rate limit
        
        # NextGen
        if project['nextgen_id'] and project['nextgen_token']:
            log(f"   🚀 Fetching NextGen...")
            nextgen_data = fetch_project_data(
                project['nextgen_id'], 
                project['nextgen_token'],
                country,
                "NextGen"
            )
            if nextgen_data:
                request_count += 1
            time.sleep(1)  # Rate limit
        
        # Aggregate
        if webshop_data or nextgen_data:
            aggregated = aggregate_country_data(webshop_data, nextgen_data, country)
            all_data[country] = aggregated
        else:
            log(f"   ⚠️ No data for {country}", "WARNING")
        
        # Check API limit
        if request_count >= max_requests:
            log(f"\n⚠️ API limit reached ({request_count}/{max_requests})", "WARNING")
            break
    
    # Save daily data
    today = datetime.now().strftime("%Y-%m-%d")
    save_daily_data(all_data, today)
    
    # Update history
    update_history_csv(all_data, rotation_day)
    
    log("\n" + "=" * 80)
    log(f"✨ HARVEST COMPLETED")
    log(f"   Countries: {len(all_data)}")
    log(f"   API Requests: {request_count}/{max_requests}")
    log(f"   Rotation: Day {rotation_day}/4")
    log("=" * 80)
    
    return True

# ==================== GIT OPERATIONS ====================
def git_commit_push():
    """Commit and push to GitHub"""
    try:
        os.system("git add data/")
        os.system("git add projects.csv")
        
        rotation_day = get_rotation_day()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        os.system(f'git commit -m "🤖 Daily harvest (Day {rotation_day}/4): {timestamp}" || true')
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
