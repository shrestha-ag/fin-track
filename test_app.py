import pytest
from app import app, init_db
import sqlite3
import os
import tempfile

@pytest.fixture
def client(monkeypatch):
    """Create and configure a new app instance for each test."""
    db_fd, db_path = tempfile.mkstemp()
    
    app.config.update({
        "TESTING": True,
        "DATABASE": db_path,
    })

    # Override the create_connection to use the temp db for the duration of the test
    def get_test_db_connection():
        conn = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.row_factory = sqlite3.Row
        return conn
    
    monkeypatch.setattr('app.create_connection', get_test_db_connection)

    with app.app_context():
        init_db()

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)


def test_index_loads(client):
    """Test that the index page loads correctly."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Financial Tracker" in response.data

def test_add_transaction_with_labels(client):
    """Test adding a transaction with multiple labels."""
    test_date = "2023-10-26"
    response = client.post('/add', data={
        'type': 'expense',
        'description': 'Groceries',
        'amount': '75.50',
        'transaction_date': test_date,
        'labels': 'food, shopping'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Groceries" in response.data
    assert b"$75.50" in response.data
    assert test_date.encode('utf-8') in response.data
    assert b'<span class="label">food</span>' in response.data
    assert b'<span class="label">shopping</span>' in response.data

def test_filter_by_label(client):
    """Test filtering transactions by a specific label."""
    client.post('/add', data={
        'type': 'expense', 'description': 'Restaurant', 'amount': '45',
        'transaction_date': '2023-11-01', 'labels': 'food, dining'
    })
    client.post('/add', data={
        'type': 'expense', 'description': 'Gas', 'amount': '50',
        'transaction_date': '2023-11-02', 'labels': 'car'
    })

    response = client.get('/?label=food')
    assert response.status_code == 200
    assert b"Restaurant" in response.data
    assert b"Gas" not in response.data

    response = client.get('/?label=car')
    assert response.status_code == 200
    assert b"Restaurant" not in response.data
    assert b"Gas" in response.data
    
    response = client.get('/')
    assert b"Restaurant" in response.data
    assert b"Gas" in response.data

def test_edit_transaction_with_labels(client):
    """Test editing a transaction's details and labels."""
    client.post('/add', data={
        'type': 'saving', 'description': 'Initial Deposit', 'amount': '500',
        'transaction_date': '2023-01-01', 'labels': 'banking'
    })

    response = client.post('/update/1', data={
        'type': 'saving',
        'description': 'Updated Deposit',
        'amount': '550.50',
        'transaction_date': '2023-01-02',
        'labels': 'banking, bonus'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Initial Deposit" not in response.data
    assert b"Updated Deposit" in response.data
    assert b"550.50" in response.data
    assert b"2023-01-02" in response.data
    assert b'<span class="label">banking</span>' in response.data
    assert b'<span class="label">bonus</span>' in response.data

def test_delete_transaction(client):
    """Test deleting a transaction."""
    client.post('/add', data={
        'type': 'expense', 'description': 'Lunch', 'amount': '15',
        'transaction_date': '2023-11-11', 'labels': 'food'
    })
    
    response = client.get('/')
    assert b"Lunch" in response.data

    response = client.get('/delete/1', follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Lunch" not in response.data
    assert b"Total Expenses: <span class=\"expense\">$0.00</span>" in response.data
