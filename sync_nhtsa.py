#!/usr/bin/env python3
"""
RecallAlert — NHTSA Flat File Sync
Downloads NHTSA FLAT_RCL_POST_2010.zip, parses pipe-delimited flat file,
upserts all vehicle recall records to Supabase.

Run locally:  python sync_nhtsa.py
Run via CI:   see .github/workflows/sync.yml
"""

import os, sys, time, zipfile, io, csv, json, logging
from datetime import datetime, date
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── Config ──────────────────────────────────────────────────────────────────
NHTSA_URL = "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip"
FLAT_FILENAME = "FLAT_RCL.txt"          # filename inside the zip

SUPABASE_URL = os.environ["SUPABASE_URL"]          # e.g. https://xxx.supabase.co
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]  # service_role key (not anon)
TABLE = "vehicle_recalls"

BATCH_SIZE = 500       # rows per upsert batch (Supabase limit ~1000)
LOG_LEVEL  = "INFO"

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("sync_nhtsa")

# ── NHTSA column definitions (from RCL.txt data dictionary) ──────────────────
# Pipe-delimited, no header row — columns in fixed order
COLS = [
    "CAMPNO",           # 0  Campaign number (e.g. 24V001000)
    "MAKETXT",          # 1  Make (FORD, TOYOTA...)
    "MODELTXT",         # 2  Model
    "YEARTXT",          # 3  Model year
    "MFGCAMPNO",        # 4  Manufacturer campaign number
    "COMPNAME",         # 5  Component name
    "MFGNAME",          # 6  Manufacturer name
    "BGMAN",            # 7  Begin manufacture date
    "ENDMAN",           # 8  End manufacture date
    "RCLTYPECD",        # 9  Recall type (V=vehicle, T=tire, E=equipment, C=childseat)
    "POTAFF",           # 10 Potentially affected units
    "ODATE",            # 11 Owner notification date
    "INFLUENCED_BY",    # 12 What triggered the recall
    "MFGTXT",           # 13 Manufacturer text
    "RCDATE",           # 14 Recall initiation date (YYYYMMDD)
    "DATEA",            # 15 Added to database date
    "RETDTMN",          # 16 Remedy description
    "FMVSS",            # 17 Federal Motor Vehicle Safety Standard
    "DESC_DEFECT",      # 18 Defect description
    "CONEQUENCE_DEFECT",# 19 Consequence of defect  [sic — NHTSA's spelling]
    "CORRECTIVE_ACTION",# 20 Corrective action / remedy
    "NOTES",            # 21 Notes
    "RCL_CMPT_ID",      # 22 Recall component ID
    "MFR_COMP_NM",      # 23 Manufacturer component name
    "MFR_COMP_DESC",    # 24 Manufacturer component description
    "MFR_COMP_PTNO",    # 25 Manufacturer component part number
]


def parse_date(s: str):
    """Convert YYYYMMDD string to ISO date string, or None."""
    if not s or len(s) < 8:
        return None
    try:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    except Exception:
        return None


def parse_int(s: str):
    """Parse integer, return None on failure."""
    try:
        return int(s.strip()) if s and s.strip().isdigit() else None
    except Exception:
        return None


def download_flat_file() -> bytes:
    """Download the NHTSA zip and return raw bytes."""
    log.info(f"Downloading {NHTSA_URL} ...")
    t0 = time.time()
    req = Request(NHTSA_URL, headers={"User-Agent": "RecallAlert/1.0 (recall data aggregator)"})
    with urlopen(req, timeout=120) as resp:
        data = resp.read()
    elapsed = time.time() - t0
    log.info(f"Downloaded {len(data)/1_048_576:.1f} MB in {elapsed:.1f}s")
    return data


def parse_rows(zip_bytes: bytes) -> list[dict]:
    """Unzip and parse pipe-delimited flat file, return list of dicts."""
    log.info("Unzipping and parsing flat file ...")
    rows = []
    skipped = 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # Find the data file (name varies slightly between releases)
        names = zf.namelist()
        data_file = next((n for n in names if n.upper().endswith(".txt") and "RCL" in n.upper()), None)
        if not data_file:
            raise ValueError(f"Could not find recall data file in zip. Contents: {names}")
        log.info(f"Reading {data_file} from zip ...")

        with zf.open(data_file) as f:
            # NHTSA uses Latin-1 encoding (some manufacturer names have accented chars)
            reader = csv.reader(
                io.TextIOWrapper(f, encoding="latin-1", errors="replace"),
                delimiter="|",
                quoting=csv.QUOTE_NONE
            )
            for lineno, raw in enumerate(reader, 1):
                # Skip empty lines and header-like lines
                if not raw or len(raw) < 15:
                    skipped += 1
                    continue

                # Pad to expected column count
                row = (raw + [""] * len(COLS))[:len(COLS)]
                d = dict(zip(COLS, row))

                # Clean whitespace
                d = {k: v.strip() for k, v in d.items()}

                campaign = d.get("CAMPNO", "").strip()
                make     = d.get("MAKETXT", "").strip().upper()
                model    = d.get("MODELTXT", "").strip().upper()
                year     = d.get("YEARTXT", "").strip()

                # Skip rows with no campaign number
                if not campaign:
                    skipped += 1
                    continue

                rows.append({
                    "campaign_number":      campaign,
                    "make":                 make or None,
                    "model":                model or None,
                    "model_year":           year or None,
                    "manufacturer":         d.get("MFGNAME") or d.get("MFGTXT") or None,
                    "component":            d.get("COMPNAME") or None,
                    "defect_summary":       d.get("DESC_DEFECT") or None,
                    "consequence":          d.get("CONEQUENCE_DEFECT") or None,
                    "remedy":               d.get("CORRECTIVE_ACTION") or d.get("RETDTMN") or None,
                    "recall_date":          parse_date(d.get("RCDATE", "")),
                    "potentially_affected": parse_int(d.get("POTAFF", "")),
                    "recall_type":          d.get("RCLTYPECD") or "V",
                })

    log.info(f"Parsed {len(rows):,} rows ({skipped} skipped)")
    return rows


def upsert_batch(rows: list[dict]) -> dict:
    """Upsert a batch of rows to Supabase via REST API."""
    import urllib.request, json as json_mod
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    payload = json_mod.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer":        "resolution=merge-duplicates,return=minimal",
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return {"status": resp.status}


def sync():
    """Main sync function."""
    t_start = time.time()
    log.info("=== RecallAlert NHTSA Sync starting ===")

    # 1. Download
    try:
        zip_bytes = download_flat_file()
    except URLError as e:
        log.error(f"Download failed: {e}")
        sys.exit(1)

    # 2. Parse
    rows = parse_rows(zip_bytes)
    if not rows:
        log.error("No rows parsed — aborting")
        sys.exit(1)

    # 3. Upsert in batches
    log.info(f"Upserting {len(rows):,} rows to Supabase in batches of {BATCH_SIZE} ...")
    total_upserted = 0
    errors = 0

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE

        try:
            result = upsert_batch(batch)
            total_upserted += len(batch)
            if batch_num % 10 == 0 or batch_num == total_batches:
                pct = (i + len(batch)) / len(rows) * 100
                log.info(f"  Batch {batch_num}/{total_batches} ({pct:.0f}%) — {total_upserted:,} rows so far")
        except Exception as e:
            errors += 1
            log.warning(f"  Batch {batch_num} failed: {e}")
            if errors > 10:
                log.error("Too many batch errors — aborting")
                sys.exit(1)
            time.sleep(2)  # back off before retry

    elapsed = int((time.time() - t_start) * 1000)
    log.info(f"=== Done: {total_upserted:,} rows upserted in {elapsed/1000:.1f}s ===")

    # 4. Log the run to Supabase
    try:
        import urllib.request, json as json_mod
        url = f"{SUPABASE_URL}/rest/v1/pipeline_log"
        payload = json_mod.dumps([{
            "source": "nhtsa_flat_file",
            "rows_upserted": total_upserted,
            "duration_ms": elapsed,
            "status": "success",
            "message": f"Synced {total_upserted:,} NHTSA vehicle recall records"
        }]).encode()
        req = urllib.request.Request(url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "return=minimal"
        })
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log.warning(f"Could not write pipeline log: {e}")

    return total_upserted


if __name__ == "__main__":
    synced = sync()
    print(f"\n✅ Sync complete — {synced:,} NHTSA vehicle recalls in Supabase")
