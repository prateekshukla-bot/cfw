from flask import Flask, render_template, request, redirect, url_for, flash, session, g ,jsonify
from flask_mysqldb import MySQL
import os
import binascii
from flask import Response
import json
app = Flask(__name__)

# Configure the MySQL connection (for WAMP)
app.config['MYSQL_HOST'] = 'localhost'  # WAMP default MySQL host
app.config['MYSQL_USER'] = 'root'  # Default MySQL user
app.config['MYSQL_PASSWORD'] = ''  # Default password (empty string in WAMP)
app.config['MYSQL_DB'] = 'jnil_db'  # Replace with your actual database name
app.config['SECRET_KEY'] = os.urandom(24)  # For CSRF protection
mysql = MySQL(app)


@app.before_request
def before_request():
    if 'customer_id' in session:
        g.user = session['customer_id']  # Set g.user to the logged-in user's customer_id
    else:
        g.user = None  # No user logged in


# Route for the login page
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None  # Initialize error variable
    if request.method == 'POST':
        csrf_token = request.form['csrf_token']
        if csrf_token != session.get('csrf_token'):
            error = "Invalid CSRF token. Please try again."
            return render_template('login.html', error=error)
        
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user_type']  # "customer" or "admin"

        cur = mysql.connection.cursor()
        
        if user_type == "customer":
            # Authenticate customer
            cur.execute("SELECT password FROM users WHERE customer_id = %s", (username,))
            user = cur.fetchone()
            if user and user[0] == password:  # Replace with proper password hashing in production
                session['customer_id'] = username
                flash("Customer login successful!", "success")
                return redirect(url_for('dashboard'))
            else:
                error = "Invalid customer credentials!"
        elif user_type == "admin":
            # Authenticate admin
            cur.execute("SELECT id, password FROM admin_users WHERE username = %s", (username,))
            admin = cur.fetchone()
            if admin and admin[1] == password:  # Replace with proper password hashing in production
                session['admin_id'] = admin[0]
                session['admin_username'] = username
                flash("Admin login successful!", "success")
                return redirect(url_for('admin_dashboard'))
            else:
                error = "Invalid admin credentials!"

        cur.close()

    # Generate a new CSRF token for security
    session['csrf_token'] = binascii.hexlify(os.urandom(32)).decode()
    return render_template('login.html', error=error)

# Route for the dashboard after login
@app.route('/dashboard')
def dashboard():
    if 'customer_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    return render_template('landing_page.html')

@app.route('/logout')
def logout():
    session.clear()  # Clears all session data
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))



@app.route('/fetch_invoices')
def fetch_invoices():
    cur = mysql.connection.cursor()
    # Execute the SQL query and fetch all rows
    cur.execute("SELECT customer_id, invoice_number, status FROM pending_invoices WHERE customer_id = %s", (g.user,))
    invoices = cur.fetchall()  # fetchall retrieves all rows

    # Process the data to format it into a list of dictionaries
    invoice_data = [
        {"invoice_number": invoice[1], "customer_id": invoice[0], "status": invoice[2]} 
        for invoice in invoices
    ]
    
    # Close the cursor after fetching the data
    cur.close()

    # Manually serialize the data to JSON and return as a Response object
    response_data = json.dumps(invoice_data)

    return Response(response_data, mimetype='application/json')  # Return as JSON with the correct MIME type

import MySQLdb  # or use your database connector as per your setup
@app.route('/fetch_invoice_details/<invoice_number>', methods=['GET'])
def fetch_invoice_details(invoice_number):
    try:
        cur = mysql.connection.cursor()
        
        # Modified query to select distinct records
        query = """
            SELECT DISTINCT
                invoice_number,
                invoice_item,
                invoice_date,
                customer,
                customer_name,
                invoice_quantity,
                COALESCE(received_quantity, 0) as received_quantity,
                material,
                material_description,
                sales_unit,
                COALESCE(remark, '') as remark
            FROM invoices 
            WHERE invoice_number = %s
        """
        
        cur.execute(query, (invoice_number,))
        
        # Fetch all matching records
        invoices = cur.fetchall()

        invoice_data_list = []
        for invoice in invoices:
            invoice_data = {
                'invoice_number': invoice[0],
                'invoice_item': invoice[1],
                'invoice_date': invoice[2].strftime('%Y-%m-%d') if invoice[2] else '',
                'customer': invoice[3],
                'customer_name': invoice[4],
                'invoice_quantity': str(invoice[5]) if invoice[5] is not None else '0',
                'received_quantity': str(invoice[6]) if invoice[6] is not None else '0',
                'material': invoice[7],
                'material_description': invoice[8],
                'sales_unit': invoice[9],
                'remark': invoice[10] if invoice[10] is not None else ''
            }
            invoice_data_list.append(invoice_data)

        cur.close()
        return jsonify(invoice_data_list)

    except Exception as e:
        print(f"Error in fetch_invoice_details: {str(e)}")
        return jsonify({"error": str(e)}), 500
  
@app.route('/update_invoice_details/<invoice_number>', methods=['POST'])
def update_invoice_details(invoice_number):
    try:
        # Get the JSON data from the request
        data = request.get_json()
        
        # Extract the invoice details
        invoice_number = data.get('invoice_number')
        details = data.get('details')

        if not invoice_number or not details:
            return jsonify({"status": "error", "message": "Invoice number or details missing"}), 400

        # Create a cursor to execute SQL queries
        cur = mysql.connection.cursor()

        # Iterate over each detail and update the corresponding invoice details
        for detail in details:
            received_quantity = detail.get('received_quantity')
            remark = detail.get('remark')

            # SQL query to update the invoice details and change status
            update_query = """
                UPDATE invoices i
                JOIN pending_invoices p ON i.invoice_number = p.invoice_number
                SET 
                    i.received_quantity = %s, 
                    i.remark = %s,
                    p.status = 'Paid'
                WHERE i.invoice_number = %s 
            """

            # Execute the update query
            cur.execute(update_query, (received_quantity, remark, invoice_number))

        # Commit the changes to the database
        mysql.connection.commit()

        # Close the cursor
        cur.close()

        # Respond with a success message
        return jsonify({"status": "success", "message": "Invoice details updated and status changed to Paid."})
    
    except MySQLdb.MySQLError as e:
        # If something goes wrong with the database
        mysql.connection.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    
    except Exception as e:

        # General error handling
        return jsonify({"status": "error", "message": str(e)}), 400
    

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'customer_id' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    # Validate inputs
    if not current_password or not new_password:
        return jsonify({"status": "error", "message": "Current and new passwords are required"}), 400

    try:
        cur = mysql.connection.cursor()
        
        # Verify current password
        cur.execute("SELECT password FROM users WHERE customer_id = %s", (session['customer_id'],))
        user = cur.fetchone()

        if not user or user[0] != current_password:
            return jsonify({"status": "error", "message": "Current password is incorrect"}), 400

        # Update password
        update_query = "UPDATE users SET password = %s WHERE customer_id = %s"
        cur.execute(update_query, (new_password, session['customer_id']))
        
        # Commit changes
        mysql.connection.commit()
        cur.close()

        return jsonify({"status": "success", "message": "Password changed successfully"})

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    
    # Admin routes
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, password FROM admin_users WHERE username = %s", (username,))
        admin = cur.fetchone()
        cur.close()

        if admin and password == admin[2]:  # Replace with check_password_hash(admin[2], password) for security
            session['admin_id'] = admin[0]
            session['admin_username'] = admin[1]
            flash("Login successful!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid username or password", "danger")

    return render_template('admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash("Admin access required.", "warning")
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        # Fetch total users count
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        # Fetch pending invoices count
        cur.execute("SELECT COUNT(*) FROM invoices WHERE status = 'Pending'")
        pending_invoices = cur.fetchone()[0]
        # Fetch total invoices count (Pending + Paid)
        cur.execute("SELECT COUNT(*) FROM invoices WHERE status IN ('Pending', 'Paid')")
        total_invoices = cur.fetchone()[0]

        cur.close()
    except MySQLdb.MySQLError:
        user_count = 0  # Fallback if there's an error
        pending_invoices = 0  # Fallback if there's an error
        total_invoices = 0  

    return render_template(
        'admin_dashboard.html', 
        user_count=user_count,
        pending_invoices=pending_invoices, 
        total_invoices=total_invoices
    )

@app.route('/admin/logout')
def admin_logout():
    print("Before clearing session:", dict(session))
    session.clear()
    print("After clearing session:", dict(session))
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

@app.route('/admin/get_users')
def get_users():
    if 'admin_id' not in session:
        return jsonify({"error": "Unauthorized access"}), 401

    print("Admin is logged in")  # Debugging line
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT customer_id, name FROM users")
        users = cur.fetchall()
        cur.close()

        print("Fetched users:", users)  # Debugging line

        users_list = [{"customer_id": u[0], "name": u[1]} for u in users]

        return jsonify(users_list)
    
    except Exception as e:
        print("Error fetching users:", str(e))  # Debugging line
        return jsonify({"error": str(e)}), 500
    
@app.route('/admin/edit_user', methods=['POST'])
def edit_user():
    if 'admin_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized access"}), 401

    data = request.get_json()
    customer_id = data.get('customer_id')
    new_name = data.get('name')

    if not customer_id or not new_name:
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET name = %s WHERE customer_id = %s", (new_name, customer_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({"status": "success", "message": "User updated successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/admin/delete_user', methods=['POST'])
def delete_user():
    if 'admin_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized access"}), 401

    data = request.get_json()
    customer_id = data.get('customer_id')
    if not customer_id:
        return jsonify({"status": "error", "message": "Customer ID is required"}), 400
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM users WHERE customer_id = %s", (customer_id,))
        mysql.connection.commit()
        cur.close()

        return jsonify({"status": "success", "message": "User deleted successfully"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/get_invoices')
def get_invoices():
    if 'admin_id' not in session:
        return jsonify({"error": "Unauthorized access"}), 401

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, invoice_number, invoice_item, invoice_date, customer, customer_name, 
               invoice_quantity, material, material_description, sales_unit, 
               received_quantity, remark, status
        FROM invoices
    """)
    invoices = cur.fetchall()
    cur.close()

    invoices_list = [{
        "id": i[0],
        "invoice_number": i[1],
        "invoice_item": i[2],
        "invoice_date": i[3].strftime('%Y-%m-%d') if i[3] else '',
        "customer": i[4],
        "customer_name": i[5],
        "invoice_quantity": i[6],
        "material": i[7],
        "material_description": i[8],
        "sales_unit": i[9],
        "received_quantity": i[10],
        "remark": i[11],
        "status": i[12]
    } for i in invoices]

    return jsonify(invoices_list)



@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if 'admin_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized access"}), 401

    try:
        data = request.get_json()  # Ensure this is correct depending on your front-end
        customer_id = data.get('customer_id')
        name = data.get('name')
        password = data.get('password')  # Replace with hashing for security

        if not customer_id or not name or not password:
            return jsonify({"status": "error", "message": "All fields are required"}), 400

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (customer_id, name, password) VALUES (%s, %s, %s)", 
                    (customer_id, name, password))
        mysql.connection.commit()
        cur.close()

        return jsonify({"status": "success", "message": "User added successfully"})
    
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/admin/reports/invoices')
def report_pending_invoices():
    if 'admin_id' not in session:
        return jsonify({"error": "Unauthorized access"}), 401

    cur = mysql.connection.cursor()
    query = """
        SELECT DATE(invoice_date) as date, COUNT(*) as count 
        FROM invoices 
        WHERE status = 'Pending' 
        GROUP BY DATE(invoice_date)
        ORDER BY DATE(invoice_date);
    """
    cur.execute(query)
    data = cur.fetchall()
    cur.close()

    result = [{"date": row[0].strftime('%Y-%m-%d'), "count": row[1]} for row in data]
    return jsonify(result)

@app.route('/admin/reports/status')
def report_invoice_status():
    if 'admin_id' not in session:
        return jsonify({"error": "Unauthorized access"}), 401

    cur = mysql.connection.cursor()
    query = """
        SELECT status, COUNT(*) as count 
        FROM invoices 
        GROUP BY status;
    """
    cur.execute(query)
    data = cur.fetchall()
    cur.close()

    result = [{"status": row[0], "count": row[1]} for row in data]
    return jsonify(result)

@app.route('/search_users', methods=['GET'])
def search_users():
    query = request.args.get('query', '').strip()
    cur = mysql.connection.cursor()
    
    search_query = "%" + query + "%"
    sql = "SELECT customer_id, name FROM users WHERE customer_id LIKE %s OR name LIKE %s"

    cur.execute(sql, (search_query, search_query))
    users = cur.fetchall()
    cur.close()

    users_list = [{"customer_id": user[0], "name": user[1]} for user in users]

    return jsonify(users_list)

@app.route('/admin/change_password', methods=['POST'])
def admin_change_password():
    if 'admin_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized access"}), 401

    data = request.get_json()
    customer_id = data.get('customer_id')
    new_password = data.get('new_password')

    if not customer_id or not new_password:
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET password = %s WHERE customer_id = %s", (new_password, customer_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({"status": "success", "message": "Password changed successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Main block to run the Flask application
if __name__ == '__main__':
    print(app.url_map)  # This will show all the registered routes
    app.run(host='0.0.0.0', debug=True)
