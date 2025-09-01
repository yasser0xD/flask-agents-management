
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_from_directory, flash
from werkzeug.utils import secure_filename
import os
import mysql.connector
from functools import wraps
from datetime import datetime
from datetime import date
from werkzeug.security import check_password_hash
from uuid import uuid4  
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "defaultsecret")
app.config['UPLOAD_FOLDER'] = os.getenv("UPLOAD_FOLDER", "uploads")

# Gmail
SENDER_EMAIL = os.getenv("EMAIL_ADDRESS")
SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "flask_db")


def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Pinson25@",
        database="pinson_travel"
    )
    return connection, connection.cursor(dictionary=True)


def save_documents(files, client_id, client_name):
    folder_name = secure_filename(client_name.upper().replace(" ", "_"))
    client_folder = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)

    if not os.path.exists(client_folder):
        os.makedirs(client_folder)

    db, cursor = get_db_connection()
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(client_folder, filename)
            file.save(file_path)
            relative_path = os.path.join(folder_name, filename).replace('\\', '/')

            cursor.execute(
                "INSERT INTO documents (client_id, filename) VALUES (%s, %s)",
                (client_id, relative_path)
            )
            db.commit()
    cursor.close()
    db.close()

app = Flask(__name__)
app.secret_key = 'secretkey'

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads') 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


#------------------------------------------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db, cursor = get_db_connection()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            cursor.close()
            db.close()
            return redirect(url_for('dashboard'))

        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
        cursor.close()
        db.close()

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

#------------------------------------------------------------------------------------------------------------

@app.route('/')
@login_required
def dashboard():
    db, cursor = get_db_connection()

    # إجماليات عامة
    cursor.execute("SELECT COUNT(*) AS total_clients FROM clients")
    total_clients = cursor.fetchone()['total_clients']

    cursor.execute("SELECT COUNT(*) AS total_countries FROM countries")
    total_countries = cursor.fetchone()['total_countries']

    cursor.execute("SELECT COUNT(*) AS total_documents FROM documents")
    total_documents = cursor.fetchone()['total_documents']

    cursor.execute("SELECT IFNULL(SUM(amount_paid), 0) AS total_paid FROM clients")
    total_paid = cursor.fetchone()['total_paid']

    cursor.execute("SELECT IFNULL(SUM(amount_due - amount_paid), 0) AS total_unpaid FROM clients")
    total_unpaid = cursor.fetchone()['total_unpaid']

    cursor.execute("SELECT IFNULL(SUM(profit_amount), 0) AS total_profit FROM clients")
    total_profit = cursor.fetchone()['total_profit']

    # الإحصائيات الجديدة
    cursor.execute("SELECT COUNT(*) AS new_clients FROM clients WHERE created_at >= CURDATE() - INTERVAL 7 DAY")
    new_clients = cursor.fetchone()['new_clients']

    cursor.execute("SELECT COUNT(*) AS tourist_clients FROM clients WHERE visa_type = 'سياحية'")
    tourist_clients = cursor.fetchone()['tourist_clients']

    cursor.execute("SELECT COUNT(*) AS work_clients FROM clients WHERE visa_type = 'عمل'")
    work_clients = cursor.fetchone()['work_clients']

    cursor.execute("SELECT COUNT(*) AS single_clients FROM clients WHERE client_type = 'فردي'")
    single_clients = cursor.fetchone()['single_clients']

    cursor.execute("SELECT COUNT(*) AS family_clients FROM clients WHERE client_type = 'عائلي'")
    family_clients = cursor.fetchone()['family_clients']

    # توزيع أنواع الفيزا
    cursor.execute("SELECT visa_type, COUNT(*) AS count FROM clients GROUP BY visa_type")
    visa_type_stats = cursor.fetchall()

    cursor.execute("SELECT client_type, COUNT(*) AS count FROM clients GROUP BY client_type")
    client_type_stats = cursor.fetchall()

    # العملاء الجدد
    cursor.execute("""
        SELECT c.id, c.full_name, c.amount_paid, c.visa_type,
               co.name AS country_name, co.flag_filename, c.created_at
        FROM clients c
        JOIN countries co ON c.country_id = co.id
        ORDER BY c.created_at DESC
        LIMIT 5
    """)
    recent_clients_list = cursor.fetchall()

    # العملاء الذين يقترب موعد دفعهم
    cursor.execute("""
        SELECT c.id, c.full_name, c.file_payment_date, 
               co.name AS country_name, co.flag_filename
        FROM clients c
        JOIN countries co ON c.country_id = co.id
        WHERE c.file_payment_date IS NOT NULL
          AND c.file_payment_date BETWEEN CURDATE() AND CURDATE() + INTERVAL 10 DAY
        ORDER BY c.file_payment_date ASC
    """)
    upcoming_payment_clients = cursor.fetchall()

    cursor.execute("""
        SELECT 
            co.name AS country_name,
            co.flag_filename,
            IFNULL(SUM(c.amount_paid), 0) AS total_paid,
            IFNULL(SUM(c.amount_due - c.amount_paid), 0) AS total_unpaid,
            IFNULL(SUM(c.profit_amount), 0) AS total_profit,
            IFNULL(SUM(c.amount_due), 0) AS total_amount
        FROM countries co
        LEFT JOIN clients c ON c.country_id = co.id
        GROUP BY co.id, co.name, co.flag_filename
        ORDER BY total_amount DESC
    """)
    country_stats = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        'dashboard.html',
        total_clients=total_clients,
        total_countries=total_countries,
        total_documents=total_documents,
        total_paid=total_paid,
        total_unpaid=total_unpaid,
        total_profit=total_profit,
        recent_clients=new_clients,
        visa_type_stats=visa_type_stats,
        client_type_stats=client_type_stats,
        recent_clients_list=recent_clients_list,
        new_clients=new_clients,
        tourist_clients=tourist_clients,
        work_clients=work_clients,
        single_clients=single_clients,
        family_clients=family_clients,
        upcoming_payment_clients=upcoming_payment_clients,
        country_stats=country_stats  # << الإحصائيات الجديدة
    )



#------------------------------------------------------------------------------------------------------------

@app.route('/add-client', methods=['GET', 'POST'])
@login_required
def add_client():
    db, cursor = get_db_connection()
    if request.method == 'POST':

        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        file_payment_date = request.form.get('file_payment_date') or None
        amount_due = float(request.form['amount_due'])
        amount_paid = float(request.form['amount_paid'])
        profit_amount = float(request.form.get('profit_amount') or 0)
        comments = request.form['comments']
        registration_date = datetime.now().strftime('%Y-%m-%d')
        country_id = request.form['country_id']
        visa_type = request.form['visa_type']
        client_type = request.form['client_type']
        created_by = session['user_id']

        cursor.execute("""
    INSERT INTO clients (
        full_name, email, phone, amount_due, amount_paid,
        profit_amount, registration_date, country_id,
        comments, file_payment_date, visa_type,
        client_type, created_at, created_by
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (
    full_name, email, phone, amount_due, amount_paid,
    profit_amount, registration_date, country_id,
    comments, file_payment_date, visa_type,
    client_type, datetime.now(), created_by
))


        db.commit()
        client_id = cursor.lastrowid

        if 'documents' in request.files:
            save_documents(request.files.getlist('documents'), client_id, full_name)
         
        if client_type == 'family':
             member_names = request.form.getlist('member_full_name[]')
             member_is_child = request.form.getlist('member_is_child[]')

             for i in range(len(member_names)):
                 name = member_names[i]
                 is_child = False
                 if len(member_is_child) > i:
                    is_child = member_is_child[i] == 'true'

                 cursor.execute("""
            INSERT INTO family_members (
                client_id, full_name, is_child,
                amount_due, amount_paid, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            client_id, name, is_child,
            0.0, 0.0, datetime.now()
        ))

        db.commit()

        cursor.close()
        db.close()
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM countries")
    countries = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('add_client.html', countries=countries)

#------------------------------------------------------------------------------------------------------------

@app.route('/countries/<int:country_id>')
@login_required
def clients_by_countries(country_id):
    db, cursor = get_db_connection()
    page = request.args.get('page', 1, type=int)
    per_page = 8
    offset = (page - 1) * per_page
    search = request.args.get('search', '').strip()

    # جلب بيانات الدولة
    cursor.execute("SELECT name, flag_filename FROM countries WHERE id = %s", (country_id,))
    countries = cursor.fetchone()

    if countries is None:
        flash("لم يتم العثور على البلد المطلوب.", "warning")
        cursor.close()
        db.close()
        return redirect(url_for('dashboard'))

    like_pattern = f"%{search.lower()}%" if search else None

    # عدد العملاء
    if search:
        cursor.execute("""
            SELECT COUNT(*) AS count FROM clients
            WHERE country_id = %s AND LOWER(full_name) LIKE %s
        """, (country_id, like_pattern))
    else:
        cursor.execute("""
            SELECT COUNT(*) AS count FROM clients
            WHERE country_id = %s
        """, (country_id,))
    total_clients = cursor.fetchone()['count']
    total_pages = (total_clients + per_page - 1) // per_page

    # العملاء
    selected_fields = """
        id, full_name, client_type, visa_type,
        created_at, file_payment_date, amount_paid, amount_due
    """
    current_date = date.today()

    if search:
        query = f"""
            SELECT {selected_fields}
            FROM clients
            WHERE country_id = %s AND LOWER(full_name) LIKE %s
            ORDER BY visa_type ASC, client_type ASC,
                    (file_payment_date IS NOT NULL AND file_payment_date < %s) ASC,
                    file_payment_date ASC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, (country_id, like_pattern, current_date, per_page, offset))
    else:
        query = f"""
            SELECT {selected_fields}
            FROM clients
            WHERE country_id = %s
            ORDER BY visa_type ASC, client_type ASC,
                    (file_payment_date IS NOT NULL AND file_payment_date < %s) ASC,
                    file_payment_date ASC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, (country_id, current_date, per_page, offset))


    clients = cursor.fetchall()

    # الوسطاء المرتبطين بهذه الدولة
    cursor.execute("""
        SELECT id, name
        FROM agents
        WHERE country_id = %s
    """, (country_id,))
    agents = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        'clients_by_countries.html',
        countries=countries,
        clients=clients,
        agents=agents,  # 👈 الآن الوسطاء متاحين في الصفحة
        current_page=page,
        total_pages=total_pages,
        country_id=country_id,
        total_clients=total_clients,
        search=search,
        current_date=date.today()
    )



#------------------------------------------------------------------------------------------------------------


@app.route('/client/<int:client_id>')
@login_required
def client_details(client_id):
    db, cursor = get_db_connection()

    try:
        # جلب بيانات العميل مع اسم المستخدم الذي أضافه
        cursor.execute("""
            SELECT clients.*, users.username AS added_by
            FROM clients
            LEFT JOIN users ON clients.created_by = users.id
            WHERE clients.id = %s
        """, (client_id,))
        client = cursor.fetchone()

        if not client:
            return "العميل غير موجود", 404

        # جلب الوثائق
        cursor.execute("SELECT * FROM documents WHERE client_id = %s", (client_id,))
        documents = cursor.fetchall()

        # جلب أفراد العائلة إذا كان العميل عائلي
        family_members = []
        if client['client_type'] == 'family':
            cursor.execute("""
                SELECT *
                FROM family_members
                WHERE client_id = %s
            """, (client_id,))
            family_members = cursor.fetchall()

        # تمرير كل البيانات إلى القالب
        return render_template(
            'client_details.html',
            client=client,
            documents=documents,
            family_members=family_members
        )
    finally:
        cursor.close()
        db.close()


#------------------------------------------------------------------------------------------------------------

@app.route('/countries')
@login_required
def countries():
    db, cursor = get_db_connection()
    try:
        cursor.execute("""
            SELECT 
                countries.id,
                countries.name,
                countries.flag_filename,
                COUNT(clients.id) AS client_count
            FROM countries
            LEFT JOIN clients ON countries.id = clients.country_id
            GROUP BY countries.id
            ORDER BY client_count DESC
        """)
        countries = cursor.fetchall()
        return render_template('countries.html', countries=countries)
    finally:
        cursor.close()
        db.close()


# Route: Add Countries
@app.route('/add-countries', methods=['GET', 'POST'])
@login_required
def add_countries():
    if request.method == 'POST':
        countries_name = request.form['name']
        flag = request.files.get('flag')

        if flag and flag.filename:
            filename = secure_filename(flag.filename)
            file_path = os.path.join('static', 'flag', filename)
            flag.save(file_path)

            db, cursor = get_db_connection()
            try:
                cursor.execute(
                    "INSERT INTO countries (name, flag_filename) VALUES (%s, %s)",
                    (countries_name, filename)
                )
                db.commit()
            finally:
                cursor.close()
                db.close()

        return redirect(url_for('countries'))

    return render_template('add_countries.html')



#------------------------------------------------------------------------------------------------------------
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os

@app.route('/agents/add', methods=['POST'])
@login_required
def add_agent():
    name = request.form['name']
    email = request.form['email']   # ✅ استبدل phone بـ email
    country_id = request.form.get('country_id') or None

    db, cursor = get_db_connection()
    cursor.execute(
        "INSERT INTO agents (name, email, country_id) VALUES (%s, %s, %s)",
        (name, email, country_id)
    )
    db.commit()
    cursor.close()
    db.close()

    flash("تمت إضافة الوسيط بنجاح", "success")
    return redirect(url_for('agents'))


@app.route('/agents')
@login_required
def agents():
    db, cursor = get_db_connection()
    cursor.execute("""
        SELECT a.id, a.name, a.email, c.name AS country_name, c.flag_filename
        FROM agents a
        LEFT JOIN countries c ON a.country_id = c.id
        ORDER BY a.id DESC
    """)
    agents_list = cursor.fetchall()

    cursor.execute("SELECT id, name FROM countries ORDER BY name ASC")
    countries_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('agents.html', agents=agents_list, countries=countries_list)


@app.route('/send-to-agent', methods=['POST'])
@login_required
def send_to_agent():
    client_id = request.form['client_id']
    agent_id = request.form['agent_id']
    comment = request.form['comment']

    # جلب بيانات العميل والوسيط
    db, cursor = get_db_connection()
    cursor.execute("SELECT full_name FROM clients WHERE id=%s", (client_id,))
    client = cursor.fetchone()

    cursor.execute("SELECT name, email FROM agents WHERE id=%s", (agent_id,))
    agent = cursor.fetchone()

    cursor.close()
    db.close()

    # إعداد البريد
    sender_email = "pinson.travel@gmail.com"
    sender_password = "yusr xnat qfhz wvuk"
    receiver_email = agent['email']

    subject = f"Dossier client : {client.get('full_name', 'Nom du client')}"

    body = f"""
    Bonjour {agent.get('name', 'Agent')},

    Vous trouverez ci-joint le dossier complet concernant le client : {client.get('full_name', 'Nom du client')}. 

    Résumé / Commentaires :
    {comment if comment else 'Aucun commentaire spécifique.'}

    Pour toute question ou information complémentaire, n’hésitez pas à me contacter directement. 

    Nous vous remercions pour votre collaboration.

    Cordialement,  
    PINSON TRAVEL
    """

    # إنشاء رسالة البريد
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    # 📂 إرفاق الملفات من مجلد العميل
    client_folder = os.path.join(app.config['UPLOAD_FOLDER'], client['full_name'].upper().replace(" ", "_"))
    if os.path.exists(client_folder):
        for filename in os.listdir(client_folder):
            file_path = os.path.join(client_folder, filename)
            with open(file_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=filename)
                part['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(part)

    # ✉️ إرسال البريد عبر Gmail
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        flash("تم إرسال البريد الإلكتروني مع الملفات بنجاح ✅", "success")
    except Exception as e:
        flash(f"فشل إرسال البريد: {str(e)}", "danger")

    # 👇 go back to the same page instead of agents
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/agents/delete/<int:agent_id>', methods=['POST'])
@login_required
def delete_agent(agent_id):
    db, cursor = get_db_connection()
    try:
        cursor.execute("DELETE FROM agents WHERE id=%s", (agent_id,))
        db.commit()
        flash("تم حذف الوسيط بنجاح ✅", "success")
    except Exception as e:
        flash(f"فشل حذف الوسيط: {str(e)}", "danger")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for('agents'))

#------------------------------------------------------------------------------------------------------------

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/upload-documents', methods=['POST'])
def upload_documents():
    client_id = request.form.get('client_id')

    db, cursor = get_db_connection()
    try:
        cursor.execute("SELECT full_name FROM clients WHERE id = %s", (client_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'success': False, 'message': 'العميل غير موجود'}), 404

        client_name = result['full_name']
        files = request.files.getlist('documents')

        save_documents(files, client_id, client_name)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        db.close()


@app.route('/delete-document/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    db, cursor = get_db_connection()
    try:
        # استرجاع اسم الملف من قاعدة البيانات أولاً
        cursor.execute("SELECT filename FROM documents WHERE id = %s", (doc_id,))
        result = cursor.fetchone()

        if result:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], result['filename'])
            if os.path.exists(filepath):
                os.remove(filepath)

        # حذف السجل من قاعدة البيانات
        cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        db.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        db.close()



@app.route('/update-client/<int:client_id>', methods=['POST'])
@login_required
def update_client(client_id):
    db, cursor = get_db_connection()
    try:
        email = request.form.get('email')
        phone = request.form.get('phone')
        amount_due = request.form.get('amount_due') or 0
        amount_paid = request.form.get('amount_paid') or 0
        profit_amount = request.form.get('profit_amount') or 0  # ✅ سطر مضاف
        comments = request.form.get('comments', '')

        cursor.execute("""
            UPDATE clients 
            SET email = %s, phone = %s, 
                amount_due = %s, amount_paid = %s, 
                profit_amount = %s,                  -- ✅ مضاف هنا
                comments = %s
            WHERE id = %s
        """, (
            email, phone, amount_due, amount_paid, 
            profit_amount,                       # ✅ مضاف هنا
            comments, client_id
        ))
        db.commit()

        return jsonify({'success': True})
    
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        db.close()



@app.route('/delete-client/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    db, cursor = get_db_connection()
    try:
        # حذف الملفات المرتبطة
        cursor.execute("SELECT filename FROM documents WHERE client_id = %s", (client_id,))
        docs = cursor.fetchall()
        for doc in docs:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc['filename'])
            if os.path.exists(filepath):
                os.remove(filepath)

        # حذف أفراد العائلة
        cursor.execute("DELETE FROM family_members WHERE client_id = %s", (client_id,))

        # حذف الوثائق والعميل
        cursor.execute("DELETE FROM documents WHERE client_id = %s", (client_id,))
        cursor.execute("DELETE FROM clients WHERE id = %s", (client_id,))
        db.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        db.close()






if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host='0.0.0.0', port=5001, debug=True)

   