from flask import Flask, render_template, request, redirect, url_for, session,flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'car_booking'
mysql = MySQL(app)

# Home Route
@app.route('/')
def index():
    return render_template('index.html')


# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                    (username, email, password))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['is_admin'] = user[4] if len(user) > 4 else False  # Assuming column 4 is is_admin
            if session['is_admin']:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        return "Invalid Credentials"
    return render_template('login.html')

# Dashboard (List Available Cars)
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM cars WHERE available=1")
    cars = cur.fetchall()
    
    # Get user's bookings
    cur.execute("""
        SELECT bookings.*, cars.name, booking_details.source_location, 
        booking_details.destination, booking_details.mobile_number, bookings.status
        FROM bookings 
        JOIN cars ON bookings.car_id = cars.id
        JOIN booking_details ON bookings.id = booking_details.booking_id
        WHERE bookings.user_id = %s
        ORDER BY bookings.id DESC
    """, (session['user_id'],))
    bookings = cur.fetchall()
    cur.close()
    return render_template('dashboard.html', cars=cars, bookings=bookings)


# Admin Dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    
    # Get all cars
    cur.execute("SELECT * FROM cars")
    cars = cur.fetchall()
    
    # Get all bookings with user and booking details
    cur.execute("""
        SELECT bookings.*, users.username, cars.name as car_name,
        booking_details.mobile_number, booking_details.source_location,
        booking_details.destination
        FROM bookings 
        JOIN users ON bookings.user_id = users.id 
        JOIN cars ON bookings.car_id = cars.id
        JOIN booking_details ON bookings.id = booking_details.booking_id
        ORDER BY bookings.start_date DESC
    """)
    bookings = cur.fetchall()
    
    cur.close()
    return render_template('admin_dashboard.html', cars=cars, bookings=bookings)


@app.route('/admin/approve_booking/<int:booking_id>')
def approve_booking(booking_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("UPDATE bookings SET status = 'approved' WHERE id = %s", (booking_id,))
    mysql.connection.commit()
    cur.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_booking/<int:booking_id>')
def reject_booking(booking_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("UPDATE bookings SET status = 'rejected' WHERE id = %s", (booking_id,))
    mysql.connection.commit()
    cur.close()
    
    return redirect(url_for('admin_dashboard'))
# Add Car Route
@app.route('/admin/add_car', methods=['POST'])
def add_car():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        model = request.form['model']
        price_per_day = request.form['price_per_day']
        image_url = request.form['image_url']
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO cars (name, model, price_per_day, available, image_url) 
            VALUES (%s, %s, %s, TRUE, %s)
        """, (name, model, price_per_day, image_url))
        mysql.connection.commit()
        cur.close()
        
    return redirect(url_for('admin_dashboard'))

# Delete Car Route
@app.route('/admin/delete_car/<int:car_id>')
def delete_car(car_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM cars WHERE id = %s", (car_id,))
    mysql.connection.commit()
    cur.close()
    
    return redirect(url_for('admin_dashboard'))

# Booking a Car

@app.route('/book/<int:car_id>', methods=['POST'])
def book(car_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    mobile_number = request.form['mobile_number']
    source_location = request.form['source']
    destination = request.form['destination']
    
    cur = mysql.connection.cursor()
    
    # Calculate price
    cur.execute("SELECT price_per_day FROM cars WHERE id=%s", (car_id,))
    price_per_day = cur.fetchone()[0]
    total_price = (int(end_date.split('-')[2]) - int(start_date.split('-')[2])) * price_per_day
    
    # Insert booking with pending status
    cur.execute("""
        INSERT INTO bookings (user_id, car_id, start_date, end_date, total_price, status) 
        VALUES (%s, %s, %s, %s, %s, 'pending')
    """, (user_id, car_id, start_date, end_date, total_price))
    mysql.connection.commit()
    
    # Get the booking id
    booking_id = cur.lastrowid
    
    # Insert booking details
    cur.execute("""
        INSERT INTO booking_details (booking_id, mobile_number, source_location, destination)
        VALUES (%s, %s, %s, %s)
    """, (booking_id, mobile_number, source_location, destination))
    mysql.connection.commit()
    
    cur.close()
    flash('Booking request sent for approval')
    return redirect(url_for('dashboard'))
# Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
