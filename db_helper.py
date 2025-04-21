import sqlite3
import json
import hashlib
from datetime import datetime

class DBHelper:
    """Helper class to manage database operations for caching summaries."""
    
    def __init__(self, db_path="ticket_summaries.db"):
        """Initialize the database helper with the specified database path."""
        self.db_path = db_path
        self.init_db()  # Ensure the database and table are initialized

    def init_db(self):
        """Create the summaries table if it does not already exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS summaries (
                    customer_number TEXT,  
                    product TEXT,          
                    content_hash TEXT,     
                    llm_response TEXT,     
                    created_at TIMESTAMP,  
                    PRIMARY KEY (customer_number, product, content_hash)  
                )
            ''')

    def get_cached_summary(self, customer_number, product, content_hash):
        """Retrieve a cached summary from the database if it exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                '''SELECT llm_response FROM summaries 
                   WHERE customer_number = ? AND product = ? AND content_hash = ?''',
                (customer_number, product, content_hash)
            )
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None  # Return the cached summary as a JSON object

    def save_summary(self, customer_number, product, content_hash, llm_response):
        """Save a new summary to the database or update an existing one."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO summaries 
                   (customer_number, product, content_hash, llm_response, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (customer_number, product, content_hash, 
                 json.dumps(llm_response), datetime.now())  # Serialize the LLM response as JSON
            )

def generate_content_hash(df):
    """Generate a unique hash for the content of a dataframe."""
    content_str = df.to_json(orient='records', date_format='iso')  # Convert dataframe to JSON string
    return hashlib.sha256(content_str.encode()).hexdigest()  # Return SHA-256 hash of the content
