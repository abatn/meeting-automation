import re
from typing import Tuple, List

def validate_password(password: str) -> Tuple[bool, List[str]]:
    """
    Validates password strength.
    Returns (is_valid, errors) where errors is a list of error messages.
    """
    errors = []
    
    # Minimum length check
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    # Uppercase check
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    # Lowercase check
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    # Number check
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number")
    
    # Special character check (optional)
    # if not re.search(r'[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]', password):
    #     errors.append("Password must contain at least one special character")
    
    return len(errors) == 0, errors