import os
import sys

from dotenv import load_dotenv
import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)

from routers.auth import hash_password

if len(sys.argv) != 3:
    print("uso: python scripts/create_user.py <username> <password>")
    sys.exit(1)

username, password = sys.argv[1], sys.argv[2]
conn = pymysql.connect(
    host=os.getenv("HOST"), user=os.getenv("USER"),
    password=os.getenv("PASSWORD"), database=os.getenv("DATABASE"),
    connect_timeout=10,
)
cur = conn.cursor()
cur.execute(
    "INSERT INTO crm_users (username, password_hash, role) VALUES (%s, %s, 'admin') "
    "ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash)",
    (username, hash_password(password)),
)
conn.commit()
print(f"usuario {username} creado/actualizado")
conn.close()
