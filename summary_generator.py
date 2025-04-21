from datetime import datetime
import requests
import os
import json
import pandas as pd
import time
from functools import wraps

class LLMProvider:
    """Class to define supported LLM providers."""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"

def retry_with_delay(max_retries=3, delay_seconds=2):
    """
    Decorator to retry a function with a delay in case of failure.
    
    Args:
        max_retries: Maximum number of retries.
        delay_seconds: Delay between retries in seconds.
    
    Returns:
        The result of the function if successful, or an error summary after retries.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            last_error = None
            
            while retries < max_retries:
                try:
                    result, is_error = func(*args, **kwargs)
                    if not is_error:
                        return result, False  # Return result if no error
                    last_error = result.get("Initial Issue", {}).get("narrative", "Unknown error")
                except Exception as e:
                    last_error = str(e)
                
                retries += 1
                if retries < max_retries:
                    time.sleep(delay_seconds)  # Wait before retrying
            
            # Return error summary after exhausting retries
            return create_error_summary(f"After {max_retries} retries: {last_error}"), True
        return wrapper
    return decorator

def get_llm_provider():
    """
    Get the configured LLM provider from environment variables or session state.
    
    Returns:
        The name of the LLM provider.
    """
    import streamlit as st
    return os.getenv("LLM_PROVIDER", st.session_state.get('llm_provider', LLMProvider.OLLAMA))

def generate_summaries(df):
    """
    Generate structured summaries for each product category in the DataFrame.
    
    Args:
        df: DataFrame containing ticket data.
    
    Returns:
        A dictionary of summaries for each product.
    """
    summaries = {}
    
    for product in df['product'].unique():
        product_tickets = df[df['product'] == product]  # Filter tickets for the product
        if not product_tickets.empty:
            summaries[product] = generate_product_summary(product_tickets)  # Generate summary
    
    return summaries

def generate_product_summary(tickets):
    """
    Generate a structured summary for a specific product category.
    
    Args:
        tickets: DataFrame containing tickets for a specific product.
    
    Returns:
        A tuple containing the summary and an error flag.
    """
    prompt = create_summary_prompt(tickets)  # Create a prompt for the LLM
    provider = get_llm_provider()  # Get the configured LLM provider
    
    if provider == LLMProvider.OPENROUTER:
        summary, is_error = get_openrouter_summary(prompt)  # Use OpenRouter for summary generation
    else:
        import streamlit as st
        selected_model = st.session_state.get('ollama_model', "qwen2.5:7b")  # Default model if none selected
        summary, is_error = get_ollama_summary(prompt, model=selected_model)  # Use Ollama for summary generation
    
    return summary, is_error

def create_summary_prompt(tickets):
    """
    Create a structured prompt for the LLM to ensure consistent output.
    
    Args:
        tickets: DataFrame containing ticket data.
    
    Returns:
        A string prompt formatted for the LLM.
    """
    # Convert DataFrame to a list of dictionaries
    tickets_data = tickets.to_dict('records')
    
    # Convert timestamps to string format and handle missing values
    for ticket in tickets_data:
        for key, value in ticket.items():
            if isinstance(value, pd.Timestamp):
                ticket[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            elif pd.isna(value):
                ticket[key] = "N/A"
    
    formatted_tickets = json.dumps(tickets_data, indent=2, default=str)  # Serialize tickets to JSON
    
    # Create a detailed prompt for the LLM
    prompt = f"""
    Analyze these ticket records for a single customer and service category:
    {formatted_tickets}

    Create a chronological summary with these sections, focusing on the customer's experience:

    1. Initial Issue:
        - Timeframe: Identify the period when the initial issues began.
        - Ticket Numbers: List the relevant ticket numbers.
        - Narrative: Describe the customer's initial problems, including the nature of the issues, the customer's feedback, and any immediate actions taken.

    2. Follow-ups:
        - Timeframe: Document the period of follow-up activities.
        - Ticket Numbers: List the related ticket numbers.
        - Narrative: Detail the follow-up actions, including further customer interactions, additional feedback, and any responses from the support team.

    3. Developments:
        - Timeframe: Specify the period during which significant developments occurred.
        - Ticket Numbers: List the relevant ticket numbers.
        - Narrative: Explain the developments, such as new issues arising, advancements in resolving existing problems, and any changes in customer experiences.

    4. Later Incidents:
        - Timeframe: Note the timeframe for later incidents.
        - Ticket Numbers: List the related ticket numbers.
        - Narrative: Describe recurring issues or new problems that emerged, including how they were handled and the customer's ongoing feedback.

    5. Recent Events:
        - Timeframe: Highlight the most recent period.
        - Ticket Numbers: List the relevant ticket numbers.
        - Narrative: Provide a summary of the latest events, including current issues, recent resolutions, and the customer's final feedback.

    Format as JSON:
    {{
        "Initial Issue": {{
            "timeframe": "date range",
            "ticket_numbers": ["list of relevant tickets"],
            "narrative": "detailed description"
        }},
        "Follow-ups": {{ same structure }},
        "Developments": {{ same structure }},
        "Later Incidents": {{ same structure }},
        "Recent Events": {{ same structure }}
    }}

    Guidelines:
    - Focus on this specific customer's experience with this service category
    - Maintain chronological order
    - Include relevant ticket numbers
    - Use clear, professional language
    - Highlight patterns or recurring issues
    """
    return prompt

@retry_with_delay(max_retries=3, delay_seconds=2)
def get_ollama_summary(prompt, model="qwen2.5:7b"):
    """
    Generate a summary using the Ollama LLM.
    
    Args:
        prompt: The prompt to send to the LLM.
        model: The model to use for summary generation.
    
    Returns:
        A tuple containing the summary and an error flag.
    """
    try:
        response = requests.post(
            'http://ollama:11434/api/generate/',
            json={
                "model": model,
                "prompt": prompt,
                "system": "You are a technical support analyst. Always respond with valid JSON.",
                "format": "json",
                "stream": False,
                "temperature": 0.1,
                "options": {
                    "num_ctx": 4096
                    }
            }
        )

        if response.status_code == 200:
            result = response.json()['response']

            # Parse the response as JSON
            try:
                return json.loads(result), False
            except json.JSONDecodeError:
                # Attempt to extract JSON from the response if parsing fails
                import re
                json_match = re.search(r'{.*}', result, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group()), False
                return create_error_summary("Invalid JSON response from Ollama"), True
        return create_error_summary(f"Ollama Error: Status code {response.status_code}"), True
    except Exception as e:
        return create_error_summary(f"Ollama Error: {str(e)}"), True

@retry_with_delay(max_retries=3, delay_seconds=2)
def get_openrouter_summary(prompt, model="qwen/qwen2.5-vl-72b-instruct:free"):
    """
    Generate a summary using the OpenRouter LLM.
    
    Args:
        prompt: The prompt to send to the LLM.
        model: The model to use for summary generation.
    
    Returns:
        A tuple containing the summary and an error flag.
    """
    try:
        # Required headers for OpenRouter API
        headers = {
            "Authorization": "Bearer " + os.getenv("OPENROUTER_API_KEY", ""),
            "Content-Type": "application/json",
        }

        # Prepare the payload for the API request
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        # Make the API request
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            # Extract the content from the assistant's message
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                # Remove markdown code block markers if present
                content = content.replace('```json', '').replace('```', '').strip()
                try:
                    # Parse the JSON content
                    parsed_json = json.loads(content)
                    return parsed_json, False
                except json.JSONDecodeError as e:
                    return create_error_summary(f"Failed to parse OpenRouter response: {str(e)}"), True
            else:
                return create_error_summary("No valid content in OpenRouter response"), True
        else:
            return create_error_summary(f"OpenRouter Error: {response.status_code} - {response.text}"), True
            
    except Exception as e:
        return create_error_summary(f"OpenRouter Error: {str(e)}"), True

def create_error_summary(error_message):
    """
    Create a structured error summary.
    
    Args:
        error_message: The error message to include in the summary.
    
    Returns:
        A dictionary representing the error summary.
    """
    return {
        "Initial Issue": {
            "timeframe": "N/A",
            "ticket_numbers": [],
            "narrative": error_message
        },
        "Follow-ups": {
            "timeframe": "N/A",
            "ticket_numbers": [],
            "narrative": "Not available due to error"
        },
        "Developments": {
            "timeframe": "N/A",
            "ticket_numbers": [],
            "narrative": "Not available due to error"
        },
        "Later Incidents": {
            "timeframe": "N/A",
            "ticket_numbers": [],
            "narrative": "Not available due to error"
        },
        "Recent Events": {
            "timeframe": "N/A",
            "ticket_numbers": [],
            "narrative": "Not available due to error"
        }
    }
