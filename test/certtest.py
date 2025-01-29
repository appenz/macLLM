import os
import openai
import requests
import ssl
import socket
import certifi
import pprint
from urllib.parse import urlparse

def get_certificate_info(hostname, port=443):
    context = ssl.create_default_context(cafile=certifi.where())
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            return cert

def test_simple_request():
    # Get API key from environment variable
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key is None:
        raise Exception("OPENAI_API_KEY not found in environment variables")
    
    # Get certificate information before making the request
    api_hostname = urlparse("https://api.openai.com").netloc
    cert_info = get_certificate_info(api_hostname)

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(cert_info)

    
    # Initialize OpenAI client
    client = openai.OpenAI(api_key=openai_api_key)
    
    # Create chat completion
    response = client.chat.completions.create(
        model="gpt-4",  # or another model of your choice
        messages=[
            {"role": "user", "content": "Capital of France?"}
        ],
        temperature=0.0
    )
    
    # Get the response
    result = response.choices[0].message.content
    print(f"\nResponse: {result}")

if __name__ == "__main__":
    test_simple_request()
