from flask import Flask, request, send_from_directory, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/send-email', methods=['POST'])
def send_email():
    name = request.form['name']
    email = request.form['email']
    message = request.form['message']

    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    receiver_email = os.getenv('RECEIVER_EMAIL')

    msg = MIMEMultipart()
    msg['From'] = email
    msg['To'] = receiver_email
    msg['Subject'] = f"Contact form submission from {name}"

    body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(send_email, receiver_email, text)
        server.quit()
        return 'Email sent successfully'
    except Exception as e:
        print(f"Error: {e}")
        return 'Error sending email'
    
    if __name__ == '__main__':
        app.run(debug=True, host='0.0.0.0', port=5000)  # Listen on all public IPs and port 5000