from flask import render_template, redirect, url_for, request, session, flash
from app import app
import sqlite3
import os

app.secret_key = 'library_app_secret_key'

# connect to the database
DATABASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'library.db')
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    print(f"Connected to database at {DATABASE}")
    return conn

# main page
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Library Management System')

@app.route('/items', methods=['GET', 'POST'])
def items():
    if request.method == 'POST':
        # check if user is logged in or making a donation
        if 'user_id' not in session and request.form.get('form_type') != 'donation':
            return redirect(url_for('register'))
            
        form_type = request.form.get('form_type')
        
        if form_type == 'donation':
            title = request.form.get('title')
            author = request.form.get('author')
            item_type = request.form.get('type')
            branch_id = request.form.get('branch_id')
            
            # add donated item to the database
            if title and author and item_type and branch_id:
                conn = get_db_connection()
                try:
                    conn.execute('''
                        INSERT INTO Item (title, author, type, status, branch_id) 
                        VALUES (?, ?, ?, ?, ?)
                    ''', (title, author, item_type, 'Pending', branch_id))
                    conn.commit()
                except sqlite3.Error as e:
                    print("Error inserting donation into database. Error: ", e)
                    pass
                conn.close()
            return redirect(url_for('items'))
        # returning an item
        elif form_type == 'return':
            item_id = request.form.get('item_id')
            if item_id:
                conn = get_db_connection()
                try:
                    # only allow returning if this user borrowed the item
                    borrowed = conn.execute('''
                        SELECT * FROM Borrowed 
                        WHERE item_id = ? AND cust_id = ?
                    ''', (item_id, session['user_id'])).fetchone()
                    
                    # delete the borrowed record
                    # the triggers in our database automatically update the status of the item
                    if borrowed:
                        conn.execute('DELETE FROM Borrowed WHERE item_id = ?', (item_id,))
                        conn.commit()
                except sqlite3.Error:
                    pass
                conn.close()
            return redirect(url_for('items'))
        else:
            # use current user for borrowing
            item_id = request.form.get('item_id')
            if item_id:
                cust_id = session['user_id']
                conn = get_db_connection()
                item = conn.execute('SELECT * FROM Item WHERE item_id = ?', (item_id,)).fetchone()
                
                if item and item['status'] == 'Available':
                    try:
                        conn.execute('INSERT INTO Borrowed (cust_id, item_id) VALUES (?, ?)', 
                                    (cust_id, item_id))
                        conn.commit()
                    except sqlite3.Error:
                        pass
                conn.close()
                return redirect(url_for('items'))
    
    search_query = request.args.get('search', '')
    conn = get_db_connection()
    
    # searching functionality
    if search_query:
        items = conn.execute('''
            SELECT * FROM Item 
            WHERE title LIKE ? OR author LIKE ? OR type LIKE ?
        ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        items = conn.execute('SELECT * FROM Item').fetchall()
    
    customers = conn.execute('SELECT * FROM Customer').fetchall()
    
    branches = conn.execute('SELECT * FROM Branch').fetchall()
    
    borrowed_items = []
    if 'user_id' in session:
        borrowed_items = conn.execute('''
            SELECT item_id FROM Borrowed WHERE cust_id = ?
        ''', (session['user_id'],)).fetchall()
        borrowed_items = [item['item_id'] for item in borrowed_items]
    
    conn.close()
    return render_template('items.html', title='Library Items', items=items, search_query=search_query, 
                          customers=customers, branches=branches, borrowed_items=borrowed_items)

@app.route('/events', methods=['GET', 'POST'])
def events():
    if request.method == 'POST':
        if 'user_id' not in session:
            return redirect(url_for('register'))
            
        event_id = request.form.get('event_id')
        if event_id:
            cust_id = session['user_id']
            conn = get_db_connection()
            try:
                conn.execute('INSERT INTO Registered (cust_id, event_id) VALUES (?, ?)', 
                            (cust_id, event_id))
                conn.commit()
            except sqlite3.Error:
                pass
            conn.close()
            return redirect(url_for('events'))
    
    search_query = request.args.get('search', '')
    conn = get_db_connection()
    
    if search_query:
        events = conn.execute('''
            SELECT Event.*, Room.capacity, 
                   (SELECT COUNT(*) FROM Registered WHERE Registered.event_id = Event.event_id) as registered_count
            FROM Event 
            JOIN Room ON Event.room_id = Room.room_id
            WHERE event_name LIKE ? OR event_type LIKE ? OR recommended_audience LIKE ?
        ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        events = conn.execute('''
            SELECT Event.*, Room.capacity,
                   (SELECT COUNT(*) FROM Registered WHERE Registered.event_id = Event.event_id) as registered_count
            FROM Event 
            JOIN Room ON Event.room_id = Room.room_id
        ''').fetchall()
    
    customers = conn.execute('SELECT * FROM Customer').fetchall()
    
    registered_events = []
    if 'user_id' in session:
        registered_events = conn.execute('''
            SELECT event_id FROM Registered WHERE cust_id = ?
        ''', (session['user_id'],)).fetchall()
        registered_events = [event['event_id'] for event in registered_events]
    
    conn.close()
    return render_template('events.html', title='Library Events', events=events, 
                          search_query=search_query, customers=customers,
                          registered_events=registered_events)

@app.route('/all_data')
def all_data():
    conn = get_db_connection()
    
    # get everything
    customers = conn.execute('SELECT * FROM Customer').fetchall()
    items = conn.execute('SELECT * FROM Item').fetchall()
    employees = conn.execute('SELECT * FROM Employee').fetchall()
    events = conn.execute('SELECT * FROM Event').fetchall()
    branches = conn.execute('SELECT * FROM Branch').fetchall()
    rooms = conn.execute('SELECT * FROM Room').fetchall()
    borrowed = conn.execute('''
        SELECT Borrowed.*, Customer.first_name, Customer.last_name, Item.title
        FROM Borrowed
        JOIN Customer ON Borrowed.cust_id = Customer.cust_id
        JOIN Item ON Borrowed.item_id = Item.item_id
    ''').fetchall()
    fines = conn.execute('''
        SELECT Fine.*, Customer.first_name, Customer.last_name, Item.title
        FROM Fine
        JOIN Customer ON Fine.cust_id = Customer.cust_id
        LEFT JOIN Item ON Fine.item_id = Item.item_id
    ''').fetchall()
    registered = conn.execute('''
        SELECT Registered.*, Customer.first_name, Customer.last_name, Event.event_name
        FROM Registered
        JOIN Customer ON Registered.cust_id = Customer.cust_id
        JOIN Event ON Registered.event_id = Event.event_id
    ''').fetchall()
    
    conn.close()
    
    return render_template('all_data.html', 
                          title='All Library Data',
                          customers=customers,
                          items=items,
                          employees=employees,
                          events=events,
                          branches=branches,
                          rooms=rooms,
                          borrowed=borrowed,
                          fines=fines,
                          registered=registered)

@app.route('/query', methods=['GET', 'POST'])
def query():
    result = None
    error = None
    query_text = ''
    
    if request.method == 'POST':
        query_text = request.form.get('query', '')
        if query_text:
            conn = get_db_connection()
            try:
                result = conn.execute(query_text).fetchall()
                if result:
                    column_names = result[0].keys()
                else:
                    column_names = []
            except sqlite3.Error as e:
                error = str(e)
                column_names = []
                result = []
            conn.close()
            
            return render_template('query.html', 
                                title='Run Custom Query', 
                                result=result, 
                                column_names=column_names,
                                query=query_text,
                                error=error)
    
    return render_template('query.html', title='Run Custom Query', query=query_text)

@app.route('/staff', methods=['GET', 'POST'])
def staff():  
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'volunteer':
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            branch_id = request.form.get('branch_id')
            
            # add the volunteer to the database, automatically assigning them the 'Volunteer' role
            if first_name and last_name and email and branch_id:
                conn = get_db_connection()
                try:
                    conn.execute('''
                        INSERT INTO Employee (first_name, last_name, email, phone, branch_id, role) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (first_name, last_name, email, phone, branch_id, 'Volunteer'))
                    conn.commit()
                except sqlite3.Error as e:
                    print(e)
                conn.close()
    
    conn = get_db_connection()
    
    employees = conn.execute('''
        SELECT e.*, b.branch_id as branch_name 
        FROM Employee e
        JOIN Branch b ON e.branch_id = b.branch_id
        ORDER BY e.role, e.last_name
    ''').fetchall()
    
    branches = conn.execute('SELECT * FROM Branch').fetchall()
    
    customers = conn.execute('SELECT * FROM Customer').fetchall()
    
    conn.close()
    
    return render_template('staff.html', 
                          title='Library Staff', 
                          employees=employees, 
                          branches=branches, 
                          customers=customers,)

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    message_type = 'info'
    
    if request.method == 'POST':
        action_type = request.form.get('action_type')
        
        if action_type == 'login':

            email = request.form.get('email')
            
            if email:
                conn = get_db_connection()
                customer = conn.execute('SELECT * FROM Customer WHERE email = ?', (email,)).fetchone()
                conn.close()
                
                if customer:
                    session['user_id'] = customer['cust_id']
                    session['user_name'] = f"{customer['first_name']} {customer['last_name']}"
                    session['user_email'] = customer['email']
                    return redirect(url_for('index'))
                else:
                    message = 'No account found with that email. Please register.'
                    message_type = 'error'
            else:
                message = 'Please enter your email.'
                message_type = 'error'
        
        elif action_type == 'register':
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            
            if all([first_name, last_name, email]):
                conn = get_db_connection()
                
                existing = conn.execute('SELECT * FROM Customer WHERE email = ?', (email,)).fetchone()
                
                if existing:
                    message = 'An account with this email already exists. Please sign in.'
                    message_type = 'error'
                else:
                    try:
                        conn.execute('''
                            INSERT INTO Customer (first_name, last_name, email, phone, membership_status) 
                            VALUES (?, ?, ?, ?, ?)
                        ''', (first_name, last_name, email, phone, 'Active'))
                        conn.commit()
                        
                        customer = conn.execute('SELECT * FROM Customer WHERE email = ?', (email,)).fetchone()
                        if customer:
                            session['user_id'] = customer['cust_id']
                            session['user_name'] = f"{customer['first_name']} {customer['last_name']}"
                            session['user_email'] = customer['email']
                            message = 'Registration successful! You are now signed in.'
                            message_type = 'success'
                    except sqlite3.Error as e:
                        print(e)
                        message = 'Registration failed. Please try again.'
                        message_type = 'error'
                
                conn.close()
            else:
                message = 'Please fill out all required fields.'
                message_type = 'error'
    
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    return render_template('register.html', title='Sign In / Register', message=message, message_type=message_type)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    return redirect(url_for('index'))