from werkzeug.security import generate_password_hash
import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password="Pinson25@",
    database="pinson_travel"
)

cursor = conn.cursor(dictionary=True)

# جلب المستخدمين
cursor.execute("SELECT id, password FROM users")
users = cursor.fetchall()

for user in users:
    plain_password = user['password']
    
    # فقط إذا كانت كلمة المرور غير مشفرة (بسيطة)
    if not plain_password.startswith('pbkdf2:'):  
        hashed_password = generate_password_hash(plain_password)
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user['id']))

conn.commit()
cursor.close()
conn.close()
print("✅ تم تحديث كلمات المرور وتشفيرها بنجاح.")