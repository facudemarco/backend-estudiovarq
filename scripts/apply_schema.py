import os
from dotenv import load_dotenv
import pymysql

load_dotenv(override=True)

LEAD_COLS = {
    "lead_id": "VARCHAR(64)",
    "lastName": "VARCHAR(120)",
    "email": "VARCHAR(255)",
    "address": "VARCHAR(255)",
    "totalsM2": "VARCHAR(40)",
    "bathroom": "VARCHAR(40)",
    "diningRoom": "VARCHAR(40)",
    "kitchen": "VARCHAR(40)",
    "livingRoom": "VARCHAR(40)",
    "garage": "VARCHAR(40)",
    "mainBedroom": "VARCHAR(40)",
    "secondBedroom": "VARCHAR(40)",
    "plants": "VARCHAR(40)",
    "anotherPlace": "VARCHAR(255)",
    "startDate": "VARCHAR(40)",
    "zone": "VARCHAR(120)",
    "comments": "TEXT",
    "status": "VARCHAR(40) DEFAULT 'nuevo'",
    "question_index": "INT DEFAULT 0",
    "cualificado": "VARCHAR(8)",
    "razon_no_cual": "VARCHAR(255)",
    "etapa_seg": "VARCHAR(10)",
    "prox_seg_ts": "DATETIME NULL",
    "ultimo_msg_ts": "DATETIME NULL",
    "calendar_event_id": "VARCHAR(255)",
    "q1": "VARCHAR(255)", "q2": "VARCHAR(255)", "q3": "VARCHAR(255)",
    "q4": "VARCHAR(255)", "q5": "VARCHAR(255)", "q6": "VARCHAR(255)",
    "q7": "VARCHAR(255)", "q8": "VARCHAR(255)", "q9": "VARCHAR(255)",
    "notas": "TEXT",
}

STATEMENTS = [
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS status VARCHAR(40) DEFAULT 'nuevo'",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS lead_id VARCHAR(64)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS lastName VARCHAR(120)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS email VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS address VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS totalsM2 VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS bathroom VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS diningRoom VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS kitchen VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS livingRoom VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS garage VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS mainBedroom VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS secondBedroom VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS plants VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS anotherPlace VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS startDate VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS zone VARCHAR(120)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS comments TEXT",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS question_index INT DEFAULT 0",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS cualificado VARCHAR(8)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS razon_no_cual VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS etapa_seg VARCHAR(10)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS prox_seg_ts DATETIME NULL",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS ultimo_msg_ts DATETIME NULL",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS calendar_event_id VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q1 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q2 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q3 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q4 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q5 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q6 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q7 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q8 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS q9 VARCHAR(255)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS notas TEXT",
    "ALTER TABLE crm_messages ADD COLUMN IF NOT EXISTS source VARCHAR(10) DEFAULT 'bot'",
    "CREATE TABLE IF NOT EXISTS crm_events ("
    "  id INT AUTO_INCREMENT PRIMARY KEY,"
    "  phone VARCHAR(24) NOT NULL,"
    "  tipo VARCHAR(40) NOT NULL,"
    "  detail JSON NULL,"
    "  actor VARCHAR(8) DEFAULT 'bot',"
    "  ts DATETIME DEFAULT CURRENT_TIMESTAMP,"
    "  KEY (phone, ts))",
    "CREATE TABLE IF NOT EXISTS crm_users ("
    "  id INT AUTO_INCREMENT PRIMARY KEY,"
    "  username VARCHAR(60) NOT NULL UNIQUE,"
    "  password_hash VARCHAR(255) NOT NULL,"
    "  role VARCHAR(20) DEFAULT 'admin',"
    "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)",
    "UPDATE crm_leads SET status = stage WHERE status IS NULL AND stage IS NOT NULL",
]


def main():
    conn = pymysql.connect(
        host=os.getenv("HOST"), user=os.getenv("USER"),
        password=os.getenv("PASSWORD"), database=os.getenv("DATABASE"),
        connect_timeout=10,
    )
    cur = conn.cursor()
    for stmt in STATEMENTS:
        cur.execute(stmt)
    cur.execute("ALTER TABLE crm_leads ADD INDEX IF NOT EXISTS idx_etapa_prox (etapa_seg, prox_seg_ts)")
    cur.execute("ALTER TABLE crm_leads ADD INDEX IF NOT EXISTS idx_status (status)")
    cur.execute("ALTER TABLE crm_leads ADD INDEX IF NOT EXISTS idx_source_created (source, created_at)")
    conn.commit()
    print("schema ok")


if __name__ == "__main__":
    main()
