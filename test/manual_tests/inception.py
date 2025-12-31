import os
import requests

api_key = os.getenv("INCEPTION_API_KEY")
if api_key is None:
    raise Exception("INCEPTION_API_KEY not found in environment variables")

response = requests.post(
    'https://api.inceptionlabs.ai/v1/chat/completions',
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    },
    json={
        'model': 'mercury',
        'messages': [
            {'role': 'user', 'content': 'Write a haiku about the weather'}
        ],
        'max_tokens': 1000
    }
)
data = response.json()

print(data)