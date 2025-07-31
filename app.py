import sqlite3
from sqlite3 import Error
from flask import Flask, render_template, request, redirect, url_for, flash
import datetime
import json
import csv
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flashing messages

# --- Database Functions ---
def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect('finance.db', check_same_thread=False)
    except Error as e:
        print(e)
    return conn

def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = create_connection()
    if conn is None:
        print("Error! Cannot create the database connection.")
        return
        
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('expense', 'saving')),
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_date TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS transaction_labels (
                transaction_id INTEGER,
                label_id INTEGER,
                PRIMARY KEY (transaction_id, label_id),
                FOREIGN KEY (transaction_id) REFERENCES transactions (id) ON DELETE CASCADE,
                FOREIGN KEY (label_id) REFERENCES labels (id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    except Error as e:
        print(f"Database initialization error: {e}.")
    finally:
        if conn:
            conn.close()

def get_or_create_label(cur, label_name):
    """Get the id of a label, creating it if it doesn't exist, using the provided cursor."""
    cur.execute("SELECT id FROM labels WHERE name = ?", (label_name,))
    label = cur.fetchone()
    if label:
        return label[0]
    else:
        cur.execute("INSERT INTO labels (name) VALUES (?)", (label_name,))
        return cur.lastrowid

def add_transaction_db(transaction_type, description, amount, transaction_date, labels_str):
    """Add a new transaction to the database."""
    conn = create_connection()
    sql = ''' INSERT INTO transactions(type,description,amount,transaction_date)
              VALUES(?,?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, (transaction_type, description, amount, transaction_date))
        trans_id = cur.lastrowid
        
        if labels_str:
            label_names = [label.strip() for label in labels_str.split(',') if label.strip()]
            for name in label_names:
                label_id = get_or_create_label(cur, name)
                if label_id:
                    cur.execute("INSERT INTO transaction_labels (transaction_id, label_id) VALUES (?, ?)", (trans_id, label_id))
        
        conn.commit()
    except Error as e:
        print(f"Failed to add transaction: {e}")
    finally:
        if conn:
            conn.close()

def update_transaction_db(trans_id, trans_type, description, amount, transaction_date, labels_str):
    """Update an existing transaction in the database."""
    conn = create_connection()
    sql = ''' UPDATE transactions
              SET type = ? ,
                  description = ? ,
                  amount = ? ,
                  transaction_date = ?
              WHERE id = ?'''
    try:
        cur = conn.cursor()
        cur.execute(sql, (trans_type, description, amount, transaction_date, trans_id))
        
        cur.execute("DELETE FROM transaction_labels WHERE transaction_id = ?", (trans_id,))
        if labels_str:
            label_names = [label.strip() for label in labels_str.split(',') if label.strip()]
            for name in label_names:
                label_id = get_or_create_label(cur, name)
                if label_id:
                    cur.execute("INSERT INTO transaction_labels (transaction_id, label_id) VALUES (?, ?)", (trans_id, label_id))

        conn.commit()
    except Error as e:
        print(f"Failed to update transaction: {e}")
    finally:
        if conn:
            conn.close()

def delete_transaction_db(trans_id):
    """Delete a transaction from the database by transaction id."""
    conn = create_connection()
    sql = 'DELETE FROM transactions WHERE id=?'
    try:
        cur = conn.cursor()
        cur.execute(sql, (trans_id,))
        conn.commit()
    except Error as e:
        print(f"Failed to delete transaction: {e}")
    finally:
        if conn:
            conn.close()

def get_transactions_db(label_filter=None):
    """Query and return all transactions from the database, with optional label filtering."""
    conn = create_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        sql = """
            SELECT t.id, t.type, t.description, t.amount, t.transaction_date, t.timestamp,
                   GROUP_CONCAT(l.name) as labels
            FROM transactions t
            LEFT JOIN transaction_labels tl ON t.id = tl.transaction_id
            LEFT JOIN labels l ON tl.label_id = l.id
        """
        params = []
        if label_filter:
            sql += " WHERE t.id IN (SELECT transaction_id FROM transaction_labels tl JOIN labels l ON tl.label_id = l.id WHERE l.name = ?)"
            params.append(label_filter)

        sql += " GROUP BY t.id ORDER BY t.transaction_date DESC"

        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows
    except Error as e:
        print(f"Failed to retrieve transactions: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_transaction_by_id_db(trans_id):
    """Query and return a single transaction by its id, with labels."""
    conn = create_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.type, t.description, t.amount, t.transaction_date,
                   GROUP_CONCAT(l.name) as labels
            FROM transactions t
            LEFT JOIN transaction_labels tl ON t.id = tl.transaction_id
            LEFT JOIN labels l ON tl.label_id = l.id
            WHERE t.id = ?
            GROUP BY t.id
        """, (trans_id,))
        row = cur.fetchone()
        return row
    except Error as e:
        print(f"Failed to retrieve transaction: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_all_labels_db():
    """Query and return all labels from the database."""
    conn = create_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM labels ORDER BY name")
        rows = cur.fetchall()
        return rows
    except Error as e:
        print(f"Failed to retrieve labels: {e}")
        return []
    finally:
        if conn:
            conn.close()


# --- Flask Routes ---
@app.route('/')
def index():
    """Main page, displays all transactions and a summary."""
    label_filter = request.args.get('label')
    transactions = get_transactions_db(label_filter=label_filter)
    labels = get_all_labels_db()
    
    total_savings = sum(t['amount'] for t in transactions if t['type'] == 'saving')
    total_expenses = sum(t['amount'] for t in transactions if t['type'] == 'expense')
    net_balance = total_savings - total_expenses
    
    totals = {
        'savings': total_savings,
        'expenses': total_expenses,
        'net': net_balance
    }
    
    today = datetime.date.today().isoformat()
    
    return render_template('index.html', transactions=transactions, totals=totals, today=today, labels=labels, selected_label=label_filter)

@app.route('/add', methods=['POST'])
def add_transaction_route():
    """Handles adding a new transaction from the form."""
    trans_type = request.form['type']
    description = request.form['description']
    amount = float(request.form['amount'])
    transaction_date = request.form['transaction_date']
    labels_str = request.form.get('labels', '')
    
    add_transaction_db(trans_type, description, amount, transaction_date, labels_str)
    
    return redirect(url_for('index'))

@app.route('/edit/<int:trans_id>')
def edit_transaction_route(trans_id):
    """Displays the form to edit a transaction."""
    transaction = get_transaction_by_id_db(trans_id)
    if transaction is None:
        return "Transaction not found", 404
    return render_template('edit_transaction.html', transaction=transaction)

@app.route('/update/<int:trans_id>', methods=['POST'])
def update_transaction_route(trans_id):
    """Handles updating a transaction."""
    trans_type = request.form['type']
    description = request.form['description']
    amount = float(request.form['amount'])
    transaction_date = request.form['transaction_date']
    labels_str = request.form.get('labels', '')
    
    update_transaction_db(trans_id, trans_type, description, amount, transaction_date, labels_str)
    
    return redirect(url_for('index'))

@app.route('/delete/<int:trans_id>')
def delete_transaction_route(trans_id):
    """Handles deleting a transaction."""
    delete_transaction_db(trans_id)
    return redirect(url_for('index'))

@app.route('/import', methods=['POST'])
def import_transactions_route():
    """Handles importing transactions from a JSON or CSV file."""
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('index'))
        
    if file and file.filename.endswith('.json'):
        try:
            transactions = json.load(file)
            for t in transactions:
                add_transaction_db(
                    t.get('type'),
                    t.get('description'),
                    t.get('amount'),
                    t.get('transaction_date'),
                    t.get('labels', '')
                )
            flash('Transactions imported successfully from JSON!', 'success')
        except json.JSONDecodeError:
            flash('Invalid JSON file.', 'error')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
    elif file and file.filename.endswith('.csv'):
        try:
            # Use io.TextIOWrapper to ensure correct decoding
            csv_file = io.TextIOWrapper(file.stream, encoding='utf-8')
            reader = csv.DictReader(csv_file)
            for row in reader:
                add_transaction_db(
                    row.get('type'),
                    row.get('description'),
                    float(row.get('amount')),
                    row.get('transaction_date'),
                    row.get('labels', '')
                )
            flash('Transactions imported successfully from CSV!', 'success')
        except Exception as e:
            flash(f'An error occurred while importing the CSV file: {e}', 'error')
    else:
        flash('Invalid file type. Please upload a .json or .csv file.', 'error')

    return redirect(url_for('index'))

# --- Initialization ---
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
