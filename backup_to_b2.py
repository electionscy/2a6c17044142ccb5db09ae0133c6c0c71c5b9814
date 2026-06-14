#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from b2sdk.v2 import InMemoryAccountInfo, B2Api

B2_KEY_ID = "4683e9d78dc5"
B2_APP_KEY = "00352faa3b0c857a48cbe9c39f8ae93cb061a3a361"
B2_BUCKET_ID = "9496d8f33e79cd5798ed0c15"
PROJECT_DIR = "/home/agent/migration_agent"
DB_FILE = f"{PROJECT_DIR}/migration_data.db"
LOG_FILE = f"{PROJECT_DIR}/cron_log.txt"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{timestamp}] {msg}"
    print(text, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(text + "\n")

try:
    log("Starting B2 backup...")
    
    if not os.path.exists(DB_FILE):
        log(f"❌ Database not found: {DB_FILE}")
        sys.exit(1)
    
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)
    bucket = b2_api.get_bucket_by_id(B2_BUCKET_ID)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    remote_name = f"backups/migration_data_{timestamp}.db"
    
    log(f"Uploading to B2: {remote_name}")
    bucket.upload_local_file(local_file=DB_FILE, file_name=remote_name)
    log(f"✅ Backup successful: {remote_name}")
    
except Exception as e:
    log(f"❌ Backup failed: {str(e)}")
    import traceback
    log(traceback.format_exc())
    sys.exit(1)
