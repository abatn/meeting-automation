# OnlyOffice ds-docservice.conf WebSocket Fix

## Problem
OnlyOffice editor shows "download failed" because WebSocket connection fails:
```
io.connection_error code=3, message=Bad request, url=/doc/?EIO=4&transport=websocket,
x_forwarded_proto=http, upgrade=undefined, connection=close
```

## Root Cause
The `ds-docservice.conf` `/` catch-all location doesn't forward WebSocket upgrade headers. The `http-common.conf` sets them at http level, but the chain is:
- Browser → nginx-ingress (HTTP NodePort) → frontend nginx → onlyoffice internal nginx → NodeJS
- nginx-ingress doesn't set `X-Forwarded-Proto: https` (HTTP NodePort, not HTTPS)
- Frontend nginx passes empty `$http_x_forwarded_proto` → OnlyOffice sees `http`
- WebSocket `Upgrade`/`Connection` headers get lost in the chain

## Fix
Update `onlyoffice-ds-docservice` ConfigMap to add WebSocket headers and force `X-Forwarded-Proto: https` in the `/` location block.
