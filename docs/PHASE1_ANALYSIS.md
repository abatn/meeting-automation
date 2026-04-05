# Phase 1: Kunden-Onboarding - Vollständige Analyse

## 1.1 Zusammenfassung der Probleme

### 🔴 KRITISCH (P1)

**P1-1: Self-Service-Registrierung fehlt ActivationToken + E-Mail**
- **Datei**: `backend/app/api/v1/auth.py:125-213` (register Endpoint)
- **Problem**: User wird sofort mit `status=ACTIVE` erstellt (Zeile 172), kein ActivationToken, keine E-Mail
- **Impact**: ISO 27001 Compliance verletzt (keine Email-Verifikation), Security Risk (keine Zugangskontrolle)

**P1-2: Fehlende DB-Transaktion-Sicherheit**
- **Datei**: `backend/app/api/v1/auth.py:162-201`
- **Problem**: 
  - Zeile 162-163: `db.add(new_client)` + `await db.flush()` → Client wird persistent
  - Zeile 166-199: User wird erstellt
  - Zeile 201: `await db.commit()` → beides wird committet
  - **Wenn User-Erstellung fehlschlägt** (z.B. FK-Constraint, DB-Error) nach Client flush → Client bleibt in DB ohne User! Datenleck!
- **Korrektur**: Alles erst nach vollständiger Validierung committen, oder SAVEPOINT verwenden

**P1-3: Kein AuditLog für Client-Erstellung**
- **Datei**: `backend/app/api/v1/auth.py:155-163` 
- **Problem**: `db.add(new_client)` ohne `AuditService.log_action()`
- **Impact**: ISO 27001 Compliance Requirement verletzt (keine Nachvollziehbarkeit)

**P1-4: Kein n8n user-invited Webhook bei Self-Service-Registrierung**
- **Datei**: `backend/app/api/v1/auth.py` (fehlt komplett)
- **Problem**: `trigger_user_invited_webhook()` wird nur in `team_service.py:160-165` aufgerufen
- **Impact**: Landing-Page Registrierungen erhalten KEINE Einladungs-E-Mail

**P1-5: Keine Email-Konflikt-Prüfung zwischen users und team_members**
- **Datei**: `backend/app/api/v1/auth.py:125-213` (fehlt)
- **Problem**: auth.register prüft NICHT ob Email bereits in `team_members` Tabelle existiert
- **Vergleich**: `team_service.py:99-105` macht diese Prüfung und löscht bestehenden TeamMember
- **Impact**: Dieselbe Email kann sowohl in `users` (registriert) als auch `team_members` (nur Kontakt) existieren → Inkonsistenz

## 1.2 Korrektur-Referenz: team_service.py:create_team_member

**korrekte Implementierung** (Zeilen 74-178):

```python
async def create_team_member(self, client_id: str, obj_in: TeamMemberCreate, creator_id: str) -> User:
    # 1. Security Check (Zeilen 76-78)
    if obj_in.role in ["system_admin", "tech_admin"]:
        raise ValueError("Unauthorized role assignment.")
    
    # 2. Prüfe ob Email bereits in users existiert (Zeilen 81-93)
    stmt = select(User).where(User.email == obj_in.email)
    res = await self.db.execute(stmt)
    existing_user = res.scalar_one_or_none()
    
    if existing_user:
        if existing_user.status != UserStatus.DISABLED.value:
            raise ValueError("A user with this email already exists and is active or pending.")
        
        # Re-activate DISABLED user
        existing_user.status = UserStatus.PENDING.value  # ✅ PENDING, nicht ACTIVE!
        existing_user.full_name = obj_in.full_name
        existing_user.hashed_password = "PENDING_USER_NO_PASSWORD"
        new_user = existing_user
        
        # Delete old tokens
        await self.db.execute(delete(ActivationToken).where(ActivationToken.user_id == new_user.id))
        await self.db.flush()
    else:
        # 3. Prüfe ob Email in team_members existiert (Zeilen 99-105)
        stmt_tm = select(TeamMember).where(TeamMember.email == obj_in.email, TeamMember.client_id == client_id)
        res_tm = await self.db.execute(stmt_tm)
        existing_tm = res_tm.scalar_one_or_none()
        if existing_tm:
             await self.db.delete(existing_tm)
             await self.db.flush()
        
        # 4. Create NEW PENDING User (Zeilen 108-117)
        new_user = User(
            id=str(uuid.uuid4()),
            client_id=client_id,
            email=obj_in.email,
            full_name=obj_in.full_name,
            hashed_password="PENDING_USER_NO_PASSWORD",  # ✅ Kein echtes Passwort
            status=UserStatus.PENDING.value,  # ✅ PENDING!
            is_superuser=False,
            is_mfa_enabled=False
        )
    
    # 5. Assign Role (Zeilen 120-137)
    role_stmt = select(Role).where(Role.name == obj_in.role)
    role_res = await self.db.execute(role_stmt)
    role_obj = role_res.scalar_one_or_none()
    if not role_obj:
        role_stmt = select(Role).where(Role.name == "participant")
        role_res = await self.db.execute(role_stmt)
        role_obj = role_res.scalar_one()
    
    new_user.roles = [role_obj]
    
    if not existing_user:
        self.db.add(new_user)
    
    await self.db.flush()
    
    # 6. ActivationToken erstellen (Zeilen 139-148)
    token = secrets.token_urlsafe(32)
    expiration = datetime.now(timezone.utc) + timedelta(days=7)
    activation_entry = ActivationToken(
        id=str(uuid.uuid4()),
        user_id=new_user.id,
        token=token,
        expires_at=expiration
    )
    self.db.add(activation_entry)
    
    # 7. Client laden für Company Name (Zeilen 150-153)
    client_stmt = select(Client).where(Client.id == client_id)
    client_res = await self.db.execute(client_stmt)
    client_obj = client_res.scalar_one()
    
    # 8. ALTE Version: Commit + Refresh (Zeile 155-156)
    await self.db.commit()
    await self.db.refresh(new_user)
    
    # 9. Webhook triggern (Zeilen 158-165)
    activation_link = f"{settings.FRONTEND_URL}/activate?token={token}"
    await trigger_user_invited_webhook(
        email=new_user.email,
        full_name=new_user.full_name or "Colleague",
        company_name=client_obj.company_name,
        activation_link=activation_link
    )
    
    # 10. AuditLog (Zeilen 167-176)
    await AuditService.log_action(
        self.db, 
        client_id=client_id, 
        action="RE_INVITE_USER" if existing_user else "INVITE_USER", 
        user_id=creator_id,
        table_name="users",
        record_id=new_user.id,
        new_values={"email": new_user.email, "status": new_user.status}
    )
    
    return new_user
```

## 1.3 Detaillierter Code-Vergleich

### auth.py:register ( Defizitär )

```python
# Zeilen 125-213 (Original)
@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    *, db: AsyncSession = Depends(deps.get_db), user_in: UserCreate
) -> Any:
    user_result = await db.execute(
        select(UserModel).where(UserModel.email == user_in.email)
    )
    user = user_result.scalar_one_or_none()
    if user:
        raise HTTPException(  # ✅ Duplicate-Check OK
            status_code=400,
            detail="The user with this username already exists in the system.",
        )

    from app.models.client import Client, SubscriptionStatus, SubscriptionPlan
    
    client_id = user_in.client_id
    if not client_id:
        client_id = str(uuid.uuid4())
        plan_enum = SubscriptionPlan.GRATUIT
        minutes = 600
        
        if user_in.plan == "PRO":
            plan_enum = SubscriptionPlan.PRO
            minutes = 3000
        elif user_in.plan == "ENTREPRISE":
            plan_enum = SubscriptionPlan.ENTREPRISE
            minutes = 12000
            
        new_client = Client(
            id=client_id,
            company_name=user_in.company_name or f"{user_in.full_name or user_in.email}'s Company",
            subscription_plan=plan_enum,
            subscription_status=SubscriptionStatus.ACTIVE,
            minutes_included=minutes
        )
        db.add(new_client)  # ❌ Wird sofort hinzugefügt
        await db.flush()     # ❌ Flush -> Client ist persistent (aber noch kein Commit)
    
    # Create user with string ID
    db_obj = UserModel(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),  # ✅ Hash OK
        full_name=user_in.full_name,
        status=UserStatus.ACTIVE.value,  # ❌ ACTIVE statt PENDING!
        is_superuser=False,
        is_mfa_enabled=False,
        created_at=datetime.now(datetime.timezone.utc) if hasattr(datetime, "UTC") else datetime.utcnow(),
    )
    
    # Determine role...
    if not user_in.client_id:
        target_role = "dg"
    else:
        target_role = user_in.role or "participant"
    
    role_result = await db.execute(
        select(RoleModel).where(RoleModel.name == target_role)
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {target_role}. Please contact administrator."
        )
    
    db_obj.roles = [role]
    db.add(db_obj)
    await db.flush()
    
    await db.commit()  # ❌ Alles wird committet, aber kein Rollback möglich wenn Client schon flush()
    await db.refresh(db_obj)
    
    return User(...)  # ✅ Response OK
```

**Fehlende Schritte:**
1. ❌ Keine Prüfung auf `team_members` Tabelle (wie in team_service.py:99-105)
2. ❌ `status=UserStatus.ACTIVE` statt `PENDING`
3. ❌ Kein ActivationToken erstellt
4. ❌ Kein `trigger_user_invited_webhook()` Aufruf
5. ❌ Kein `AuditService.log_action()` für Client oder User
6. ❌ Transaktions-Sicherheit: Client wird vor User-Check hinzugefügt → Bei User-Fehler bleibt Client

### team_service.py:create_team_member ( Korrekte Vorlage )

```python
# Zeilen 74-178 (Korrekte Implementierung)
async def create_team_member(self, client_id: str, obj_in: TeamMemberCreate, creator_id: str) -> User:
    # ✅ 1. Security Check
    if obj_in.role in ["system_admin", "tech_admin"]:
        raise ValueError("Unauthorized role assignment.")
    
    # ✅ 2. Check users table (Zeilen 81-93)
    stmt = select(User).where(User.email == obj_in.email)
    res = await self.db.execute(stmt)
    existing_user = res.scalar_one_or_none()
    
    if existing_user:
        if existing_user.status != UserStatus.DISABLED.value:
            raise ValueError("A user with this email already exists and is active or pending.")
        
        existing_user.status = UserStatus.PENDING.value  # ✅ PENDING
        existing_user.full_name = obj_in.full_name
        existing_user.hashed_password = "PENDING_USER_NO_PASSWORD"  # ✅ Kein User-Passwort needed
        new_user = existing_user
        
        await self.db.execute(delete(ActivationToken).where(ActivationToken.user_id == new_user.id))
        await self.db.flush()
    else:
        # ✅ 3. Check team_members table (Zeilen 99-105)
        stmt_tm = select(TeamMember).where(TeamMember.email == obj_in.email, TeamMember.client_id == client_id)
        res_tm = await self.db.execute(stmt_tm)
        existing_tm = res_tm.scalar_one_or_none()
        if existing_tm:
             await self.db.delete(existing_tm)  # ✅ Upgrade: TeamMember → User
             await self.db.flush()
        
        # ✅ 4. Create NEW PENDING User (Zeilen 108-117)
        new_user = User(
            id=str(uuid.uuid4()),
            client_id=client_id,
            email=obj_in.email,
            full_name=obj_in.full_name,
            hashed_password="PENDING_USER_NO_PASSWORD",  # ✅ Wird später gesetzt bei Activation
            status=UserStatus.PENDING.value,  # ✅ WICHTIG: PENDING
            is_superuser=False,
            is_mfa_enabled=False
        )
    
    # ✅ 5. Assign Role (Zeilen 120-137)
    role_stmt = select(Role).where(Role.name == obj_in.role)
    role_res = self.db.execute(role_stmt)
    role_obj = role_res.scalar_one_or_none()
    if not role_obj:
        role_stmt = select(Role).where(Role.name == "participant")
        role_res = self.db.execute(role_stmt)
        role_obj = role_res.scalar_one()
    
    new_user.roles = [role_obj]
    
    if not existing_user:
        self.db.add(new_user)
    
    await self.db.flush()  # ✅ Alle Adds vor Commit
    
    # ✅ 6. ActivationToken (Zeilen 139-148)
    token = secrets.token_urlsafe(32)
    expiration = datetime.now(timezone.utc) + timedelta(days=7)
    activation_entry = ActivationToken(
        id=str(uuid.uuid4()),
        user_id=new_user.id,
        token=token,
        expires_at=expiration
    )
    self.db.add(activation_entry)
    
    # ✅ 7. Load Client for company_name
    client_stmt = select(Client).where(Client.id == client_id)
    client_res = self.db.execute(client_stmt)
    client_obj = client_res.scalar_one()
    
    await self.db.commit()  # ✅ Atomar: User + Token in einem Commit
    await self.db.refresh(new_user)
    
    # ✅ 8. Webhook (Zeilen 158-165)
    activation_link = f"{settings.FRONTEND_URL}/activate?token={token}"
    await trigger_user_invited_webhook(
        email=new_user.email,
        full_name=new_user.full_name or "Colleague",
        company_name=client_obj.company_name,
        activation_link=activation_link
    )
    
    # ✅ 9. AuditLog (Zeilen 167-176)
    await AuditService.log_action(
        self.db, 
        client_id=client_id, 
        action="RE_INVITE_USER" if existing_user else "INVITE_USER", 
        user_id=creator_id,
        table_name="users",
        record_id=new_user.id,
        new_values={"email": new_user.email, "status": new_user.status}
    )
    
    return new_user
```

## 1.4 Benötigte Imports für auth.py Fix

```python
# Zusätzliche imports in auth.py needed:
from datetime import timedelta, timezone  # für token expiration
import secrets  # für token_urlsafe
from sqlalchemy import delete  # für cleanup
from app.models.user import User as UserModel, Role as RoleModel, UserStatus, ActivationToken
from app.services.audit_service import AuditService
from app.utils.webhook_utils import trigger_user_invited_webhook
```

## 1.5 Fix-Vorschlag für auth.py:register

**Kompletter Ersatz-Code** (analog zu team_service.py aber für Self-Service):

```python
@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    *, db: AsyncSession = Depends(deps.get_db), user_in: UserCreate
) -> Any:
    """
    Self-Service Registration.
    
    Flow:
    1. Check if email already exists in users (ACTIVE or PENDING) → Error
    2. Check if email exists in team_members → delete (upgrade to registered user)
    3. Create Client if not provided
    4. Create User with status=PENDING (not ACTIVE!)
    5. Create ActivationToken (expires in 7 days)
    6. Trigger user-invited webhook (sends email with activation link)
    7. AuditLog for Client creation and User creation
    8. Single transaction (commit at end)
    """
    # 1. Prüfe Duplicate in users (ACTIVE oder PENDING)
    stmt = select(UserModel).where(UserModel.email == user_in.email)
    res = await db.execute(stmt)
    existing_user = res.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists.",
        )
    
    # 2. Prüfe team_members und lösche falls vorhanden (upgrade)
    from app.models.team import TeamMember
    stmt_tm = select(TeamMember).where(TeamMember.email == user_in.email)
    res_tm = await db.execute(stmt_tm)
    existing_tm = res_tm.scalar_one_or_none()
    if existing_tm:
        await db.delete(existing_tm)
        await db.flush()
    
    # 3. Client Handling
    client_id = user_in.client_id
    if not client_id:
        client_id = str(uuid.uuid4())
        
        # Determine plan
        plan_enum = SubscriptionPlan.GRATUIT
        minutes = 600
        
        if user_in.plan == "PRO":
            plan_enum = SubscriptionPlan.PRO
            minutes = 3000
        elif user_in.plan == "ENTREPRISE":
            plan_enum = SubscriptionPlan.ENTREPRISE
            minutes = 12000
            
        new_client = Client(
            id=client_id,
            company_name=user_in.company_name or f"{user_in.full_name or user_in.email}'s Company",
            subscription_plan=plan_enum,
            subscription_status=SubscriptionStatus.ACTIVE,
            minutes_included=minutes
        )
        db.add(new_client)
        await db.flush()  # Get client_id for user FK
        
        # AuditLog für Client-Erstellung
        await AuditService.log_action(
            db,
            client_id=client_id,
            action="CREATE_CLIENT",
            user_id=None,  # Self-Service, kein User-ID verfügbar
            table_name="clients",
            record_id=new_client.id,
            new_values={
                "company_name": new_client.company_name,
                "subscription_plan": new_client.subscription_plan.value,
                "minutes_included": new_client.minutes_included
            }
        )
    
    # 4. Determine Role
    if not user_in.client_id:
        target_role = "dg"  # First user of tenant becomes 'dg'
    else:
        target_role = user_in.role or "participant"
    
    role_result = await db.execute(
        select(RoleModel).where(RoleModel.name == target_role)
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {target_role}. Please contact administrator."
        )
    
    # 5. Create User mit status=PENDING (nicht ACTIVE!)
    db_obj = UserModel(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        status=UserStatus.PENDING.value,  # ✅ PENDING för E-Mail-Verifikation
        is_superuser=False,
        is_mfa_enabled=False,
        created_at=datetime.now(timezone.utc) if hasattr(datetime, "UTC") else datetime.utcnow(),
    )
    
    db_obj.roles = [role]
    db.add(db_obj)
    await db.flush()
    
    # 6. ActivationToken erstellen
    token = secrets.token_urlsafe(32)
    expiration = datetime.now(timezone.utc) + timedelta(days=7)
    activation_entry = ActivationToken(
        id=str(uuid.uuid4()),
        user_id=db_obj.id,
        token=token,
        expires_at=expiration
    )
    db.add(activation_entry)
    await db.flush()
    
    # 7. Client laden für Company Name im Webhook
    client_stmt = select(Client).where(Client.id == client_id)
    client_res = await db.execute(client_stmt)
    client_obj = client_res.scalar_one()
    
    # 8. AuditLog für User-Erstellung
    await AuditService.log_action(
        db,
        client_id=client_id,
        action="CREATE_USER",
        user_id=db_obj.id,  # Self-Service: User erstellt sich selbst
        table_name="users",
        record_id=db_obj.id,
        new_values={
            "email": db_obj.email,
            "status": db_obj.status,
            "role": target_role
        }
    )
    
    # 9. Commit ALLES atomar (Client + User + Token + AuditLogs)
    await db.commit()
    await db.refresh(db_obj)
    
    # 10. Webhook AUSSERHALB Transaction (nach Commit) – Background Task wäre besser
    activation_link = f"{settings.FRONTEND_URL}/activate?token={token}"
    try:
        await trigger_user_invited_webhook(
            email=db_obj.email,
            full_name=db_obj.full_name or "Valued Customer",
            company_name=client_obj.company_name,
            activation_link=activation_link
        )
    except Exception as e:
        logger.error(f"Failed to send activation webhook: {e}")
        # Optional: Celery Task für Retry Queueen
    
    return User(
        id=db_obj.id,
        email=db_obj.email,
        full_name=db_obj.full_name,
        status=db_obj.status,
        is_superuser=db_obj.is_superuser,
        is_mfa_enabled=db_obj.is_mfa_enabled,
        created_at=db_obj.created_at,
        role=target_role,
    )
```

## 1.6 Transaktions-Sicherheit: Warum Commit am Ende?

**Problem in Original:**
```python
db.add(new_client)
await db.flush()  # Client wird persistent (autocommit in Session?)
# ... später User-Erstellung ...
await db.commit()  # Wenn User fehlschlägt, bleibt Client!
```

**Lösung:**
- Alle `db.add()` Aufrufe vor `await db.commit()` sammeln
- Kein `flush()` nach einzelnen adds (außer für FK-Auflösung bei neuen Clients)
- Erst nach allen Operationen `commit()` aufrufen
- Bei Exception → automatischer Rollback durch Session (keine Daten persistiert)

**In team_service.py korrekt:** Zeile 155 `await self.db.commit()` → erst NACH allen adds (User, Token)

**In unserem Fix:** Alle adds (Client, User, ActivationToken, AuditLogs) vor finalem commit → atomar

## 1.7 Zusätzliche Sicherheits-Überlegungen

### Secure Password Handling für Self-Service
- `user_in.password` wird gehasht via `security.get_password_hash()` ✅
- User muss Passwort bei Registration selbst setzen (kein随机生成的Kennwort)
- ActivationToken sichert E-Mail-Besitz

### Role Assignment
- Self-Service: Erster User einer Tenant wird `dg` (Directeur Général) → Admin-Rechte
- Spätere User: Default `participant` oder explizit `user_in.role`
- `team_service.py` blockiert `system_admin`/`tech_admin` über Team-Management ✅

### Client-Erstellung bei existing client_id
- Wenn User `client_id` mitliefert → wird KEIN neuer Client erstellt
- Client muss bereits existieren (z.B. von Admin angelegt)
- Plan wird ignoriert, Client hat eigenen Plan → OK

## 1.8 Testing in DEV & Staging

### DEV (docker-compose)
```bash
# 1. Starte DEV Environment
cd /home/opc/meeting-automation
docker-compose up -d

# 2. Teste Registration über Frontend oder curl
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!",
    "full_name": "Test User",
    "company_name": "Test Corp",
    "plan": "GRATUIT"
  }'

# 3. Prüfe DB
docker-compose exec postgres psql -U meeting_user -d meeting_db \
  -c "SELECT id, email, status FROM users WHERE email='test@example.com';"
# Erwartet: status = PENDING (nicht ACTIVE)

docker-compose exec postgres psql -U meeting_user -d meeting_db \
  -c "SELECT id, token FROM activation_tokens WHERE user_id=(SELECT id FROM users WHERE email='test@example.com');"
# Erwartet: 1 Token vorhanden

docker-compose exec postgres psql -U meeting_user -d meeting_db \
  -c "SELECT company_name FROM clients WHERE id=(SELECT client_id FROM users WHERE email='test@example.com');"
# Erwartet: Client erstellt

docker-compose exec postgres psql -U meeting_user -d meeting_db \
  -c "SELECT action, table_name, record_id FROM audit_logs WHERE client_id=(SELECT client_id FROM users WHERE email='test@example.com');"
# Erwartet: AuditLog für CREATE_CLIENT und CREATE_USER

# 4. Prüfe n8n Webhook
# Öffne http://localhost:5678 und prüfe executions für "user-invited" Webhook
# Erwartet: 1 execution mit activation_link

# 5. Prüfe E-Mail (n8n SMTP)
# Da n8n local SMTP konfiguriert, öffne http://localhost:5678/webhook-test/user-invited
# Oder prüfe n8n UI: Workflow "User Invited Webhook" → Executions → Email gesendet?
```

### Staging (Kubernetes)
```bash
# 1. Prüfe Staging Namespace
kubectl get ns meeting-automation-staging

# 2. Port-Forward für DB Access
kubectl port-forward -n meeting-automation-staging svc/postgres 5432:5432 &
# Oder exec direkt:
kubectl exec -n meeting-automation-staging deployment/postgres -- psql -U meeting_user -d meeting_db_staging \
  -c "SELECT email, status FROM users WHERE email='staging-test@example.com';"

# 3. Teste Registration
kubectl exec -n meeting-automation-staging deployment/backend -- curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"staging-test@example.com","password":"Test123!","full_name":"Staging Test"}'

# 4. Prüfe DB
kubectl exec -n meeting-automation-staging deployment/postgres -- psql -U meeting_user -d meeting_db_staging \
  -c "SELECT id, email, status FROM users WHERE email='staging-test@example.com';"
# Erwartet: PENDING

# 5. Prüfe n8n Webhook in Staging
# Staging n8n läuft auf Port 5679 (config checken)
kubectl port-forward -n meeting-automation-staging svc/n8n 5679:5678 &
# Öffne http://localhost:5679 und prüfe Workflow "User Invited Webhook" executions

# 6. Prüfe AuditLogs
kubectl exec -n meeting-automation-staging deployment/postgres -- psql -U meeting_user -d meeting_db_staging \
  -c "SELECT * FROM audit_logs WHERE user_id=(SELECT id FROM users WHERE email='staging-test@example.com');"

# 7. Cleanup nach Test
kubectl exec -n meeting-automation-staging deployment/postgres -- psql -U meeting_user -d meeting_db_staging \
  -c "DELETE FROM users WHERE email='staging-test@example.com';"
```

## 1.9 Migration: Schema-Änderungen?

**Keine Schema-Änderungen erforderlich!**
- `activation_tokens` Tabelle existiert bereits ✅
- `users.status` erlaubt `PENDING` (UserStatus Enum) ✅
- `clients` Tabelle existiert ✅
- `audit_logs` Tabelle existiert ✅

**Nur Code-Änderung** in `backend/app/api/v1/auth.py`

## 1.10 Fragen vor Implementierung

1. **Soll der Webhook-Aufruf synchron bleiben oder als Celery Task?** 
   - Aktuell: team_service.py macht synchronen httpx-Aufruf (blockiert API bis n8n antwortet)
   - Risiko: n8n down → API-Request timeout
   - Empfehlung: Celery Task für asynchrone Verarbeitung (siehe Phase 6)

2. **Rollback bei Webhook-Fehler?**
   - team_service.py:160-165 macht Webhook NACH commit
   - Wenn Webhook fehlschlägt → User bleibt in DB, aber keine E-Mail
   - Empfehlung: Retry-Mechanismus mit Celery (Phase 6)

3. **AuditLog User-ID bei Self-Service**
   - team_service.py:169 `user_id=creator_id` (Admin der einlädt)
   - auth.py:register → Self-Service, kein creator_id vorhanden
   - Mein Vorschlag: `user_id=db_obj.id` (User erstellt sich selbst) oder `None`
   - Welcome Feedback: Welche Option bevorzugen Sie?

4. **Client-Plan bei Self-Service**
   - User kann `plan` im Request mitgeben ("GRATUIT"/"PRO"/"ENTREPRISE")
   - Ist das OK oder soll immer GRATUIT sein und Upgrade später via Stripe?
   - Mein Vorschlag: Plan aus Request respektieren (User wählt Plan self-service)

Bitte bestätigen Sie die Analyse und geben Sie Feedback zu den 4 Fragen, bevor ich implementiere.
