# -*- coding: utf-8 -*-
"""app

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1oA26apSPXyforxROJFar0JQFECopbYyE
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import os
from datetime import datetime
import random
import pymysql
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)

# Configure MySQL connection
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'your_mysql_user'
app.config['MYSQL_PASSWORD'] = 'your_mysql_password'
app.config['MYSQL_DB'] = 'your_mysql_database'

# Initialize MySQL connection
mysql = pymysql.connect(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    db=app.config['MYSQL_DB'],
    cursorclass=pymysql.cursors.DictCursor
)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Set the login view


class User(UserMixin):
    def __init__(self, id, full_name, username, password, role):
        self.user_id = id
        self.full_name = full_name
        self.username = username
        self.password = password  # Storing hashed password
        self.role = role

    def __repr__(self):
        return f'<User(username={self.username}, role={self.role})>'

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def get_user_id(self):
        return str(self.user_id)


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id_int = int(user_id)
        with mysql.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id_int,))
            user_data = cursor.fetchone()
            if user_data:
                return User(user_data['user_id'], user_data['full_name'], user_data['username'], user_data['password'],
                            user_data['role'])
        return None
    except (ValueError, pymysql.Error) as e:
        print(f"Error loading user: {e}")
        return None


@app.before_request
def before_request():
    session.permanent = True  # Make the session permanent
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']
    session.modified = True  # Ensure session expiry is checked on each request
    if current_user.is_authenticated and 'last_activity' in session:
        if datetime.utcnow() - session['last_activity'] > app.permanent_session_lifetime:
            logout_user()
            return redirect(url_for('login', message='Session timed out. Please log in again.'))
    session['last_activity'] = datetime.utcnow()


# Routes
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        try:
            with mysql.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user_data = cursor.fetchone()
                if user_data and check_password_hash(user_data['password'], password):
                    user = User(user_data['user_id'], user_data['full_name'], user_data['username'],
                                user_data['password'], user_data['role'])
                    login_user(user)
                    if user.role == 'Admin':
                        return redirect(url_for('admin_dashboard'))
                    elif user.role == 'Finance Officer':
                        return redirect(url_for('finance_officer_dashboard'))
                    elif user.role == 'Auditor':
                        return redirect(url_for('auditor_dashboard'))
                else:
                    return render_template('login.html', error="Invalid credentials.")
        except pymysql.Error as e:
            print(f"Error during login: {e}")
            return render_template('login.html', error="Database error during login.")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('last_activity', None)
    return redirect(url_for('home'))


# Admin functionalities
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'Admin':
        return jsonify({"msg": "Unauthorized"}), 403
    return render_template('admin.html')


@app.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'Admin':
        return jsonify({"msg": "Unauthorized"}), 403

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        full_name = request.form.get('full_name')
        if username and password and role and full_name:
            hashed_password = generate_password_hash(password)
            try:
                with mysql.cursor() as cursor:
                    cursor.execute("INSERT INTO users (full_name, username, password, role) VALUES (%s, %s, %s, %s)",
                                   (full_name, username, hashed_password, role))
                    mysql.commit()
                    return render_template('admin.html', message="User added successfully!")
            except pymysql.Error as e:
                mysql.rollback()
                print(f"Error adding user: {e}")
                return render_template('add user.html', error="Database error adding user.")
        return render_template('add user.html', error="All fields are required.")
    return render_template('add user.html')


@app.route('/view_password/<int:user_id>')
@login_required
def view_password(user_id):
    if current_user.role != 'Admin':
        return jsonify({"msg": "Unauthorized"}), 403
    try:
        with mysql.cursor() as cursor:
            cursor.execute("SELECT username, password FROM users WHERE user_id = %s", (user_id,))
            user_data = cursor.fetchall()
            if user_data:
                return render_template('view_password.html', username=user_data['username'],
                                       password=user_data['password'])
            else:
                return render_template('admin.html', error=f"User with ID {user_id} not found.")
    except pymysql.Error as e:
        print(f"Error fetching password: {e}")
        return render_template('admin.html', error="Database error fetching password.")


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        if check_password_hash(current_user.password, current_password):
            hashed_new_password = generate_password_hash(new_password)
            try:
                with mysql.cursor() as cursor:
                    cursor.execute("UPDATE users SET password = %s WHERE user_id = %s",
                                   (hashed_new_password, current_user.user_id))
                    mysql.commit()
                    return render_template('home.html', message="Password changed successfully.")
            except pymysql.Error as e:
                mysql.rollback()
                print(f"Error changing password: {e}")
                return render_template('change password.html', error="Database error changing password.")
        else:
            return render_template('change password.html', error="Current password is incorrect.")
    return render_template('change password.html')


# Finance Officer Dashboard
@app.route('/finance_officer_dashboard')
@login_required
def finance_officer_dashboard():
    if current_user.role != 'Finance Officer':
        return jsonify({"msg": "Unauthorized"}), 403
    return render_template('finance.html')


@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    if current_user.role != 'Finance Officer':
        return jsonify({"msg": "Unauthorized"}), 403

    if request.method == 'POST':
        account_id = request.form.get('AccountID')
        transaction_type = request.form.get('transactionType')
        amount = request.form.get('amount')
        description = request.form.get('description')
        user_id = current_user.user_id
        if account_id and transaction_type and amount and description:
            try:
                with mysql.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO transactions (account_id, transaction_type, transaction_date, transaction_purpose, amount, user_id) VALUES (%s, %s, NOW(), %s, %s, %s)",
                        (account_id, transaction_type, description, float(amount), user_id))
                    mysql.commit()
                    return render_template('finance.html', message="Transaction added successfully.")
            except pymysql.Error as e:
                mysql.rollback()
                print(f"Error adding transaction: {e}")
                return render_template('add transaction.html', error="Database error adding transaction.")
        return render_template('add transaction.html', error="All fields are required.")
    return render_template('add transaction.html')


@app.route('/view_transactions', methods=['GET'])
@login_required
def view_transactions():
    if current_user.role not in ['Auditor', 'Finance Officer']:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        with mysql.cursor() as cursor:
            cursor.execute("SELECT * FROM transactions")
            transactions = cursor.fetchall()
            return render_template('view transaction.html', transactions=transactions)
    except pymysql.Error as e:
        print(f"Error fetching transactions: {e}")
        return render_template('view transaction.html', error="Database error fetching transactions.")

def fetch_transactions():
    try:
        with mysql.cursor() as cursor:
            cursor.execute("SELECT transaction_type, amount, transaction_date FROM transactions")
            transactions_data = cursor.fetchall()
        return transactions_data
    except pymysql.Error as e:
        print(f"Error fetching transactions: {e}")
        return None

# Visualization and Anomaly Detection
@app.route('/visualizations')
@login_required
def visualizations():
    if current_user.role not in ['Auditor', 'Finance Officer']:
        return jsonify({"msg": "Unauthorized"}), 403

    transactions_data = fetch_transactions()
    if not transactions_data:
        return render_template('transaction analysis.html', error="No transaction data available for visualization.")

    df = pd.DataFrame(transactions_data)

    # Print descriptive statistics
    print(df[['amount']].describe())

    # Visualization 1: Transaction type distribution
    transaction_type_counts = df['transaction_type'].value_counts()
    plt.figure()
    sns.barplot(x=transaction_type_counts.index, y=transaction_type_counts.values)
    plt.title("Transaction Type Distribution")
    plt.savefig('static/transaction_type_distribution.png')
    plt.close()

    # Visualization 2: Amount distribution
    plt.figure()
    sns.histplot(df['amount'], kde=True)
    plt.title("Transaction Amount Distribution")
    plt.savefig('static/transaction_amount_distribution.png')
    plt.close()

    # Visualization 3: Amount by transaction type
    amount_by_type = df.groupby("transaction_type")["amount"].sum()
    fig, ax = plt.subplots()
    sns.barplot(x=amount_by_type.index, y=amount_by_type.values, ax=ax)
    plt.xlabel("Transaction Type")
    plt.ylabel("Total Amount")
    plt.savefig('static/transaction_amount_bytype.png')
    plt.close()

    # Visualization 4: Amount by Month
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    df['month'] = df['transaction_date'].dt.strftime('%B')  # Get month names
    amount_by_month = df.groupby('month')['amount'].sum().reindex(
        ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
         "December"])
    plt.figure()
    sns.barplot(x=amount_by_month.index, y=amount_by_month.values)
    plt.title("Total Amount by Month")
    plt.xlabel("Month")
    plt.ylabel("Total Amount")
    plt.savefig('static/transaction_month_by_amount.png')
    plt.close()

    return render_template('transaction analysis.html')



@app.route('/anomaly_detection')
@login_required
def anomaly_detection():
    if current_user.role != 'Auditor':
        return jsonify({"msg": "Unauthorized"}), 403

    try:
        # Load saved anomaly detection model
        if not os.path.exists('trained_model.joblib'):
            return render_template('anomaly.html', error="Anomaly detection model not found.")
        model = joblib.load('trained_model.joblib')

        with mysql.cursor() as cursor:
            cursor.execute("SELECT amount FROM transactions")
            transactions_data = cursor.fetchall()
            df = pd.DataFrame(transactions_data)

            if not df.empty:
                # Predict anomalies
                predictions = model.predict(df[['amount']])
                anomalies = df[predictions == 1]
                anomalies_list = anomalies.to_dict(orient='records')  # Convert to list of dict
                return render_template('anomaly.html', anomalies=anomalies_list)
            else:
                return render_template('anomaly.html',
                                       message="No transaction data available for anomaly detection.")

    except FileNotFoundError:
        return render_template('anomaly.html', error="Anomaly detection model file not found.")
    except Exception as e:
        print(f"Error during anomaly detection: {e}")
        return render_template('anomaly.html', error=str(e))


# Auditor Dashboard
@app.route('/auditor_dashboard')
@login_required
def auditor_dashboard():
    if current_user.role != 'Auditor':
        return jsonify({"msg": "Unauthorized"}), 403
    return render_template('Auditor.html')


@app.route('/back')
def back():
    # Redirect to the previous page. This is a basic implementation.
    # A more robust solution might involve storing the history of visited pages.
    referrer = request.headers.get('Referer')
    if referrer:
        return redirect(referrer)
    else:
        return redirect(url_for('home'))  # Default fallback


if __name__ == '__main__':
    app.run(debug=True)