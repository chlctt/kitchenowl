# Manueller Testplan – Zuweisung (@name) & Einkaufsdatum

Diese beiden Features wurden ergänzt:

1. **Zuweisung** – Einkaufslisten-Artikel können einem Haushaltsmitglied
   zugewiesen werden, per `@name` bei der Eingabe oder über ein Feld auf der
   Detailseite. In der Übersicht erscheint der Avatar / die Initiale des
   zugewiesenen Mitglieds am Artikel.
2. **Einkaufsdatum** – Ein Datum (z.B. `15.09.`, `morgen`, `next monday`,
   `2026-09-15`, `20. Dezember`) wird bei der Eingabe automatisch erkannt und
   dem Artikel als "Einkaufsdatum" zugeordnet. Solange das Datum in der
   Zukunft liegt, wird der Artikel in der Übersicht mit 50 % Deckkraft
   dargestellt. Auf der Detailseite gibt es einen Datums-Picker.

## Voraussetzungen

* Docker + Docker Compose
* Zwei Haushaltsmitglieder (für den Zuweisungs-Test), z.B. `sebastian` und `anna`

## 1. Backend vorbereiten

```bash
cd backend
uv sync --group dev          # oder: pip install -e .

# DB-Migration einspielen (fügt shoppinglist_items.assigned_to + due_date hinzu)
flask db upgrade

# Backend-Tests
uv run pytest tests/util/test_item_annotation_parser.py -q
uv run pytest tests/api/test_api_shoppinglist.py -q
```

> Hinweis: `sqlite-icu` lässt sich unter Python 3.14/Windows aktuell nicht
> bauen. Tests bitte unter Linux / im Docker-Image oder mit Python ≤ 3.13
> ausführen.

## 2. Kompletten Stack lokal starten

```bash
docker compose -f docker-compose.yml up --build
# UI: http://localhost:8080
```

Beim Hochfahren wendet der Container die Migration automatisch an
(`flask db upgrade` im Entrypoint).

## 3. Frontend bauen (optional, für Web-Dev)

```bash
cd kitchenowl
flutter pub get
flutter gen-l10n          # erzeugt lib/gen/l10n mit den neuen Keys
flutter analyze
flutter test test/models  test/cubits
flutter run -d chrome --dart-define=API_URL=http://localhost:5000
```

## 4. Testszenarien

### A. Zuweisung per @name beim Anlegen
1. Einkaufsliste öffnen, ins Suchfeld `Milch @anna` eingeben, Enter.
2. **Erwartet:** Artikel heißt `Milch` (ohne `@anna`). In der Übersicht wird
   an der Kachel/Zeile Annas Avatar/Initiale angezeigt.
3. Artikel öffnen → Feld **„Zuweisen an“** steht auf *Anna*.

### B. Zuweisung unscharf
* `Butter @seb` → wird `sebastian` zugeordnet (Teiltreffer auf Anzeigename).
* `Butter @gibtsnicht` → kein Treffer, Artikel heißt `Butter @gibtsnicht`
  (Token bleibt stehen), keine Zuweisung.

### C. Zuweisung über die Detailseite
1. Beliebigen Artikel öffnen.
2. Unter **„Zuweisen an“** ein Mitglied auswählen → zurück.
3. **Erwartet:** In der Übersicht erscheint der Avatar. Nach App-Neustart /
   Pull-to-Refresh bleibt die Zuweisung erhalten.
4. Auf *Keine* zurücksetzen → Avatar verschwindet.

### D. Datum automatisch erkennen
Jeweils neuen Artikel anlegen und Name + Einkaufsdatum prüfen:

| Eingabe | Name | Einkaufsdatum |
|---|---|---|
| `Brot 15.09` | Brot | 15. September (nächstes Vorkommen) |
| `Eier morgen` | Eier | morgen |
| `Käse 2026-12-24` | Käse | 24.12.2026 |
| `Reis next monday` | Reis | nächster Montag |
| `Mehl in 3 Tagen` | Mehl | heute + 3 Tage |
| `Butter 20. Dezember` | Butter | 20. Dezember |
| `Pizza @anna am Freitag` | Pizza | nächster Freitag, zugewiesen an Anna |

### E. Deckkraft (Opacity) in der Übersicht
1. Artikel mit Datum **in der Zukunft** anlegen (`Brot morgen`).
   **Erwartet:** Kachel/Zeile wird mit 50 % Deckkraft dargestellt.
2. Artikel öffnen, Einkaufsdatum auf **heute** oder Vergangenheit setzen.
   **Erwartet:** Volle Deckkraft.
3. Datum entfernen → volle Deckkraft.

### F. Datum über die Detailseite
1. Artikel öffnen → **„Einkaufsdatum“** → Kalender-Icon → Datum wählen.
2. Zurück → Übersicht zeigt Datum + ggf. reduzierte Deckkraft.
3. Über das X-Icon Datum löschen.

### G. Mehrbenutzer-Sync
1. Zweites Gerät / zweiter Browser mit demselben Haushalt.
2. Auf Gerät 1 `Apfel @anna morgen` anlegen.
3. **Erwartet:** Gerät 2 zeigt den Artikel innerhalb weniger Sekunden mit
   Avatar + reduzierter Deckkraft (WebSocket-Event `shoppinglist_item:add`).

### H. Regression
* Artikel ohne @name / Datum verhalten sich unverändert.
* Mengenangaben in der Beschreibung (`2 kg`) funktionieren weiter.
* URL-Erkennung in der Beschreibung (Long-Press) funktioniert weiter.
* `Salami am Stück` bleibt `Salami am Stück` (kein falsch erkanntes Datum).

## 5. API-Schnelltest (curl)

```bash
TOKEN=...   # Bearer Token
LIST=1

curl -s -XPOST localhost:5000/api/shoppinglist/$LIST/add-item-by-name \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Milch @anna morgen"}' | jq

curl -s localhost:5000/api/shoppinglist/$LIST/items \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {name, assigned_to, due_date}'
```
