from datetime import datetime
import re
import json
import streamlit as st
from streamlit_timeline import timeline

def llm_to_timeline_dict(llm_dict: dict, title: str = "Customer Ticket Timeline"):
    """
    Convert LLM-generated summary data into a timeline-compatible dictionary.
    
    Args:
        llm_dict: Dictionary containing LLM-generated summaries.
        title: Title for the timeline.
    
    Returns:
        A dictionary formatted for the Streamlit timeline component.
    """
    def extract_date(content):
        """
        Extract a date from the content using regex.
        
        Args:
            content: Content containing a potential date.
        
        Returns:
            A dictionary with year, month, and day if a date is found, otherwise None.
        """
        if isinstance(content, dict):
            timeframe = content.get('timeframe', '')
            match = re.search(r"(\d{4}-\d{2}-\d{2})", timeframe)
        else:
            match = re.search(r"\*\*Timeframe\*\*:\s*(\d{4}-\d{2}-\d{2})", str(content))
        
        if match:
            dt = datetime.strptime(match.group(1), "%Y-%m-%d")
            return {"year": dt.year, "month": dt.month, "day": dt.day}
        return None

    def format_text_content(text):
        """
        Format text content by converting markdown-style bold text to HTML.
        
        Args:
            text: The text content to format.
        
        Returns:
            Formatted text with HTML tags.
        """
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b><hr>', text)  # Convert bold text
        return text.replace("\n", "<br>")  # Replace newlines with HTML line breaks

    events = []  # List to store timeline events
    last_valid_date = None  # Track the last valid date for fallback

    for section_title, content in llm_dict.items():
        # Extract date and format content based on its type
        if isinstance(content, dict):
            date_info = extract_date(content)
            text_content = f"""
                <b>Timeframe</b>: {content.get('timeframe', 'N/A')}<hr>
                <b>Ticket Numbers</b>: {', '.join(content.get('ticket_numbers', []))}<hr>
                <b>Narrative</b>: {content.get('narrative', 'N/A')}
            """
        else:
            date_info = extract_date(content)
            text_content = format_text_content(str(content))

        # Use the last valid date if no date is found
        if date_info is None:
            date_info = last_valid_date or {"year": 2024, "month": 1, "day": 1}
        else:
            last_valid_date = date_info

        # Add the event to the timeline
        events.append({
            "start_date": date_info,
            "text": {
                "headline": section_title,
                "text": text_content
            }
        })

    # Return the timeline dictionary
    return {
        "title": {
            "text": {
                "headline": title,
                "text": "Chronological view of customer issues and resolutions"
            }
        },
        "events": events
    }

def show_timeline_modal(summary, customer_num, product):
    """
    Display a timeline view in an expandable Streamlit component.
    
    Args:
        summary: The summary data to display in the timeline.
        customer_num: The customer number associated with the summary.
        product: The product associated with the summary.
    """
    with st.expander(f"Timeline View - Customer {customer_num} - {product}", expanded=True):
        # Convert the summary into timeline-compatible data
        timeline_data = llm_to_timeline_dict(
            summary,
            f"Customer {customer_num} - {product} Timeline"
        )
        # Render the timeline in the Streamlit app
        timeline(json.dumps(timeline_data), height=400)