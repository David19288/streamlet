from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import os
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Strong random secret key for session

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to reach the StreamLet directory, then to users.txt
USER_DATA_FILE = os.path.join(BASE_DIR, '..', 'users.txt')
TRANSACTION_TIMEOUT = 60  # seconds to wait between transactions
user_last_transaction = {}

# Function to save user data
def save_user(username, password, paypal_name, paypal_email, initial_balance=0.0):
    with open(USER_DATA_FILE, 'a') as f:
        f.write(f"{username},{password},{paypal_name},{paypal_email},{initial_balance}\n")

# Function to get user data by username
def get_user_data(username):
    try:
        with open(USER_DATA_FILE, 'r') as f:
            for line in f:
                user_data = line.strip().split(',')
                if user_data[0] == username:
                    return user_data  # Return the entire user data
    except FileNotFoundError:
        # Create the file if it doesn't exist
        with open(USER_DATA_FILE, 'w') as f:
            pass
    return None  # Return None if user is not found

# Function to update user's PayPal info
def update_paypal_info(username, paypal_name, paypal_email):
    with open(USER_DATA_FILE, 'r') as f:
        users = f.readlines()
    
    with open(USER_DATA_FILE, 'w') as f:
        for user in users:
            if user.startswith(username):
                name, pw, _, _, balance = user.strip().split(',')
                f.write(f"{username},{pw},{paypal_name},{paypal_email},{balance}\n")
            else:
                f.write(user)

# Function to update user balance
def update_balance(username, new_balance):
    with open(USER_DATA_FILE, 'r') as f:
        users = f.readlines()
    
    with open(USER_DATA_FILE, 'w') as f:
        for user in users:
            if user.startswith(username):
                data = user.strip().split(',')
                data[-1] = str(new_balance)  # Update the balance
                f.write(','.join(data) + "\n")
            else:
                f.write(user)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        paypal_name = request.form['paypal_name']
        paypal_email = request.form['paypal_email']
        
        # Save the user's details with an initial balance of 0.0
        save_user(username, password, paypal_name, paypal_email, initial_balance=0.0)
        
        # Log the user in by setting the session
        session['username'] = username 
        flash("Successfully signed up!", "success")
        return redirect(url_for('dashboard'))  # Redirect to dashboard after signing up
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = get_user_data(username)
        
        if user_data is not None and user_data[1] == password:
            session['username'] = username
            flash("Successfully logged in!", "success")
            return redirect(url_for('dashboard'))
        else:
            error_message = "Invalid username or password. Please try again."
    
    return render_template('login.html', error_message=error_message)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    user_data = get_user_data(session['username'])
    balance = 0.0
    if user_data:
        balance = user_data[-1]  # Get the balance

    return render_template('dashboard.html', balance=balance)

@app.route('/paypal', methods=['GET', 'POST'])
def paypal():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in
    if request.method == 'POST':
        paypal_name = request.form['paypal_name']
        paypal_email = request.form['paypal_email']
        update_paypal_info(session['username'], paypal_name, paypal_email)
        flash("PayPal information updated successfully!", "success")
        return redirect(url_for('dashboard'))
    return render_template('paypal.html')

@app.route('/watch_ad', methods=['POST'])
def watch_ad():
    if 'username' not in session:
        return {'error': 'Not authenticated'}, 401  # JSON error for fetch callers

    user_data = get_user_data(session['username'])
    if user_data is None:
        return {"error": "User not found"}, 404
        
    balance = float(user_data[-1])
    new_balance = balance + 0.10  # Add earnings from watching the ad
    update_balance(session['username'], new_balance)  # Update user's balance

    return {'new_balance': new_balance}

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Successfully logged out!", "success")
    return redirect(url_for('index'))

@app.route('/pro')
def pro():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in
    return render_template('pro.html')  # Render the Pro Features page

@app.route('/check_balance', methods=['POST'])
def check_balance():
    if 'username' not in session:
        return {'success': False, 'message': 'User not logged in.'}, 401
        
    data = request.get_json()
    duration = data['duration']
    cost = duration * 1  # Change this to whatever your cost is

    user_data = get_user_data(session['username'])
    
    if user_data is None:
        return {'success': False, 'message': 'User not found.'}, 404

    balance = float(user_data[-1])  # Current balance of the user

    if balance < cost:
        # Balance is insufficient
        return {
            'success': False,
            'message': 'Insufficient funds.',
            'balance': balance
        }, 403

    # Deduct the cost from the user's balance
    update_balance(session['username'], balance - cost)

    # Store the bot duration or remaining time in session
    session['bot_duration'] = duration  # Store the duration

    return {'success': True, 'message': f'Bot activated for {duration} hour(s)!'}

@app.route('/search', methods=['GET', 'POST'])
def search():
    return render_template('search.html')

@app.route('/search_user')
def search_user():
    username_query = request.args.get('username', '')
    results = []

    with open(USER_DATA_FILE, 'r') as f:
        for line in f:
            user_data = line.strip().split(',')
            if username_query.lower() in user_data[0].lower():  # Case insensitive search
                results.append({
                    'username': user_data[0],
                    'balance': user_data[-1]  # Assuming balance is the last entry
                })

    return {'results': results}  # Return results as JSON

@app.route('/user/<username>')  # Route to show user details
def user_details(username):
    user_data = get_user_data(username)
    if user_data:
        return render_template('usersearch.html', user_data=user_data)
    else:
        flash("User not found!", "error")
        return redirect(url_for('search'))

@app.route('/send_money', methods=['POST'])
def send_money():
    if 'username' not in session:
        return {'message': 'User not logged in'}, 400

    data = request.get_json()  # Retrieve JSON payload
    sender_username = session['username']
    receiver_username = data.get('receiver_username')  # Use get to avoid KeyError
    amount = data.get('amount')

    if receiver_username is None or amount is None:
        return {'message': 'Invalid request data.'}, 400

    # Validate amount
    try:
        amount = float(amount)  # Ensure amount is a float
    except ValueError:
        return {'message': 'Invalid amount provided.'}, 400

    sender_data = get_user_data(sender_username)
    receiver_data = get_user_data(receiver_username)

    if sender_data is None or receiver_data is None:
        return {'message': 'User not found'}, 404

    sender_balance = float(sender_data[-1])
    receiver_balance = float(receiver_data[-1])

    # Check transaction limits
    current_time = time.time()
    last_transaction_time = user_last_transaction.get(sender_username, 0)

    if (current_time - last_transaction_time) < TRANSACTION_TIMEOUT:
        return {'message': 'You must wait before sending money again.'}, 400

    if amount > sender_balance:
        return {'message': 'Insufficient funds.'}, 400

    # Deduct amount from sender and add to receiver
    new_sender_balance = sender_balance - amount
    new_receiver_balance = receiver_balance + amount

    update_balance(sender_username, new_sender_balance)
    update_balance(receiver_username, new_receiver_balance)

    # Update the last transaction time
    user_last_transaction[sender_username] = current_time

    return {'message': f'Successfully sent €{amount} to {receiver_username}'}

# Serve ads.txt at the root for AdSense verification
@app.route('/ads.txt')
def ads_txt():
    content = "google.com, pub-7224699187685418, DIRECT, f08c47fec0942fa0"
    return Response(content, mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True)