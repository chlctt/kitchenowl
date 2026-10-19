# Konzept: Aufgaben/Chores (Issue #512 und #55, TomBursch/kitchenowl)

Status: **v5, konsolidierter Endstand** (zwei unabhängige Reviews eingearbeitet; frühere Fassungen in der Git-Historie). Offene Entscheidungen siehe §10.

## 1. Anforderungen (Stand Auftraggeber)

Ausgangspunkt #512 (rotierende Haushalts-Chores) und #55 (ToDo-Listen), erweitert durch Entscheidungen:

- Allgemeine Aufgaben ("Tasks") pro Haushalt, einzeilig, ohne Unteraufgaben und ohne Gamification.
- Zuweisung: fest (ein Mitglied), offen (niemand) oder Rotation (`ordered` fest oder `random` zufällig).
- Fälligkeit optional. Merkmal "wiederkehrend" (`recurring`): wiederkehrende Aufgaben bleiben stehen, einmalige verschwinden beim Erledigen. Häufigkeit frei definierbar (alle N Tage/Wochen/Monate).
- Wer abhaken darf, ist pro Haushalt einstellbar (`anyone` | `assignee`).
- Erledigt-Historie wird mitgeschrieben, Auswertung pro Person in Phase 2.
- UI: Long-Press = erledigt. Neuer Tab direkt nach dem ersten Tab. Der erste Tab heißt künftig "Einkauf" (statt "Liste").
- Feature pro Haushalt aktivierbar, Standard aus.

## 2. Machbarkeit

Machbar ohne Architekturänderung; Wiederverwendung: Feature-Toggles (`planner_feature`, `expenses_feature`), `ViewsEnum`/`view_ordering`, `HouseholdMember`, Blueprint-/Schema-/Autorisierungsmuster des Planners. Neu: drei Tabellen, Controller, Tab. Aufwand deutlich über "klein" (siehe §9).

## 3. Datenmodell

Alle neuen Modelle erben von der Projekt-Basis (`db.Model`/`DbModelBase`), Haushaltsbezug über `household_id` (für `DbModelAuthorizeMixin`).

**household** (neue Spalten, Migration mit `server_default`):
- `tasks_feature` BOOLEAN NOT NULL, Default **false** (auch in `Household.fromJson` und `isViewActive` einheitlich `?? false`).
- `tasks_only_assignee_can_complete` BOOLEAN NOT NULL, Default **false** (Schalter in den Haushaltseinstellungen: false = jedes Mitglied darf abhaken, true = nur die zugewiesene Person). Änderbar nur durch Admin/Owner.

**task**
- `id`, `household_id` (FK, index, ORM `Household.tasks` mit `cascade="all, delete-orphan"`)
- `name` String(128) NOT NULL
- `recurring` Boolean NOT NULL default false
- `due_date` Date NULL (reines Datum ohne Uhrzeit)
- `repeat_every` Integer NULL (1..365) und `repeat_unit` String NULL (`day` | `week` | `month`); beide gesetzt oder beide NULL (Häufigkeit der Aufgabe, z. B. täglich = 1/day, wöchentlich = 1/week, monatlich = 1/month)
- `rotation_mode` String NOT NULL default `none` (`none` | `ordered` | `random`; String + Schema-Validierung, kein natives Enum)
- `assigned_to` FK user.id NULL
- `created_by` FK user.id NULL
- `created_at` DateTime NOT NULL, `completed_at` DateTime NULL, `last_done_at` DateTime NULL

**task_participant** (nur bei Rotation): `task_id`, `user_id` (PK zusammen), `position` Integer, UNIQUE(`task_id`,`position`).

**task_completion**: `id`, `task_id`, `household_id` (index), `done_by` FK user NULL, `done_at` DateTime NOT NULL, `previous_assigned_to` NULL (für späteres Undo).

**Fremdschlüssel/Löschen:** Das Projekt setzt kein `ondelete`, SQLite erzwingt Fremdschlüssel nicht (`config.py`). Daher explizit im Code, `ondelete` in der Migration nur zusätzlich:
- Haushalt löschen: ORM-Kaskade `Household.tasks` → `Task.participants`, `Task.completions` (alle `delete-orphan`). Vorher klären, an welcher Stelle der Haushalt tatsächlich gelöscht wird.
- `HouseholdMember.delete()` (`models/household.py`) und Selbstlöschung in `user_controller.py` sowie `User.delete()`: Teilnehmerzeilen entfernen und `position` neu nummerieren; `created_by`/`done_by` auf NULL; `assigned_to`: bei Rotation Nachfolger anhand der Position des Entfernten, sonst NULL (offen). Bleiben bei Rotation weniger als 2 Teilnehmer, wird `rotation_mode` auf `none` gesetzt (`assigned_to` = verbliebener Teilnehmer oder NULL).
- Migration: einfaches Schemamuster mit `op.add_column(... server_default=sa.false())` in `batch_alter_table` (SQLite), nicht `6c669d9ec3bd` (Daten-Migration). Head-Revision vorher prüfen, auf SQLite und PostgreSQL testen.

## 4. Validierungsmatrix (Create und Update, serverseitig, 400)

| Regel | Verhalten |
|---|---|
| `repeat_every`/`repeat_unit` gesetzt | nur zusammen mit `recurring=true` **und** `due_date`; sonst 400 |
| `recurring` true→false | `repeat_every`/`repeat_unit` werden genullt (kein 400) |
| `due_date` per Update auf NULL | `repeat_every`/`repeat_unit` werden mit genullt |
| `rotation_mode` `ordered`/`random` | mindestens 2 `participants`, alle Mitglieder des Haushalts, keine Duplikate; `assigned_to` ∈ Teilnehmer, sonst auf kleinste Position gesetzt |
| `rotation_mode` `none` | `participants` werden ignoriert und geleert; `assigned_to` = Mitglied oder NULL (offen) |
| Offen (`assigned_to` NULL) | nur bei `none`; bei Rotation immer ein Zuständiger |
| `assigned_to` ändern | erlaubt für alle Mitglieder bei ausgeschaltetem Schalter; bei aktivem Schalter nur Zuständiger oder Admin (verhindert Umgehung) |
| Erledigter Einmal-Task | nicht editierbar außer `completed=false` (Reaktivieren); `completed_at` wird dabei NULL |
| Nicht-Mitglied als Zuständiger/Teilnehmer | 400 |

## 5. API

Registrierung wie Expense: Household-Blueprint `/<int:household_id>/tasks` und Top-Level-Blueprint `/tasks`, in `api/register_controller.py` und `controller/__init__.py`.

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/<hid>/tasks` | offene Tasks (`?completed=true` für erledigte Einmal-Tasks), Teilnehmer inklusive, alphabetisch |
| POST | `/<hid>/tasks` | anlegen |
| GET/POST/DELETE | `/tasks/<id>` | lesen, ändern, löschen (`checkAuthorized`) |
| POST | `/tasks/<id>/done` | erledigen |
| GET | `/<hid>/tasks/completions` | Historie, paginiert, für alle Haushaltsmitglieder lesbar (MVP: nur `done_by`, `done_at`, `task_id`) |

Das Backend erzwingt `tasks_feature` nicht (wie Planner, bewusste Entscheidung); `tasks_only_assignee_can_complete` wird erzwungen.

**`done`-Logik** (Reihenfolge der Prüfungen: 404 → 403 Schalter → 400 bereits erledigt → 409 Konflikt):
- Body: `expected_assigned_to` (Pflichtfeld, `null` = erwartet offen) und `done_on` (lokales Datum des Clients, nur erlaubt ±1 Tag zur Server-UTC-Zeit; Server nutzt es als "heute"). Bei Abweichung des aktuellen `assigned_to`: 409, Client lädt neu (verhindert doppeltes Weiterrotieren).
- Schalter `tasks_only_assignee_can_complete` an: nur der Zuständige (oder Admin) darf, offene Tasks darf jedes Mitglied; aus: jedes Mitglied.
- Eine Transaktion: Completion schreiben, `last_done_at` setzen, dann:
  - `recurring=false`: `completed_at` setzen, Rotation irrelevant.
  - `recurring=true`: Rotation `ordered`: nächster nach dem *bisherigen Zuständigen* (nicht nach dem Erledigenden), zyklisch; `random`: zufällig unter den anderen Teilnehmern; `none`: unverändert.
  - `recurring=true` mit Häufigkeit: neue Fälligkeit = alte `due_date` + `repeat_every` × `repeat_unit`; liegt sie vor `done_on`, dann `done_on` + Häufigkeit (kein Aufholen). Monate sind Kalendermonate; fehlt der Tag im Zielmonat, wird auf den Monatsletzten gekürzt (31. Jan → 28. Feb → 28. Mär; Drift bewusst akzeptiert).
- UI-Presets: täglich, wöchentlich, monatlich, eigener Wert (alle N Tage/Wochen/Monate).

## 6. Frontend (Flutter, `kitchenowl/`)

**Tab:**
- `ViewsEnum.tasks` an Index 1; Default `ViewsEnum.values` ergibt: Einkauf, Aufgaben, Rezepte, Planer, Bilanzen, Mehr. Alle Index-Listen in `views_enum.dart` (`toLocalizedString`, `toLocalizedShortString`, `toIcon`, `toSelectedIcon`, `isOptional`) erweitern, besser auf `switch`-Ausdrücke umstellen (sonst Laufzeit-RangeError); `parse`, `floatingActionButton` (Task-FAB), `isViewActive` (`featureTasks ?? false`).
- `addMissing` ist heute "fehlende Views in Enum-Reihenfolge anhängen" (`more` wird in `household.dart` vorher entfernt und im Enum zuletzt eingefügt). Neu: fehlende View direkt hinter ihrem Vorgänger im Enum einfügen, falls vorhanden, sonst am Anfang. Für `tasks`: hinter `items`, sonst vorne; `more` zuletzt. Gilt generisch, daher mit Test absichern, dass Bestandshaushalte mit vollständiger Liste unverändert bleiben.
- Weitere Stellen: `household_page.dart` (Switch in `_onItemTapped`, Refresh-Zweig, `MultiBlocProvider` mit `TaskListCubit`), `router.dart` (Shell-Route `tasks`), `sliver_household_feature_settings.dart` (Toggle `tasks_feature`, Schalter "Nur Zugewiesene dürfen abhaken", Annahme "`more` zuletzt" bei Reset prüfen), drei Cubits `household_add_cubit`, `household_update_cubit`, `household_add_update_cubit` (jeweils Duplikat der Feature-Logik; für `tasks` ergänzen, besser eine Quelle in `ViewsEnum`).
- Ein älterer Client verwirft `tasks` aus `view_ordering` beim Speichern; akzeptiert.
- 6 Einträge in Bottom-Bar/Drawer/Rail visuell prüfen (Material empfiehlt max. 5). Fallback: Aufgaben-Tab ist ohnehin nur bei aktiviertem Feature sichtbar.

**Umbenennung:** neuer Key `shoppingShort` (de "Einkauf", en "Shopping") nur für den Tab-Kurznamen in `views_enum.dart`; `loc.list` bleibt (wird auch in `settings_page.dart` genutzt). Andere Sprachen fallen bis zur Weblate-Übersetzung auf en zurück.

**Aufgaben-Seite:** einspaltige Liste; Sortierung überfällig → nach Fälligkeit → eigene → alphabetisch; undatierte folgen den datierten. Zeile: Name, Zuständiger, Fälligkeit (überfällig rot). Long-Press = erledigt mit Bestätigung. Tap = Bearbeiten (Name, Zuweisung/offen, Rotation + Teilnehmer, wiederkehrend, Fälligkeit, Intervall). Aufgaben nur online. ca. 20 neue l10n-Keys in `app_en.arb`.

## 7. Phasen

1. **MVP-A:** Toggle + Schalter, Modelle/Migration, CRUD, `recurring`, Rotation, `done` mit 409, Tab, Liste, Tests.
2. **MVP-B:** Fälligkeit und Häufigkeit (Tag/Woche/Monat), Completion-Endpunkt.
3. **Später:** Historie-/Statistik-UI pro Person (inkl. `created_by`), Undo (`previous_assigned_to`), Echtzeit via Socket.IO, ggf. zeitgesteuerte Rotation.

## 8. Tests

Backend (Muster `test_api_planner.py`): CRUD, gesamte Validierungsmatrix, Rotation inkl. Randfälle, Häufigkeitsberechnung (Tag/Woche/Monat inkl. Monatsende, Vergangenheit/Zukunft, `done_on`), Schalter-403, 409, Berechtigung fremder Haushalte, User-/Mitglied-/Haushaltslöschung, Migration auf SQLite und PostgreSQL. Flutter: Tests für `addMissing` und Sortierung; vorhandene Teststruktur zuerst prüfen.

## 9. Risiken und Aufwand

- Aufwand realistisch ca. +50–80 % gegenüber einem reinen Rotations-MVP (Backend ca. 10 Dateien, Flutter ca. 15, plus Tests und Migration), ca. 2 Wochen (Backend 3–4 Tage, Flutter 4–5 Tage, Feinschliff 1–2 Tage).
- Upstream-Fit: Der Maintainer wollte in #512 keine Fälligkeiten und dachte in #55 an ein Tab-Untermenü. Empfehlung: Konzept vorab als Issue-Kommentar abstimmen und den Fork-Commit "feat: Add household chores tracking feature" (1ARdotNO) vorher sichten (nicht geprüft).
- Zeitzonen: durch `done_on` entschärft, `due_date` bleibt zeitzonenfreies Datum.
- `tasks_only_assignee_can_complete` wird serverseitig erzwungen, `tasks_feature` nicht: bewusst, aber zu dokumentieren.

## 10. Entscheidungen und Rest

Geklärt: Intervall = Häufigkeit der Aufgabe (täglich/wöchentlich/monatlich/eigen); Rotation läuft bei jedem Erledigen. Haushaltsschalter "nur Zugewiesene dürfen abhaken". Intern `task`. Der leere Anforderungspunkt war ein Formatierungsfehler.
Offen: UI-Name des Tabs (Vorschlag "Aufgaben"/"Tasks"), Scope-Split (siehe §7).

## 11. Review 3: Korrekturen (gelten vor allem Früheren)

1. **Admin-Definition:** "Admin" = `HouseholdMember.admin` oder `owner` des Haushalts. `authorize_household` lässt zusätzlich Server-Admins durch (`helpers/authorize_household.py`); diese gelten ebenfalls. Eine Hilfsfunktion `is_household_admin` wird für Schalter und `assigned_to`-Änderung genutzt; `/tasks/<id>` und `/done` prüfen über `checkAuthorized`/`isAuthorized`.
2. **Household-API:** `tasks_feature` und `tasks_only_assignee_can_complete` in `controller/household/schemas.py` und `household_controller.py` (Create und Update, Update nur `RequiredRights.ADMIN`) ergänzen.
3. **Positionen:** `UNIQUE(task_id, position)` entfällt (nicht deferrable auf PostgreSQL, Neunummerieren scheitert sonst mittendrin). Sortierung nur über Index; beim Ändern/Entfernen werden Teilnehmer in Python neu nummeriert (Zeilen löschen und neu einfügen).
4. **Random-Rotation und Mitglied-Entfernung:** `random` hat keinen Nachfolger; bei Entfernung des Zuständigen wird zufällig ein verbleibender Teilnehmer gewählt. Bei aktivem Schalter bleibt ein offener Task für jedes Mitglied abhakbar. `User.delete()` räumt alle Haushalte des Users auf. Die Aufräumlogik läuft vor der Owner-Übergabe in derselben Transaktion.
5. **Historie beim Löschen:** Löschen eines Tasks löscht dessen Completions (bewusst, MVP). `task_completion` erhält zusätzlich `task_name` (Snapshot) für spätere Auswertung. Indizes: `task.household_id`, `task.assigned_to`, `task_completion.task_id`/`household_id`.
6. **`addMissing`:** Auflösung iterativ in Enum-Reihenfolge, fehlende View hinter ihren nächsten vorhandenen Vorgänger im Enum, sonst an den Anfang; `more` zuletzt. Sichtbarer Index-Sprung für Bestandshaushalte (gemerkter Tab, Deeplinks) wird akzeptiert. Neuer Test in `kitchenowl/test/models/household_test.dart`.
7. **Startseite:** `router.dart:256` nimmt `viewOrdering.first`; inaktive Views (Feature aus) werden vorher herausgefiltert. `tasks` Default `false` in `fromJson`, `isViewActive` und allen drei Cubits.
8. **`done_on`:** nur Basis für die neue Fälligkeit, `done_at` bleibt Serverzeit. Fehlt `done_on` (alter Client): Server-UTC-Datum. Bereits erledigter Einmal-Task: 409 (nach 403, vor Rotation).
9. **Wertebereiche:** `repeat_every`: Tag 1–365, Woche 1–52, Monat 1–24. Name nicht leer, max. 128. Datumsüberlauf abfangen (400). Monatsarithmetik mit `calendar.monthrange`. `recurring=true` ohne Häufigkeit und Datum = bleibt dauerhaft stehen (gewollt). UI erzwingt Fälligkeit, sobald eine Häufigkeit gewählt wird.
10. **Migration:** eine Revision (3 Tabellen, 3 Household-Spalten), `sa.false()` als `server_default`, Head-Revision vorher ermitteln, kein Datenumzug.
