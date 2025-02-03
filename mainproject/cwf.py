from flask import Flask, render_template, request, redirect, url_for, flash, session, g ,jsonify
from flask_mysqldb import MySQL
import os
import binascii
from werkzeug.security import check_password_hash

app = Flask(__name__)

# Configure the MySQL connection (for WAMP)
app.config['MYSQL_HOST'] = 'localhost'  # WAMP default MySQL host
app.config['MYSQL_USER'] = 'root'  # Default MySQL user
app.config['MYSQL_PASSWORD'] = ''  # Default password (empty string in WAMP)
app.config['MYSQL_DB'] = 'jnayil_db'  # Replace with your actual database name
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
    if request.method == 'POST':
        # CSRF Token check
        csrf_token = request.form['csrf_token']
        if csrf_token != session.get('csrf_token'):
            flash("Invalid CSRF token. Please try again.", "danger")
       
        
        customer_id = request.form['customer_id']
        password = request.form['password']
        
        g.user = customer_id
        
        # Query the database for user authentication
        cur = mysql.connection.cursor()
        cur.execute("SELECT password FROM users WHERE customer_id = %s", (customer_id,))
        user = cur.fetchone()
        print(user)
        
        if user[0] == password :
            # Store user session
            session['customer_id'] = customer_id
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials. Please try again.", "danger")
    
    # Generate a CSRF token and store it in the session
    session['csrf_token'] = binascii.hexlify(os.urandom(32)).decode()
    
    return render_template('login.html')

# Route for the dashboard after login
@app.route('/dashboard')
def dashboard():
    if 'customer_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('landing_page.html')

@app.route('/logout')
def logout():
    return render_template('login.html')

from flask import Response
import json

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
    # # Convert the list of invoices to a JSON string
    # response_data = json.dumps(invoice_data_list)
    
    # # Return the invoice details as JSON response
    # return Response(response_data, status=200, mimetype='application/json')

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
    
# Main block to run the Flask application
if __name__ == '__main__':
    app.run(host='0.0.0.0' ,debug=True)