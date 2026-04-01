#!/bin/bash

# cleanup-users.sh - Löscht bestimmte Benutzer aus der Datenbank

echo "Lösche Benutzer aus der Datenbank..."

docker compose exec -T postgres psql -U meeting_user -d meeting_db << EOF
BEGIN;

-- Audit-Logs bereinigen
UPDATE audit_logs SET user_id = NULL 
WHERE user_id IN (SELECT id FROM users WHERE email IN ('batniniabdelkader@yahoo.com'));

-- User-Rollen löschen
DELETE FROM user_roles 
WHERE user_id IN (SELECT id FROM users WHERE email IN ('batniniabdelkader@yahoo.com'));

-- Aktivierungs-Tokens löschen
DELETE FROM activation_tokens 
WHERE user_id IN (SELECT id FROM users WHERE email IN ('batniniabdelkader@yahoo.com'));

-- Benutzer löschen
DELETE FROM users 
WHERE email IN ( 'batniniabdelkader@yahoo.com');

COMMIT;

-- Anzahl der gelöschten Benutzer anzeigen
SELECT 'Benutzer gelöscht: ' || COUNT(*) AS result 
FROM users WHERE email IN ( 'batniniabdelkader@yahoo.com');
EOF

echo "Fertig."
