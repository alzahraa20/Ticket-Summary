import pandas as pd
from io import StringIO
import streamlit as st

# Define valid service categories for filtering
VALID_CATEGORIES = ['HDW', 'NET', 'KAI', 'KAV', 'GIGA', 'VOD', 'KAD']

# Map service categories to product names
CATEGORY_MAPPING = {
    'KAI': 'Broadband',
    'NET': 'Broadband',
    'KAV': 'Voice',
    'KAD': 'TV',
    'GIGA': 'GIGA',
    'VOD': 'VOD',
    'HDW': 'HDW' # Remains the same as it is not mentioned in the mapping instructions
}

def process_data(file):
    """
    Process and clean the uploaded ticket data file.
    
    Args:
        file: The uploaded file object containing ticket data.
    
    Returns:
        grouped_data: A grouped DataFrame by customer number and product.
    """
    try:
        # Read the text file content
        content = file.getvalue().decode('utf-8')
        
        # Convert the text content into a structured DataFrame
        df = pd.read_csv(StringIO(content))
        
        # Filter rows to include only valid service categories
        df = df[df['SERVICE_CATEGORY'].isin(VALID_CATEGORIES)]
        
        # Map service categories to product names
        df['product'] = df['SERVICE_CATEGORY'].map(CATEGORY_MAPPING)
        
        # Convert timestamp columns to datetime format
        timestamp_columns = ['ACCEPTANCE_TIME', 'COMPLETION_TIME']
        for col in timestamp_columns:
            df[col] = pd.to_datetime(df[col])
        
        # Sort the data by acceptance time within each group
        df = df.sort_values(['ACCEPTANCE_TIME'])
        
        # Group the data by customer number and product
        grouped_data = df.groupby(['CUSTOMER_NUMBER', 'product'])
        
        return grouped_data  # Return the grouped data for further processing
        
    except Exception as e:
        # Display an error message in the Streamlit app if processing fails
        st.error(f"Error processing file: {str(e)}")
        return None

def parse_ticket_row(row):
    """
    Parse a single row of ticket data.
    
    Args:
        row: A string representing a single row of ticket data.
    
    Returns:
        A dictionary containing parsed ticket information or None if parsing fails.
    """
    # Placeholder implementation for parsing a row
    # Modify this function based on the actual data format
    parts = row.split(',')
    if len(parts) >= 4:
        return {
            'ticket_id': parts[0],       # Extract ticket ID
            'timestamp': parts[1],      # Extract timestamp
            'category': parts[2],       # Extract category
            'description': parts[3]     # Extract description
        }
    return None  # Return None if the row format is invalid
