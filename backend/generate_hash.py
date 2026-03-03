from app.core.security import get_password_hash

password = "test123"
hashed = get_password_hash(password)
print(f"Password: {password}")
print(f"Hash: {hashed}")
