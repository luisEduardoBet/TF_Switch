import httpx

response2 = httpx.get("http://127.0.0.1:8000/", headers={"X-Forwarded-For": "203.0.113.195"})
# {"detected_client_ip": "203.0.113.195"}