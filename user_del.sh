docker compose exec -T postgres psql -U meeting_user -d meeting_db -c "BEGIN;                                                     │
│ UPDATE audit_logs SET user_id = NULL WHERE user_id IN (SELECT id FROM users WHERE email IN ('bkta3beispiel@gmail.com',            │
│ 'batniniabdelkader@yahoo.com'));                                                                                                  │
│ DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users WHERE email IN ('bkta3beispiel@gmail.com',                          │
│ 'batniniabdelkader@yahoo.com'));                                                                                                  │
│ DELETE FROM activation_tokens WHERE user_id IN (SELECT id FROM users WHERE email IN ('bkta3beispiel@gmail.com',                   │
│ 'batniniabdelkader@yahoo.com'));                                                                                                  │
│ DELETE FROM users WHERE email IN ('bkta3beispiel@gmail.com', 'batniniabdelkader@yahoo.com');                                      │
│ COMMIT;"                                                                             
