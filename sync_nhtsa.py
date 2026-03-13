#!/usr/bin/env python3
"""
RecallAlert — NHTSA Flat File Sync
Downloads NHTSA FLAT_RCL_POST_2010.zip, parses pipe-delimited flat file,
upserts all vehicle recall records to Supabase.
"""

import os, sys, time, zipfile, io, csv, json, logging
from datetime import datetime, date
from urllib.request import urlopen, Request
from urllib.error import URLError

NHTSA_URL = "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
TABLE = "vehicle_recalls"
BATCH_SIZE = 500

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("sync_nhtsa")

COLS = ["CAMPNO","MAKETXT","MODELTXT","YEARTXT","MFGCAMPNO","COMPNAME","MFGNAME","BGMAN","ENDMAN","RCLTYPECD","POTAFF","ODATE","INFLUENCED_BY","MFGTXT","RCDATE","DATEA","RETDTMN","FMVSS","DESC_DEFECT","CONEQUENCE_DEFECT","CORRECTIVE_ACTION","NOTES","RCL_CMPT_ID","MFR_COMP_NM","MFR_COMP_DESC","MFR_COMP_PTNO"]

def parse_date(s):
    if not s or len(s) < 8: return None
