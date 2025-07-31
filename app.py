import sqlite3
from sqlite3 import Error

# --- Database Functions ---
def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect('S:/Study/projects/financial_tracker/finance.db')
    except Error as e:
        print(e)
    return conn

def init_db(conn):
    """Initialize the database and create the transactions table if it doesn't exist."""
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('expense', 'saving')),
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    except Error as e:
        print(e)

def add_transaction(conn, transaction_type, description, amount):
    """Add a new transaction to the database."""
    sql = ''' INSERT INTO transactions(type,description,amount)
              VALUES(?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, (transaction_type, description, amount))
        conn.commit()
        print(f"Successfully added {transaction_type}: {description} - ${amount:.2f}")
    except Error as e:
        print(f"Failed to add transaction: {e}")


def get_transactions(conn):
    """Query and return all transactions from the database."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT type, description, amount, timestamp FROM transactions ORDER BY timestamp DESC")
        return cur.fetchall()
    except Error as e:
        print(f"Failed to retrieve transactions: {e}")
        return []

# --- CLI Functions ---
def get_user_input():
    """Get transaction details from the user."""
    description = input("Enter description: ")
    while True:
        try:
            amount = float(input("Enter amount: "))
            if amount <= 0:
                print("Amount must be positive.")
                continue
            return description, amount
        except ValueError:
            print("Invalid amount. Please enter a number.")

def view_summary(conn):
    """Display a summary of all transactions."""
    print("\n--- Financial Summary ---")
    transactions = get_transactions(conn)
    if not transactions:
        print("No transactions yet.")
        return

    total_expenses = 0
    total_savings = 0

    print("\nExpenses:")
    for t in transactions:
        if t[0] == 'expense':
            print(f"  - {t[3]} | {t[1]}: ${t[2]:.2f}")
            total_expenses += t[2]

    print("\nSavings:")
    for t in transactions:
        if t[0] == 'saving':
            print(f"  - {t[3]} | {t[1]}: ${t[2]:.2f}")
            total_savings += t[2]

    print("\n-------------------------")
    print(f"Total Expenses: ${total_expenses:.2f}")
    print(f"Total Savings:  ${total_savings:.2f}")
    print(f"Net Balance:    ${total_savings - total_expenses:.2f}")
    print("-------------------------\n")


def main():
    """Main function to run the CLI application."""
    conn = create_connection()
    if conn is None:
        print("Error! Cannot create the database connection.")
        return

    init_db(conn)

    while True:
        print("\nFinancial Tracker Menu:")
        print("1. Add Expense")
        print("2. Add Saving")
        print("3. View Summary")
        print("4. Exit")
        choice = input("Enter your choice (1-4): ")

        if choice == '1':
            print("\n--- Add New Expense ---")
            description, amount = get_user_input()
            add_transaction(conn, 'expense', description, amount)
        elif choice == '2':
            print("\n--- Add New Saving ---")
            description, amount = get_user_input()
            add_transaction(conn, 'saving', description, amount)
        elif choice == '3':
            view_summary(conn)
        elif choice == '4':
            print("Exiting application. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")

    if conn:
        conn.close()

if __name__ == '__main__':
    main()
