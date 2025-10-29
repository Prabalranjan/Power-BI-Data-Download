
# app.py - Sanitized FastAPI export service
# Note: All sensitive info replaced with placeholders. Replace environment variables before running.
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
import pandas as pd
from io import StringIO
import os

app = FastAPI(title="Sanitized Export Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# CONFIG - use environment variables (example in .env.example)
# -----------------------------
DB_HOST = os.getenv("DB_HOST", "<DB_HOST>")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "<DB_USER>")
DB_PASS = os.getenv("DB_PASS", "<DB_PASSWORD>")
DB_NAME = os.getenv("DB_NAME", "<DB_NAME>")  # used for connection; queries may reference multiple schemas

API_KEY_REQUIRED = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
API_KEY = os.getenv("EXPORT_API_KEY", "<YOUR_API_KEY>")

# -----------------------------
# DB connection helper
# -----------------------------
def get_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            auth_plugin='mysql_native_password'
        )
        return conn
    except mysql.connector.Error as e:
        raise Exception(f"Failed to connect to database: {str(e)}")

# -----------------------------
# Build SQL dynamically - sanitized schema names used:
#   core_db -> transactional tables (replace with your schema)
#   ref_db  -> reference/lookup tables (replace with your schema)
# -----------------------------
def build_query_and_params(query_params):
    """Build SQL + params for export. Accepts:
    - district, block, cluster, school_management, school_type, geography
    Values may be comma-separated to request multiple.
    """

    base_query = f"""
        SELECT
            d.district_name    AS district,
            b.block            AS block,
            c.cluster          AS cluster,
            s.udise_id         AS udise_id,
            s.school_name      AS school_name,
            sm.school_management AS school_management,
            CASE s.school_assam_category_id
                WHEN 1 THEN 'LP'
                WHEN 2 THEN 'UP'
                WHEN 3 THEN 'HS'
                WHEN 4 THEN 'HSS'
                ELSE NULL
            END AS school_category,
            st.total_students,
            st.total_students_present,
            sf.total_teaching_staff,
            sf.total_non_teaching_staff,
            sf.total_teaching_staff_present,
            sf.total_non_teaching_staff_present
        FROM core_db.tbl_rp_school_registration_2025_2026 s
        LEFT JOIN ref_db.district d ON s.district_id = d.district_id
        LEFT JOIN ref_db.blocks b ON s.block_id = b.block_id
        LEFT JOIN ref_db.cluster c ON s.cluster_id = c.cluster_id
        LEFT JOIN ref_db.school_management sm ON s.school_management_id = sm.school_management_id

        LEFT JOIN (
            SELECT
                s.udise_id,
                IFNULL(SUM(registered_students), 0) AS total_students,
                IFNULL(SUM(present), 0) AS total_students_present
            FROM core_db.tbl_rp_students_summery_today_2025_2026 s
            WHERE s.report_date = CURDATE()
            GROUP BY s.udise_id
        ) st ON s.udise_id = st.udise_id

        LEFT JOIN (
            SELECT
                s.udise_id,
                IFNULL(SUM(CASE WHEN staff_type_id = 1 THEN total_staff END), 0) AS total_teaching_staff,
                IFNULL(SUM(CASE WHEN staff_type_id != 1 THEN total_staff END), 0) AS total_non_teaching_staff,
                IFNULL(SUM(CASE WHEN staff_type_id = 1 THEN present END), 0) AS total_teaching_staff_present,
                IFNULL(SUM(CASE WHEN staff_type_id != 1 THEN present END), 0) AS total_non_teaching_staff_present
            FROM core_db.tbl_rp_staff_registration_2025_2026 s
            WHERE s.report_date = CURDATE()
            GROUP BY s.udise_id
        ) sf ON s.udise_id = sf.udise_id

        WHERE s.report_date = CURDATE()
    """

    filters = []
    params = []

    def add_in_clause(field, param_name):
        if param_name in query_params and query_params[param_name]:
            values = [v.strip() for v in query_params[param_name].split(",") if v.strip()]
            if values:
                placeholders = ", ".join(["%s"] * len(values))
                filters.append(f"{field} IN ({placeholders})")
                params.extend(values)

    # Map Power BI parameter names to DB fields
    add_in_clause("d.district_name", "district")
    add_in_clause("b.block", "block")
    add_in_clause("c.cluster", "cluster")
    add_in_clause("sm.school_management", "school_management")
    add_in_clause("g.geography", "geography")

    # school_type maps to category IDs
    if "school_type" in query_params and query_params["school_type"]:
        mappings = {"LP": 1, "UP": 2, "HS": 3, "HSS": 4}
        types = [v.strip() for v in query_params["school_type"].split(",") if v.strip()]
        ids = [mappings[t] for t in types if t in mappings]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            filters.append(f"s.school_assam_category_id IN ({placeholders})")
            params.extend(ids)

    if filters:
        base_query += " AND " + " AND ".join(filters)

    base_query += """ 
        ORDER BY s.district_id, s.block_id, s.cluster_id, s.udise_id
    """

    return base_query, params

# -----------------------------
# Export endpoint
# -----------------------------
@app.get("/export")
async def export(request: Request):
    q = dict(request.query_params)

    # API key enforcement (optional)
    if API_KEY_REQUIRED:
        key = q.get("apikey") or request.headers.get("x-api-key")
        if key != API_KEY:
            return {"error": "invalid API key"}, 401

    sql, params = build_query_and_params(q)
    out_format = q.get("format", "csv").lower()

    try:
        conn = get_connection()
        # pandas will execute safely with parameters
        df = pd.read_sql(sql, conn, params=params)
        conn.close()
    except Exception as e:
        return {"error": "database error", "detail": str(e)}, 500

    if out_format == "json":
        return df.to_dict(orient="records")

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    headers = {"Content-Disposition": "attachment; filename=export.csv"}

    return StreamingResponse(iter([csv_buffer.getvalue()]), media_type="text/csv", headers=headers)

# -----------------------------
# Health
# -----------------------------
@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}
