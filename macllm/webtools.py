import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os

def retrieve_url(url: str) -> str:

    # Validate URL
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise ValueError("Invalid URL format")
    except Exception as e:
        raise ValueError(f"Invalid URL: {str(e)}")

    # Download content
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
    except requests.RequestException as e:
        raise requests.RequestException(f"Failed to retrieve URL: {str(e)}")

    # Parse HTML and extract text
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Remove script and style elements
    for element in soup(['script', 'style', 'header', 'footer', 'nav']):
        element.decompose()
    
    # Get text and clean it up
    text = soup.get_text(separator='\n')
    
    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text 

def read_file(filepath: str) -> str:

    MAX_SIZE = 10 * 1024  # 10KB in bytes
    
    try:
        # Try to read file as text
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(MAX_SIZE)  # Only read up to MAX_SIZE bytes
            
            # Check for null bytes which indicate binary content
            if '\0' in content:
                raise ValueError("File appears to be binary")
                
            return content
            
    except UnicodeDecodeError:
        raise ValueError("File appears to be binary")
    except IOError as e:
        raise IOError(f"Failed to read file: {str(e)}") 