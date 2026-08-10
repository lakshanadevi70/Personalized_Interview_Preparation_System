def register(client): return client.post("/api/auth/register", json={"name": "Student One", "email": "student@example.com", "password": "SecurePass123"})
def test_registration(client):
    response = register(client); assert response.status_code == 201; assert response.json()["access_token"]
def test_duplicate_email(client): register(client); assert register(client).status_code == 409
def test_login(client):
    register(client); assert client.post("/api/auth/login", json={"email": "student@example.com", "password": "SecurePass123"}).status_code == 200
def test_invalid_password(client):
    register(client); assert client.post("/api/auth/login", json={"email": "student@example.com", "password": "wrong"}).status_code == 401
def test_authenticated_me(client):
    token = register(client).json()["access_token"]; response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}); assert response.status_code == 200; assert response.json()["email"] == "student@example.com"; assert "password_hash" not in response.json()
def test_unauthenticated_me(client): assert client.get("/api/auth/me").status_code == 401
def test_database_initialization(client): assert client.get("/health").json() == {"status": "ok"}
