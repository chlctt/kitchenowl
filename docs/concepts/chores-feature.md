# Konzept: Chores (Issue #512, TomBursch/kitchenowl)

Status: Entwurf v4 (Abschnitt 11 = Entscheidungen des Auftraggebers, hat Vorrang vor allem Früheren)

## 1. Anforderungen (aus Issue #512 und #55)

Issue-Autor (gymnae):
- Neuer Tab "Chores" (neben dem geplanten ToDo-Feature #55).
- Einfache, einspaltige Liste mit einzeiligen Aufgaben.
- Rotation: Haushaltsmitglieder werden einer Aufgabe zugeordnet, Reihenfolge fest oder zufällig.
- Alphabetische Sortierung, eigene Chores oben.
- Langer Druck = erledigt, Aufgabe geht automatisch an die nächste Person.
- Bewusst NICHT: Fälligkeitsdaten, Unteraufgaben, Gamification.

Ergänzungen aus den Kommentaren:
- Timoses: jeder kann Aufgaben anlegen und übernehmen; Erledigtes pro Person erfassen (Bilanz wie bei Ausgaben), auch wer die Aufgabe angelegt hat (Mental Load).
- braklo (#55): Wunsch nach Fälligkeit + Zuständigem; Rotation nur "nice to have"; Aktivierung über Feature-Toggle statt fester Tab-Leiste.
- Maintainer (#55): Tab-Leiste hat schon 5 Einträge, Idee: konfigurierbar / Untermenü.

## 2. Machbarkeit mit vorhandener Funktionalität

| Baustein | Vorhanden | Wiederverwendung |
|---|---|---|
| Feature-Toggle pro Haushalt | `planner_feature`, `expenses_feature` (Household-Model, Schemas, `ViewsEnum.isViewActive`, `sliver_household_feature_settings.dart`) | 1:1 Muster für `chores_feature` |
| Tab-Konfiguration | `ViewsEnum` + `view_ordering`, `isOptional()`, `addMissing()` | neuer Enum-Wert `chores`; neue Tabs werden automatisch angehängt |
| Mitglieder | `HouseholdMember` (household_id, user_id, owner, admin, expense_balance) | Rotation referenziert `user.id` der Mitglieder |
| Backend-Muster | Blueprint je Feature, Registrierung in `api/register_controller.py`, `@authorize_household`, `validate_args` (Marshmallow), `DbModelAuthorizeMixin` | identisch (`/<household_id>/chores`) |
| Statistik/Bilanz-Idee | `expense_balance`, Analytics-Controller | nicht nötig; eigene Completion-Tabelle |
| Frontend-Muster | Cubit + Page unter `pages/household_page/`, Service in `services/api`, Offline-Transactions in `services/transactions` | wie Planner |
| Echtzeit | Socket.IO nur für Einkaufsliste | optional, Phase 2 |

Ergebnis: **gut machbar, keine Architekturänderung nötig.** Neu sind nur ein Datenmodell, ein Controller, ein Tab. Einziger echter Konfliktpunkt: Platz in der Navigationsleiste (siehe Rückfragen).

## 3. Offene Rückfragen (mit vorgeschlagenem Default)

1. **Umfang:** Nur Rotation-Chores (Issue #512) oder allgemeine ToDos mit Zuständigem/Fälligkeit (#55)? Default: nur #512, Modell so, dass #55 später aufsetzen kann.
2. **Rotationsmodus:** fest (Reihenfolge) und zufällig, oder nur fest? Default: beides, pro Chore wählbar. "Zufällig" = zufällig unter den anderen Teilnehmern, nie dieselbe Person zweimal hintereinander.
3. **Ohne Rotation:** Darf ein Chore nur einen festen Zuständigen haben oder gar keinen (Timoses-Variante "übernehmen")? Default: Teilnehmerliste darf 1 oder 0 Personen enthalten; bei 0 = "offen", jeder kann übernehmen.
4. **Nach "erledigt":** Chore bleibt dauerhaft in der Liste (wiederkehrend, ohne Fälligkeit, wie im Issue) und geht an die nächste Person. Einmalige Chores, die verschwinden: ja/nein? Default: nein; Löschen manuell.
5. **Erledigt-Historie/Bilanz (Timoses):** Soll pro Person gezählt werden? Default: Completion-Log wird immer geschrieben (billig, Mental-Load-Auswertung später möglich), UI dafür erst Phase 2.
6. **Tab-Platz:** Als sechster Tab, anstelle eines optionalen, oder im "Mehr"-Menü? Default: optionaler Tab wie Planner/Balances, per Feature-Toggle, Standard **aus** (damit bestehende Haushalte nichts ändern).
7. **Wer darf ändern?** Alle Mitglieder anlegen/erledigen, Löschen/Bearbeiten ebenfalls alle (wie Rezepte)? Default: ja.
8. **Erledigt für jemand anderen:** Darf jeder jeden Chore abhaken oder nur der aktuell Zuständige? Default: jeder darf (Realität: jemand springt ein); im Log steht, wer es getan hat.
9. **Push/Benachrichtigung** bei Zuweisung: Default: nicht Teil des ersten Releases (KitchenOwl hat keine Push-Infrastruktur).

## 4. Datenmodell (Backend)

Neue Tabellen (Alembic-Migration, Muster `6c669d9ec3bd`):

```
chore
  id              int PK
  household_id    int FK household.id, NOT NULL, index   (cascade delete-orphan via Household)
  name            str(128) NOT NULL
  description     str NULL            (optional, Phase 2)
  rotation_mode   enum('ordered','random') NOT NULL default 'ordered'
  assigned_to     int FK user.id NULL (ondelete SET NULL)   -- aktuell zuständig
  created_by      int FK user.id NULL (ondelete SET NULL)
  created_at      datetime NOT NULL
  last_done_at    datetime NULL

chore_participant           -- Teilnehmer + Reihenfolge
  chore_id   int FK chore.id (ondelete CASCADE)  PK
  user_id    int FK user.id  (ondelete CASCADE)  PK
  position   int NOT NULL

chore_completion            -- Historie / Statistik
  id         int PK
  chore_id   int FK chore.id (ondelete CASCADE)
  household_id int FK, index
  done_by    int FK user.id NULL (ondelete SET NULL)
  done_at    datetime NOT NULL
```

Zusätzlich `household.chores_feature` BOOLEAN NOT NULL default **False** (Migration mit `server_default`, damit Bestandszeilen gültig sind).

Invarianten:
- Teilnehmer müssen Mitglieder des Haushalts sein (im Controller prüfen, 400/403 sonst).
- Wird ein Mitglied aus dem Haushalt entfernt: aus `chore_participant` dieses Haushalts löschen; war es `assigned_to`, Rotation weiterschalten (oder NULL). Muss im Member-Remove-Pfad (`household_controller`) ergänzt werden.
- Rotation ("next"): ordered = nächster `position` zyklisch nach dem aktuellen Zuständigen (ist dieser nicht mehr Teilnehmer: kleinste Position). random = Zufall unter Teilnehmern außer aktuellem (bei 1 Teilnehmer: derselbe).
- "Done" ist eine einzige Transaktion: Completion schreiben, `last_done_at` setzen, `assigned_to` weiterschalten. Gegen Doppel-Tap: Zeilensperre (`with_for_update`) bzw. Idempotenz-Fenster nicht nötig, da jede Erledigung zählt.

## 5. API

Blueprint `choresHousehold`, Prefix `/<int:household_id>/chores`, Muster wie Expense (Liste/Create unter Household, Einzel-Operationen unter `/chores/<id>` mit `DbModelAuthorizeMixin.checkAuthorized()`):

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/<hid>/chores` | alle Chores inkl. Teilnehmer (sortiert Name) |
| POST | `/<hid>/chores` | anlegen (`name`, `rotation_mode`, `participants[user_id]`, optional `assigned_to`) |
| GET | `/chores/<id>` | Einzelabfrage |
| POST | `/chores/<id>` | ändern (Name, Modus, Teilnehmer, Zuständiger manuell überschreiben) |
| DELETE | `/chores/<id>` | löschen |
| POST | `/chores/<id>/done` | erledigt: Log + Rotation, liefert aktualisierten Chore |
| GET | `/<hid>/chores/completions` | Historie (paginiert), Phase 2 |

Sortierung "eigene oben" und alphabetisch erfolgt **clientseitig** (Client kennt eigene user.id), Server liefert alphabetisch.
Household-Schemas (`UpdateHousehold`, `GetHousehold`) um `chores_feature` erweitern; Dokumentation der API/Tests analog `test_api_planner.py`.

## 6. Frontend (Flutter, `kitchenowl/`)

- `ViewsEnum.chores` ergänzen: Icons (`Icons.cleaning_services_outlined/rounded`), `toLocalizedString`/`ShortString`, `isOptional=true`, `isViewActive` → `household.featureChores ?? false`, `parse('chores')`. **Achtung:** die Enum-Reihenfolge ist Index-basiert (Listen für Icons/Strings) und `more` steht zuletzt; neuer Wert muss vor `more` eingefügt werden und alle Index-Listen erweitern. Gespeicherte `view_ordering` enthalten Namen (Strings), daher kompatibel.
- `Household` Model: `featureChores`; `sliver_household_feature_settings.dart`: Schalter.
- Neu: `models/chore.dart`, `services/api/chore.dart`, `cubits/chore_cubit.dart`, `pages/household_page/chores.dart`, Route in `router.dart` unter `/household/:id/chores`.
- UI: einspaltige Liste; eigene Chores zuerst, dann alphabetisch; je Zeile Name + Avatar/Name des Zuständigen; **Long-Press = erledigt** (mit Snackbar "Rückgängig" für ca. 5 s, da Long-Press versehentlich passieren kann; Undo = neuer Endpunkt/zweites Done ist NICHT gleichwertig, daher Undo via `POST /chores/<id>` mit altem `assigned_to` + Löschen der letzten Completion → alternativ weglassen, siehe Review-Frage); Tap = Bearbeiten-Dialog (Name, Modus, Teilnehmer per Mehrfachauswahl, Reihenfolge per Drag). FAB = neuer Chore.
- Offline: Chores nur online (wie Balances); keine Transaktions-Queue in Phase 1.
- Lokalisierung: neue Keys in `l10n/app_en.arb` (andere Sprachen über Weblate).
- Abgrenzung: Kein Datum, keine Unteraufgaben, keine Gamification (ausdrücklicher Wunsch).

## 7. Phasen

1. **MVP:** Feature-Toggle, Modelle+Migration, CRUD+done, Tab/Liste/Long-Press, Backend-Tests, Flutter-Widget/Cubit-Tests, Docs-Eintrag.
2. Completion-Historie/Statistik pro Person ("wer hat wie oft"), Undo, Echtzeit via Socket.IO.
3. Anschluss an ToDo (#55) / Fälligkeit, falls gewünscht.

## 8. Risiken

- Tab-Leiste mit 6 Einträgen auf kleinen Displays (Mitigation: optional, Default aus; Maintainer-Idee Untermenü).
- Fork-Commit "feat: Add household chores tracking feature" (1ARdotNO) existiert; Abgleich vor Implementierung, um Doppelarbeit/Inkompatibilität bei Upstream-PR zu vermeiden.
- Datenmigration auf SQLite **und** PostgreSQL testen (Enum als String/CHECK statt nativer PG-Enum, wie im Projekt üblich).
- Mitglied-Entfernung/Account-Löschung: Fremdschlüssel-Verhalten (siehe Invarianten).
- Race Condition bei gleichzeitigem "done" (zwei Geräte): Zeilensperre, beide Erledigungen zählen und rotieren nacheinander (ggf. unerwünscht, siehe Review).

## 9. Review-Ergebnis und Korrekturen (v2)

Review durch unabhängigen Agent gegen den Code. Die Machbarkeit ("keine Architekturänderung") wurde bestätigt, der Aufwand liegt aber höher als in v1 beschrieben. Korrekturen:

**Blocker, jetzt im Konzept berücksichtigt**
1. **Keine verlässlichen DB-Kaskaden.** Kein Modell setzt `ondelete`, und SQLite läuft ohne `PRAGMA foreign_keys=ON` (`backend/app/config.py`). PostgreSQL würde beim User-Löschen mit IntegrityError scheitern. Daher: Bereinigung explizit im Code, wie `User.delete()` (`models/user.py`) es für `File.created_by` tut. `ondelete` wird in der Migration zusätzlich gesetzt, aber nicht vorausgesetzt.
2. **Haushalts-Löschung:** `Household.chores` mit `cascade="all, delete-orphan"`, `Chore.participants` und `Chore.completions` ebenfalls ORM-Kaskade. Vorab klären, wo der Haushalt tatsächlich gelöscht wird (`deleteHouseholdById` löscht nur Mitglieder).
3. **Mitglied entfernen / User löschen:** Der Pfad liegt in `HouseholdMember.delete()` (`models/household.py`), nicht nur im Controller; zusätzlich Selbstlöschung in `user_controller.py`. Dort Teilnehmer entfernen, Positionen neu nummerieren, `assigned_to` anhand der Position des entfernten Mitglieds auf den Nachfolger setzen (sonst NULL).
4. **Migration:** `rotation_mode` als `sa.String` plus Schema-Validierung (kein natives Enum). `chores_feature` per `op.add_column` mit `server_default=sa.false()` in `batch_alter_table`. Als Vorlage eine einfache Schema-Migration verwenden, nicht `6c669d9ec3bd`. Head-Revision vorher prüfen. Auf SQLite und PostgreSQL testen.

**Wichtig**
5. **ViewsEnum:** Zu ändern sind die Index-Listen in `views_enum.dart`, der `switch` in `household_page.dart`, `isViewActive`, sowie `household_add_cubit`, `household_update_cubit`, `household_add_update_cubit`. `addMissing` hängt `chores` für Bestandshaushalte hinter `more` an; Entscheidung: `addMissing` hält `more` zuletzt. Ein alter Client verwirft `chores` im `view_ordering` beim Speichern; akzeptiert und dokumentiert. Der Server validiert `view_ordering` bewusst weiterhin nicht.
6. **Undo:** Im MVP gestrichen (Widerspruch §6/§7). Stattdessen Long-Press mit Bestätigung. Phase 2: `done` liefert `completion_id` und speichert `previous_assigned_to`; Undo via `DELETE /chores/<id>/completions/<cid>`.
7. **Race:** `with_for_update` hilft auf SQLite nicht, und doppeltes Abhaken würde doppelt rotieren. Neu: `POST /chores/<id>/done` erhält `expected_assigned_to`; bei Abweichung 409, Client lädt neu. Die Aussage "beide Erledigungen zählen" in §8 entfällt.
8. **Rotation, Randfälle:** 0 Teilnehmer: `done` schreibt nur Log, `assigned_to` bleibt NULL. `assigned_to` kein Teilnehmer (manuell gesetzt): "ordered" nimmt kleinste Position. `UNIQUE(chore_id, position)`; Teilnehmeränderungen und `done` in je einer Transaktion.
9. **API:** Registrierung in `api/register_controller.py` (Household-Sub-Blueprint und Top-Level-Blueprint) plus Export in `controller/__init__.py`, wie Expense. Backend ignoriert `chores_feature` wie der Planner (bewusste Entscheidung, nur UI-Toggle).
10. **Übersehene Stellen:** `Household.obj_to_export_dict`/Import-Export (Entscheidung: Chores im MVP nicht exportiert, `chores_feature` schon), optional `analytics_controller.py`, Offline-Verhalten von `isViewActive`. Spalte `description` aus dem MVP gestrichen.
11. **Tests:** Backend neu (Muster `test_api_planner.py`): Rotation (ordered/random/Randfälle), CRUD, 409, Berechtigung fremder Haushalt, User-/Mitglied-/Haushalt-Löschung. Flutter-Teststruktur ist vorab zu prüfen.
12. **Lokalisierung:** ca. 15 neue Keys in `app_en.arb`; Klären, ob `app_de.arb` mitgeliefert wird.

**Aufwandsschätzung (korrigiert):** Backend ca. 8 Dateien neu/geändert, Flutter ca. 12 Dateien; MVP realistisch mehrere Tage statt "klein".

**Priorität der Rückfragen (aus Review):** Zuerst Frage 6 (Tab-Platz) und Frage 1 (Umfang #512 vs. #55), da sie das UI- und Datenmodell bestimmen.

## 10. Anforderungsänderung (v3): optionale Rotation, feste Zuweisung, optionale Fälligkeit

Diese Änderung hat Vorrang vor den Abschnitten 1-8, soweit sie widerspricht. Sie bricht bewusst mit dem Issue-Wunsch "keine Fälligkeiten" und nähert das Feature an #55 an. Ein dritter Punkt der Anforderungen war leer und ist noch offen.

**Datenmodell (Änderungen gegenüber §4)**
- `chore.rotation_mode`: `none | ordered | random`, Default `none`.
- `chore.assigned_to` ist bei `none` die feste Zuweisung (nullable = offen, jeder kann übernehmen).
- `chore_participant` wird nur bei `ordered`/`random` genutzt; bei `none` leer. Validierung: Rotation braucht mindestens 2 Teilnehmer.
- Neu: `due_date` (Datum, nullable), `repeat_interval_days` (int > 0, nullable), `completed_at` (nullable, nur für einmalige Chores).
- `repeat_interval_days` ohne `due_date` ist ungültig (400).

**Verhalten von `POST /chores/<id>/done`** (immer mit `expected_assigned_to`/409 und Log in `chore_completion`)
- Rotation `ordered`/`random`: `assigned_to` rückt bei jedem "erledigt" weiter, unabhängig von der Fälligkeit.
- Rotation `none`: Zuweisung bleibt.
- Mit `repeat_interval_days`: neue Fälligkeit = alte Fälligkeit + Intervall; liegt das Ergebnis noch in der Vergangenheit, ab heute + Intervall (kein Aufholen von Rückständen). Chore bleibt in der Liste.
- Ohne Intervall (einmalig): `completed_at` wird gesetzt, der Chore verschwindet aus der Standardliste. Ohne `due_date` und ohne Intervall bleibt der Chore wie im Issue dauerhaft (Rotation ohne Datum), er wird also nicht archiviert. Regel: nur Chores mit `due_date` und ohne Intervall sind einmalig.
- Erledigte Einmal-Chores: `GET /<hid>/chores?completed=true`; endgültiges Löschen weiter per DELETE.

**Frontend**
- Sortierung: überfällig zuerst, dann nach Fälligkeit, dann eigene Chores, dann alphabetisch; Chores ohne Datum folgen den datierten.
- Bearbeiten-Dialog: Zuweisung (Mitglied oder offen), Schalter "Rotation" (Modus + Teilnehmer), optional Fälligkeit, optional "Wiederholen alle N Tage".
- Überfällige farblich markiert; Long-Press = erledigt bleibt.

**Folgen für Review-Punkte**
- Randfall 1 Teilnehmer/0 Teilnehmer bei Rotation entfällt (Validierung ≥ 2); bei Mitglied-Entfernung: Teilnehmer ausfallen lassen, bei < 2 Teilnehmern Modus auf `none` mit `assigned_to` = verbliebenes Mitglied oder NULL.
- Mitglied-Entfernung bei fester Zuweisung: `assigned_to` = NULL.
- Zusätzliche Tests: Intervall-Berechnung (Vergangenheit/Zukunft), Einmal-Chore-Archivierung, ungültige Kombinationen, Sortierung.
- Zeitzonen: `due_date` als reines Datum ohne Uhrzeit; "heute" serverseitig in UTC, Clients zeigen lokales Datum (offene Kleinigkeit, im Review zu prüfen).
- Aufwand wächst um etwa 20 %; Phasen: Fälligkeit/Wiederholung bleibt im MVP, Historie-UI weiter Phase 2.

## 11. Entscheidungen des Auftraggebers (v4)

Antworten auf die Rückfragen aus §3. Sie haben Vorrang vor allen früheren Abschnitten.

| # | Entscheidung | Konsequenz |
|---|---|---|
| F1 | Neuer Tab direkt **nach dem ersten Tab** (Einkauf). Der erste Tab heißt statt "Liste" künftig "Einkauf". | `ViewsEnum.tasks` an Index 1 (hinter `items`). Für Bestandshaushalte mit gespeichertem `view_ordering` fügt `addMissing` den Tab hinter `items` ein statt am Ende (siehe unten). Kurzbezeichnung: neuer Key (z.B. `shoppingShort`) statt Änderung von `list`, weil `loc.list` auch in `settings_page.dart:215` benutzt wird. de: "Einkauf", en: "Shopping". |
| F2 | **Allgemeine ToDos** statt nur Rotations-Chores (#512 und #55). | Entität heißt intern `task` (Tabellen `task`, `task_participant`, `task_completion`; Controller `/<hid>/tasks`), Tab "Aufgaben"/"Tasks". "Chore" aus §4-§10 liest sich als "Task". Bitte Benennung bestätigen. |
| F3 | Rotation **fest (ordered) oder zufällig** wählbar, mit **definierbaren Intervallen**. | Interpretation: Wiederholung `repeat_interval_days` frei definierbar (Tage; UI-Presets täglich/wöchentlich/monatlich + eigener Wert). Die Rotation läuft weiter bei jedem "erledigt". Falls stattdessen die Rotation selbst nach Zeitintervall wechseln soll, bitte sagen. |
| F4 | **Pro Haushalt einstellbar** (Einstellung). | Gemeint als: wer darf abhaken, "jedes Mitglied" oder "nur der Zugewiesene". Neue Spalte `household.tasks_complete_policy` (`anyone` | `assignee`, Default `anyone`), Prüfung im `done`-Endpunkt (403). Bitte bestätigen, falls anders gemeint. |
| F5 | Aufgaben **ohne Zuweisung** erlaubt (offen). | `assigned_to` nullable; jeder darf übernehmen (Policy `assignee` gilt dann nicht, offene Aufgaben kann jeder abhaken oder sich selbst zuweisen). |
| F6 | Merkmal **"wiederkehrend"** (`recurring`) statt Ableitung aus Datum/Intervall. | Ersetzt die Regel aus §10. `recurring=false`: einmalig, beim Erledigen `completed_at` setzen und aus der Liste nehmen. `recurring=true` ohne Intervall: bleibt dauerhaft stehen (Issue-#512-Verhalten, Rotation läuft). `recurring=true` mit Intervall: zusätzlich Fälligkeit rückt weiter (Regel aus §10). Validierung: Intervall nur mit `recurring=true` und `due_date`; Rotation ist für einmalige und wiederkehrende Aufgaben zulässig. |
| F7 | **Erledigt-Historie** wird mit geplant. | `task_completion` im MVP schreiben; Auswertung pro Person ("wer macht wie viel", auch `created_by` für Mental Load) als eigene Ansicht in Phase 2, aber Endpunkt `GET /<hid>/tasks/completions` schon im MVP, damit Daten abrufbar sind. |

**Tab-Reihenfolge (F1) im Detail**
- Standardreihenfolge neuer Haushalte: Einkauf, Aufgaben, Rezepte, Planer, Bilanzen, Mehr.
- `ViewsEnum.addMissing` ändert sich: fehlende Views werden an ihrer Enum-Position relativ zum Vorgänger eingefügt (Aufgaben direkt hinter Einkauf), `more` bleibt zuletzt. Das ändert das Verhalten für Planner/Balances nicht, weil diese bei Bestandshaushalten bereits enthalten sind.
- Aufgaben-Tab ist optional (Toggle `tasks_feature`, Default aus), ist also nur sichtbar, wenn ein Haushalt ihn aktiviert.
- 6 Tabs auf schmalen Displays: Layout in Navigationsleiste und Drawer prüfen.

**Noch offen**
- Dritter Anforderungspunkt aus der vorigen Nachricht war leer.
- Benennung Chore/Task und Auslegung von F3/F4 (siehe oben).
- Ein Review der erweiterten Anforderungen (Abschnitte 10-11) steht aus.
