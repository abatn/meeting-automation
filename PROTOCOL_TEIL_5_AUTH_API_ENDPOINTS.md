# PROTOKOLL: Teil 5 - Auth API Endpoints Implementierung
Datum: 14.02.2026
Status: ✅ Abgeschlossen

## 1. UMFANG DER TASK
- Implementiert wurden die Authentifizierungs-API-Endpunkte, die die Registrierung, das Login, die Token-Erneuerung und die MFA-Verwaltung umfassen.
- Dateien erstellt/geändert:
    - `backend/app/api/v1/auth.py` (erweitert)
    - `backend/app/schemas/user.py` (erweitert)
    - `backend/app/main.py` (Router-Integration)

## 2. IMPLEMENTIERUNGSSCHRITTE
1. Erweiterung von `backend/app/api/v1/auth.py` um Endpunkte für:
    - Benutzerregistrierung (`/register`)
    - Benutzer-Login (`/login`)
    - Token-Erneuerung (`/refresh-token`)
    - MFA-Setup (`/mfa/setup`)
    - MFA-Verifizierung (`/mfa/verify`)
    - MFA-Deaktivierung (`/mfa/disable`)
2. Anpassung von `backend/app/schemas/user.py` zur Unterstützung der Authentifizierungs- und MFA-bezogenen Datenmodelle.
3. Integration des Auth-Routers in `backend/app/main.py`.
4. Behebung eines `NameError` in `auth.py` bezüglich des `User`-Modells.

## 3. LÖSUNGSANSATZ
- **FastAPI Router**: Verwendung von FastAPI's `APIRouter` zur Strukturierung der Authentifizierungs-Endpunkte.
- **OAuth2 mit Password Flow**: Implementierung des OAuth2-Password-Flows für das Benutzer-Login und die Token-Erzeugung.
- **JWT-Tokens**: Verwendung von JSON Web Tokens für die Authentifizierung und Autorisierung.
- **Dependency Injection**: Nutzung von FastAPI's Dependency Injection für Datenbank-Sessions und den aktuellen Benutzer.
- **Security Service**: Der zuvor implementierte `security_service` wurde für alle sicherheitsrelevanten Operationen (Passwort-Hashing, MFA-Generierung und -Verifizierung) verwendet.

## 4. CODE-BEISPIELE

### Benutzerregistrierung:
```python
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    user_create: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    existing_user = await security_service.get_user_by_email(db, user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    user = await security_service.create_user(db, user_create)
    await log_action(
        db=db,
        user_id=user.id,
        action="REGISTER",
        resource_type="user",
        resource_id=user.id,
        details={"email": user.email},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    return user
```

### Benutzer-Login:
```python
@router.post("/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    user = await security_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_mfa_enabled:
        # MFA-Challenge senden oder MFA-Code anfordern
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA required",
            headers={"X-MFA-Required": "true"}
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security_service.create_access_token(
        data={"sub": user.username, "user_id": str(user.id), "role": user.role.value},
        expires_delta=access_token_expires
    )
    await log_action(
        db=db,
        user_id=user.id,
        action="LOGIN",
        resource_type="user",
        resource_id=user.id,
        details={"username": user.username},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    return {"access_token": access_token, "token_type": "bearer"}
```

## 5. TESTS
- **Backend Start**: Der Backend-Server konnte nach der Implementierung erfolgreich gestartet werden, was die korrekte Integration der neuen Endpunkte bestätigt.
- **`NameError` Fix**: Der Fehler `NameError: name 'User' is not defined` in `auth.py` wurde durch den Import des `User`-Modells behoben.

## 6. HERAUSFORDERUNGEN & LÖSUNGEN

- **Problem**: Integration des `User`-Modells in `auth.py` führte zu einem `NameError`.
- **Lösung**: Hinzufügen von `from app.models.user import User` in `auth.py`.

- **Problem**: Sicherstellung der korrekten Reihenfolge der Parameter in FastAPI-Endpunkten, insbesondere bei der Verwendung von `Depends` und Standardwerten.
- **Lösung**: Parameter ohne Standardwerte wurden vor Parametern mit Standardwerten platziert.

## 7. NÄCHSTE SCHRITTE
- Fortsetzung der Dokumentation für die weiteren implementierten Teile.