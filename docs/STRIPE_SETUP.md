# Stripe Integration — Setup & Konfiguration

**Status:** Wartet auf Stripe-Konto-Einrichtung  
**Modus aktuell:** Mock (Fallback) — wird auf echte Integration umgestellt sobald Keys vorhanden

---

## 🎯 Überblick

Stripe liefert die Payment-Infrastruktur für die SaaS-Abrechnung:
- **Checkout Sessions** — Zahlpfad für neue Abonnements
- **Subscriptions** — Wiederkehrende Zahlungen (monatlich)
- **Webhooks** — Echtzeit-Status-Synchronisation (Zahlung eingegangen, Abo gekündigt, etc.)

---

## 📋 Schritt-für-Schritt-Anleitung

### 1. Stripe-Konto erstellen

1. Gehe zu https://dashboard.stripe.com/register
2. E-Mail + Passwort eingeben
3. Land: **Frankreich** (oder Tunesien, falls verfügbar)
4. Betriebsart: **Online** (SaaS)
5.完成后 → Dashboard öffnet sich in Test-Mode

### 2. Test-Keys abrufen

Nach dem Login:
1. Linkes Menü → **Developers** → **API keys**
2. Oder direkt: https://dashboard.stripe.com/test/apikeys

Dort findest du:
| Key | Format | Variable in .env |
|-----|--------|-------------------|
| Secret key | `sk_test_...` | `STRIPE_API_KEY` |
| Publishable key | `pk_test_...` | `STRIPE_PUBLISHABLE_KEY` |

> ⚠️ **Secret key niemals im Frontend oder Git speichern!**

### 3. Products & Price-IDs erstellen

1. → https://dashboard.stripe.com/test/products
2. **"Add product"** button klicken

#### Produkt: PRO
- Name: `PRO`
- Beschreibung: `Meeting Automation PRO Plan`
- Pricing:
  - Price: `$99.00`
  - Billing period: `Monthly`
  - Tax behavior: `Exclusive`
- **"Add product"** klicken
- Nach Erstellung: **Price-ID kopieren** (`price_...`)

#### Produkt: ENTREPRISE
- Name: `ENTREPRISE`
- Beschreibung: `Meeting Automation ENTREPRISE Plan`
- Pricing:
  - Price: `$499.00`
  - Billing period: `Monthly`
  - Tax behavior: `Exclusive`
- **"Add product"** klicken
- Nach Erstellung: **Price-ID kopieren** (`price_...`)

### 4. Webhook konfigurieren

1. → https://dashboard.stripe.com/test/webhooks
2. **"Add endpoint"** button klicken

#### Konfiguration:
- **Endpoint URL:** `http://158.180.18.110:3000/api/v1/webhooks/stripe`
- **Description:** `Meeting Automation Webhook`

#### Events auswählen (5 Stück):
- ✅ `checkout.session.completed`
- ✅ `invoice.paid`
- ✅ `customer.subscription.created`
- ✅ `customer.subscription.updated`
- ✅ `customer.subscription.deleted`

3. **"Add endpoint"** klicken
4. **Signing secret** anzeigen lassen (`whsec_...`) → wird zu `STRIPE_WEBHOOK_SECRET`

> ⚠️ **Der Signing Secret wird nur EINMAL angezeigt!** Sofort kopieren.

### 5. .env konfigurieren

```bash
# Echte Stripe Keys (Test-Mode)
STRIPE_API_KEY=sk_test_DEIN_SECRET_KEY
STRIPE_PUBLISHABLE_KEY=pk_test_DEIN_PUBLISHABLE_KEY
STRIPE_WEBHOOK_SECRET=whsec_DEIN_SIGNING_SECRET
STRIPE_PRICE_ID_PRO=price_DEINE_PRO_PRICE_ID
STRIPE_PRICE_ID_ENTREPRISE=price_DEINE_ENTREPRISE_PRICE_ID
```

### 6. Backend neu starten

```bash
docker compose restart backend
```

---

## 🔒 Sicherheit

### Was ist Test-Mode?
- Alle Transaktionen sind simuliert (kein echtes Geld)
- Test-Kreditkarten: `4242 4242 4242 4242` (beliebiges Ablaufdatum, beliebiger CVC)
- Producte und Subscriptions sind real konfiguriert
- Webhooks funktionieren wie in Produktion

### Was ist Production-Mode?
- Echte Kreditkarten, echtes Geld
- Keys beginnen mit `sk_live_` / `pk_live_`
- Webhook-URL muss HTTPS haben
- **Erst nach vollständiger Test-Phase aktivieren!**

---

## 🧪 Test-Flow (nach Konfiguration)

### Test 1: Checkout starten
```bash
curl -s -X POST http://158.180.18.110:3000/api/v1/billing/checkout \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=DEIN_TOKEN" \
  -d '{"plan": "PRO", "success_url": "http://158.180.18.110:3000/billing", "cancel_url": "http://158.180.18.110:3000/billing"}'
```
**Erwartung:** Redirect zu `https://checkout.stripe.com/...`

### Test 2: Checkout abschließen (Test-Mode)
1. Checkout-URL im Browser öffnen
2. Test-Kreditkarte eingeben: `4242 4242 4242 4242`
3. Ablaufdatum: `12/34`, CVC: `123`
4. **"Subscribe"** klicken

**Erwartung:**
- Redirect zur Success-URL
- Webhook `checkout.session.completed` wird ausgelöst
- Client in DB hat `stripe_subscription_id` und `subscription_status=ACTIVE`

### Test 3: invoice.paid Webhook prüfen
```bash
# Nach ~5 Minuten (Stripe sendet invoice.paid automatisch):
curl -s http://158.180.18.110:3000/api/v1/billing/invoices \
  -H "Cookie: access_token=DEIN_TOKEN" | python3 -m json.tool
```
**Erwartung:** Neue Facture mit `status: "PAID"`

---

## ⚠️ Bekannte Probleme

### Webhook nicht erreichbar
- **Ursache:** Firewall blockiert eingehende Verbindungen auf Port 3000
- **Lösung:** Stripe → Webhooks → Endpoint → "Recent deliveries" prüfen

### Webhook-Signatur ungültig
- **Ursache:** Falscher `STRIPE_WEBHOOK_SECRET`
- **Lösung:** Signing Secret aus Stripe Dashboard kopieren, ohne Leerzeichen

### Price-ID nicht gefunden
- **Ursache:** Falsche Price-ID oder Produkt nicht aktiv
- **Lösung:** Stripe → Products → Price prüfen (muss "Active" sein)

---

## 📊 Architektur

```
Frontend                    Backend                    Stripe
   │                           │                          │
   │  POST /billing/checkout   │                          │
   │ ─────────────────────────>│                          │
   │                           │  checkout.Session.create │
   │                           │ ────────────────────────>│
   │                           │<──────────────────────── │
   │  { checkout_url, id }     │                          │
   │<───────────────────────── │                          │
   │                           │                          │
   │  Redirect zu Stripe       │                          │
   │ ────────────────────────────────────────────────────>│
   │                           │                          │
   │  User zahlt               │                          │
   │                           │                          │
   │                           │  Webhook:                │
   │                           │  checkout.session.       │
   │                           │  completed               │
   │                           │<──────────────────────── │
   │                           │                          │
   │                           │  Webhook:                │
   │                           │  invoice.paid            │
   │                           │<──────────────────────── │
   │                           │                          │
```

---

## 📝 Variablen-Referenz

| Variable | Beschreibung | Beispiel |
|----------|-------------|----------|
| `STRIPE_API_KEY` | Secret Key (Server-side) | `sk_test_abc123...` |
| `STRIPE_PUBLISHABLE_KEY` | Publishable Key (Frontend) | `pk_test_xyz789...` |
| `STRIPE_WEBHOOK_SECRET` | Signing Secret für Webhooks | `whsec_def456...` |
| `STRIPE_PRICE_ID_PRO` | Price-ID für PRO Plan | `price_1Abc...` |
| `STRIPE_PRICE_ID_ENTREPRISE` | Price-ID für ENTREPRISE Plan | `price_2Xyz...` |

---

## ✅ Checkliste vor Production

- [ ] Stripe-Konto verifiziert (E-Mail + Identität)
- [ ] Test-Mode vollständig durchgespielt
- [ ] Alle 5 Webhooks getestet (Recent deliveries → 200 OK)
- [ ] Subscription-Status wird korrekt synchronisiert
- [ ] invoice.paid erstellt Facture-Records
- [ ] BillingPanel zeigt echte Daten
- [ ] Live Mode aktiviert (Stripe Dashboard → "Activate account")
- [ ] Production-Keys in `.env` aktualisiert
- [ ] Webhook-URL auf HTTPS umgestellt
- [ ] Webhook-Events in Production nochmal konfigurieren
