import streamlit as st
from data_processor import process_data
from summary_generator import generate_summaries, LLMProvider
from timeline_helper import show_timeline_modal
from db_helper import DBHelper, generate_content_hash
import time
import os
import requests

# Fetch available models from the Ollama server
def fetch_ollama_models():
    """Fetch available models from the Ollama server."""
    try:
        response = requests.get('http://ollama:11434/api/tags')
        if response.status_code == 200:
            models = response.json().get('models', [])
            return [model['name'] for model in models]
        else:
            st.error(f"Failed to fetch Ollama models: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Error fetching Ollama models: {str(e)}")
        return []

# Initialize session state variables for the app
def initialize_session_state():
    if 'llm_provider' not in st.session_state:
        st.session_state.llm_provider = LLMProvider.OLLAMA  # Default LLM provider
    if 'db_helper' not in st.session_state:
        st.session_state.db_helper = DBHelper()  # Initialize database helper
    if 'ollama_model' not in st.session_state:
        st.session_state.ollama_model = None  # Default Ollama model

# Main function to define the Streamlit app
def main():
    st.set_page_config(layout="wide")  # Set page layout to wide
    initialize_session_state()  # Initialize session state variables
    
    st.header("System Ticket Data Summary")  # App header
    
    # Initialize filter variables
    selected_customer = []
    selected_product = []
    
    # Sidebar Components
    with st.sidebar:
        # File Upload Section
        st.subheader("File Upload")
        uploaded_file = st.file_uploader("Upload ticket data file", type=['txt', 'csv'])  # File uploader
        
        st.divider()  # Horizontal line separator
        
        # LLM Provider Settings
        st.subheader("LLM Provider Settings")
        provider = st.radio(
            "Select LLM Provider",
            [LLMProvider.OLLAMA, LLMProvider.OPENROUTER],
            index=0 if st.session_state.llm_provider == LLMProvider.OLLAMA else 1
        )
        
        # Update LLM provider in session state and environment variables
        if provider != st.session_state.llm_provider:
            st.session_state.llm_provider = provider
            os.environ["LLM_PROVIDER"] = provider
            
        # Handle OpenRouter-specific settings
        if provider == LLMProvider.OPENROUTER:
            openrouter_key = st.text_input("OpenRouter API Key", type="password")
            if openrouter_key:
                os.environ["OPENROUTER_API_KEY"] = openrouter_key
        
        # Handle Ollama-specific settings
        if provider == LLMProvider.OLLAMA:
            st.divider()
            st.subheader("Ollama Model Selection")
            models = fetch_ollama_models()  # Fetch available Ollama models
            if models:
                selected_model = st.selectbox("Select Ollama Model", models)  # Model selection dropdown
                st.session_state.ollama_model = selected_model
        
        st.info(f"Currently using: {provider}")  # Display selected provider

        # Only show filters if data is loaded
        if 'group_counts' in locals():
            st.divider()  # Horizontal line separator
            
            st.subheader("Filters")
            customers = sorted(group_counts['Customer Number'].unique())  # Get unique customers
            products = sorted(group_counts['Product'].unique())  # Get unique products
            
            # Customer filter
            selected_customer = st.multiselect(
                "Filter by Customer",
                options=customers,
                default=[]
            )
            
            # Product filter
            selected_product = st.multiselect(
                "Filter by Product",
                options=products,
                default=[]
            )
    
    # Main content area - Process uploaded file
    if uploaded_file:
        # Process data with loading indicator
        with st.spinner('Processing data...'):
            grouped_data = process_data(uploaded_file)  # Process uploaded file
        
        if grouped_data is not None:
            
            # Show group statistics
            st.subheader("Data Overview")
            group_counts = grouped_data.size().reset_index()  # Group data and count tickets
            group_counts.columns = ['Customer Number', 'Product', 'Ticket Count']  # Rename columns
            
            # Move filters to sidebar after data is loaded
            with st.sidebar:
                st.divider()
                st.subheader("Filters")
                customers = sorted(group_counts['Customer Number'].unique())
                products = sorted(group_counts['Product'].unique())
                
                # Customer filter
                selected_customer = st.multiselect(
                    "Filter by Customer",
                    options=customers,
                    default=[]
                )
                
                # Product filter
                selected_product = st.multiselect(
                    "Filter by Product",
                    options=products,
                    default=[]
                )
            
            # Expandable section to view group statistics
            with st.expander("View Group Statistics", expanded=False):
                st.dataframe(group_counts)  # Display group statistics
            
            # Filter the grouped data based on selection
            filtered_groups = []
            for group_key, group_df in grouped_data:
                customer_num, product = group_key
                if (not selected_customer or customer_num in selected_customer) and \
                   (not selected_product or product in selected_product):
                    filtered_groups.append((group_key, group_df))  # Add matching groups
            
            # Generate summaries for filtered groups
            st.subheader("Customer Summaries")
            
            if not filtered_groups:
                st.info("No data matches the selected filters.")  # No matching data
                return
            
            # Create progress tracking
            total_groups = len(filtered_groups)
            progress_bar = st.progress(0)  # Progress bar
            status_text = st.empty()  # Status text
            
            try:
                # Process each filtered customer-category group
                for i, (group_key, group_df) in enumerate(filtered_groups):
                    customer_num, product = group_key
                    status_text.text(f'Processing Customer {customer_num} - {product}...')  # Update status
                    
                    # Generate content hash
                    content_hash = generate_content_hash(group_df)
                    
                    # Try to get cached summary
                    cached_summary = st.session_state.db_helper.get_cached_summary(
                        customer_num, product, content_hash
                    )
                    
                    if cached_summary:
                        summary = {product: (cached_summary, False)}  # Use cached summary
                        st.success("Retrieved from cache")
                    else:
                        # Generate new summary
                        summary = generate_summaries(group_df)
                        # Cache the summary
                        if summary:
                            product_summary = next(iter(summary.values()))
                            if not product_summary[1]:
                                st.session_state.db_helper.save_summary(
                                    customer_num, product, content_hash, product_summary[0]
                                )
                    
                    # Update progress and display
                    progress_bar.progress((i + 1) / total_groups)  # Update progress bar
                    product_summary = next(iter(summary.values())) if summary else {}
                    product_summary = product_summary[0] if product_summary else {}
                    show_timeline_modal(product_summary, customer_num, product)  # Show timeline modal
                    
                    time.sleep(0.1)  # Simulate processing delay
            
            except Exception as e:
                st.error(f"Error generating summaries: {str(e)}")  # Handle errors
            
            finally:
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()

# Entry point for the Streamlit app
if __name__ == "__main__":
    main()