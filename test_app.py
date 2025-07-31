import pytest
from app import app, init_db, create_connection
import os
import tempfile

@pytest.fixture
def client():
    """Create and configure a new app instance for each test."""
    # Create a temporary file to act as the database
    db_fd, db_path = tempfile.mkstemp()
    
    # Configure the app for testing
    app.config.update({
        "TESTING": True,
        "DATABASE": db_path,
    })

    # Create the database and the tables
    with app.app_context():
        # Override the create_connection to use the temp db
        def get_test_db_connection():
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        
        # This is a bit of a hack, but for this small app it's fine.
        # In a larger app, you'd structure the connection handling to be more easily mockable.
        app.create_connection = get_test_db_connection
        init_db()


    # Yield the test client
    with app.test_client() as client:
        yield client

    # Close and remove the temporary database
    os.close(db_fd)
    os.unlink(db_path)


def test_index_loads(client):
    """Test that the index page loads correctly."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Financial Tracker" in response.data
    assert b"Add New Transaction" in response.data
    assert b"Transactions" in response.data
    assert b"Summary" in response.data

def test_add_transaction_and_verify(client):
    """Test adding a new transaction and verifying it appears on the page."""
    # First, add an expense
    response = client.post('/add', data={
        'type': 'expense',
        'description': 'Test Expense',
        'amount': '50.00'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Test Expense" in response.data
    assert b"$50.00" in response.data
    assert b"Total Expenses: <span class=\"expense\">$50.00</span>" in response.data
    assert b"Net Balance: <span>$-50.00</span>" in response.data

    # Then, add a saving
    response = client.post('/add', data={
        'type': 'saving',
        'description': 'Test Saving',
        'amount': '100.00'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Test Saving" in response.data
    assert b"$100.00" in response.data
    assert b"Total Savings: <span class=\"saving\">$100.00</span>" in response.data
    assert b"Total Expenses: <span class=\"expense\">$50.00</span>" in response.data
    assert b"Net Balance: <span>$50.00</span>" in response.data