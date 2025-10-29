
# FastAPI Export Service (Sanitized Public Version)

**Purpose:** this FastAPI service provides a simple, parameter-driven CSV / JSON export endpoint that Power BI (or any HTTP client) can call to download filtered data.  
This repository is a sanitized public version — all credentials, hostnames, and sensitive schema names were replaced with generic placeholders.

---

## Files in this repo

- `app.py` — FastAPI application (sanitized)
- `.env.example` — example environment variables file
- `README.md` — this file

---

## Quick start

1. Create a Python virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install fastapi uvicorn mysql-connector-python pandas python-dotenv
```

2. Copy `.env.example` to `.env` and fill with your values (see below).

3. Run the server:
```bash
uvicorn app:app --reload --port 8000
```

4. Test:
- CSV: `http://<YOUR_SERVER_URL>/export?district=CHIRANG`
- JSON: `http://<YOUR_SERVER_URL>/export?district=CHIRANG&format=json`

---

## Environment variables (.env.example)
```
DB_HOST=<YOUR_DB_HOST>
DB_PORT=3306
DB_USER=<YOUR_DB_USER>
DB_PASS=<YOUR_DB_PASSWORD>
DB_NAME=<YOUR_DB_NAME>        # used for the connection; queries may reference multiple schemas
API_KEY_REQUIRED=false
EXPORT_API_KEY=<YOUR_API_KEY>
```

---

## How Power BI should call this (DAX measure)

Add this measure in Power BI to build the dynamic export URL. Replace the host with your deployed server URL if needed.

```DAX
Export URL =
VAR BaseURL = "http://localhost:8000/export"
VAR DistrictVal = SELECTEDVALUE('DIM District'[District])
VAR BlockVal = SELECTEDVALUE('DIM District'[Block])
VAR ClusterVal = SELECTEDVALUE('DIM District'[Cluster])
VAR SchoolTypeVal = SELECTEDVALUE(AssamSchoolCategory[School Category])
VAR SchoolManagementVal = SELECTEDVALUE(School_Management[school_management])
VAR GeographyVal = SELECTEDVALUE('Disitrict Geography'[Geography])

VAR P1 = IF( NOT( ISBLANK(DistrictVal) ), "?district=" & DistrictVal, "" )
VAR P2 = IF( NOT( ISBLANK(BlockVal) ), IF( LEN(P1) = 0, "?block=" & BlockVal, P1 & "&block=" & BlockVal ), P1 )
VAR P3 = IF( NOT( ISBLANK(ClusterVal) ), IF( LEN(P2) = 0, "?cluster=" & ClusterVal, P2 & "&cluster=" & ClusterVal ), P2 )
VAR P4 = IF( NOT( ISBLANK(SchoolTypeVal) ), IF( LEN(P3) = 0, "?school_type=" & SchoolTypeVal, P3 & "&school_type=" & SchoolTypeVal ), P3 )
VAR P5 = IF( NOT( ISBLANK(SchoolManagementVal) ), IF( LEN(P4) = 0, "?school_management=" & SchoolManagementVal, P4 & "&school_management=" & SchoolManagementVal ), P4 )
VAR P6 = IF( NOT( ISBLANK(GeographyVal) ), IF( LEN(P5) = 0, "?geography=" & GeographyVal, P5 & "&geography=" & GeographyVal ), P5 )
RETURN
IF( LEN(P6) = 0, BaseURL, BaseURL & P6 )
```

**How it works:**
- Put this measure in a Card or Table visual.
- Set the measure's data category to **Web URL**.
- Clicking it opens the browser and calls the `/export` endpoint with current slicer values, producing a CSV download.

---

## Notes & best practices

- The sanitized `app.py` references `core_db` and `ref_db` as example schema names in the SQL. Replace them with the actual schema names in your environment.
- Use environment variables for credentials and keep them out of source control.
- In production, enable `API_KEY_REQUIRED=true` and set a strong `EXPORT_API_KEY`.
- Deploy behind HTTPS (reverse proxy + TLS).
- Limit DB user privileges (SELECT-only is recommended).
- Add proper indexes on frequently filtered columns (e.g., `district_id`, `report_date`, `udise_id`).

---

## License & attribution

This sanitized example is provided for educational purposes. Replace placeholders with your own values before using in production.
