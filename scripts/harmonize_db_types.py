import os
import re

model_dir = "backend/app/models"
files = [f for f in os.listdir(model_dir) if f.endswith(".py") and f != "__init__.py"]

for filename in files:
    path = os.path.join(model_dir, filename)
    with open(path, 'r') as f:
        content = f.read()
    
    # Replace Integer primary keys with String primary keys
    content = content.replace("id = Column(Integer, primary_key=True, index=True)", "id = Column(String, primary_key=True, index=True)")
    
    # Ensure uuid is imported if we want defaults, or just leave it as String for now
    # to fix the mismatch. PostgreSQL VARCHAR matches SQLAlchemy String.
    
    with open(path, 'w') as f:
        f.write(content)

print("✅ Harmonized primary keys to String in all model files.")
