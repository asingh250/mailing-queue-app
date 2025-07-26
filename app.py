from flask import Flask, request, jsonify, send_from_directory
import sqlite3
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)
DATABASE = 'queue_system.db'

# Initialize DB
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_number TEXT,
            phone_number TEXT,
            created_at TEXT,
            notified INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_token_number TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Send email: "You're 5 away"
def send_email_alert(to_email, token):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")

    subject = "Queue Alert: Your token is coming up!"
    body = f"Your token {token} is 5 away from being called. Please be ready near the counter."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
    except Exception as e:
        print("Email failed:", e)

# Send email when token is generated
def send_token_email(to_email, token):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")

    subject = "Your Queue Token Confirmation"
    body = f"Thank you! Your token number is {token}. We'll notify you when your turn is near."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
    except Exception as e:
        print("Confirmation email failed:", e)

# Token generation endpoint
@app.route('/token', methods=['POST'])
def generate_token():
    phone_number = request.json.get('phone_number')
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT token_number FROM tokens ORDER BY id DESC LIMIT 1')
    last = cursor.fetchone()
    last_number = int(last[0][1:]) if last else 99
    new_token = f"Q{last_number + 1}"
    cursor.execute(
        'INSERT INTO tokens (token_number, phone_number, created_at) VALUES (?, ?, ?)',
        (new_token, phone_number, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    # Send confirmation email to user
    send_token_email(phone_number, new_token)

    return jsonify({"token_number": new_token})

# Call next token and notify 5 ahead
@app.route('/next', methods=['POST'])
def call_next():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, token_number FROM tokens WHERE notified = 0 ORDER BY id LIMIT 1')
    current = cursor.fetchone()
    if not current:
        return jsonify({"message": "No more tokens"}), 200

    current_id, current_token = current
    cursor.execute('REPLACE INTO queue_state (id, current_token_number) VALUES (1, ?)', (current_token,))

    # Notify token 5 places ahead
    notify_id = current_id + 5
    cursor.execute('SELECT phone_number, token_number FROM tokens WHERE id = ?', (notify_id,))
    notify = cursor.fetchone()

    if notify:
        to_email, notify_token = notify
        send_email_alert(to_email, notify_token)

    cursor.execute('UPDATE tokens SET notified = 1 WHERE id = ?', (current_id,))
    conn.commit()
    conn.close()
    return jsonify({"called_token": current_token})

# Serve HTML
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
