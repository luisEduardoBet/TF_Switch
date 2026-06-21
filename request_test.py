import httpx


#Teste para uma usuário apto a acessar o sistema (professor no caso)
response = httpx.get("http://127.0.0.1:8000/", headers={"X-Forwarded-For": "192.168.1.10"})
print(response.text)

#Teste para user que não seja professor e tente acessar o sistema

response = httpx.get("http://127.0.0.1:8000/", headers={"X-Forwarded-For": "192.168.1.12"})
print(response.text)


# {"detected_client_ip": "203.0.113.195"}