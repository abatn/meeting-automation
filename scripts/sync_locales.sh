#!/bin/bash

# sync_locales.sh
# Dieses Skript synchronisiert die Übersetzungsdateien zwischen dem Source-Ordner und dem Public-Ordner.
# Die Quelle der Wahrheit (Source of Truth) ist: frontend/src/i18n/locales/

SOURCE_DIR="frontend/src/i18n/locales"
TARGET_DIR="frontend/public/locales"

echo "🔄 Synchronisiere i18n Locales..."

if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Fehler: Quellverzeichnis $SOURCE_DIR nicht gefunden!"
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "📁 Erstelle Zielverzeichnis $TARGET_DIR..."
    mkdir -p "$TARGET_DIR"
fi

# Kopiere alle JSON Dateien
cp -v $SOURCE_DIR/*.json $TARGET_DIR/

echo "✅ Synchronisation abgeschlossen!"
