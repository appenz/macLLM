import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

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