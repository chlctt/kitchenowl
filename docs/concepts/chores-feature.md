# Konzept: Aufgaben/Chores (Issue #512 und #55, TomBursch/kitchenowl)

Status: **v5, konsolidierter Endstand** (zwei unabhängige Reviews eingearbeitet; frühere Fassungen in der Git-Historie). Offene Entscheidungen siehe §10.

## 1. Anforderungen (Stand Auftraggeber)

Ausgangspunkt #512 (rotierende Haushalts-Chores) und #55 (ToDo-Listen), erweitert durch Entscheidungen:

- Allgemeine Aufgaben ("Tasks") pro Haushalt, einzeilig, ohne Unteraufgaben und ohne Gamification.
- Zuweisung: fest (ein Mitglied), offen (niemand) oder Rotation (`ordered` fest oder `random` zufällig).
- Fälligkeit optional. Merkmal "wiederkehrend" (`recurring`): wiederkehrende Aufgaben bleiben stehen, einmalige verschwinden beim Erledigen. Wiederholungsintervall in Tagen frei definierbar.
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
- `tasks_complete_policy` String NOT NULL, Default `anyone` (`anyone` | `assignee`). Änderbar nur durch Admin/Owner.

**task**
- `id`, `household_id` (FK, index, ORM `Household.tasks` mit `cascade="all, delete-orphan"`)
- `name` String(128) NOT NULL
- `recurring` Boolean NOT NULL default false
- `due_date` Date NULL (reines Datum ohne Uhrzeit)
- `repeat_interval_days` Integer NULL (1..3650)
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
| `repeat_interval_days` gesetzt | nur zusammen mit `recurring=true` **und** `due_date`; sonst 400 |
| `recurring` true→false | `repeat_interval_days` wird genullt (kein 400) |
| `due_date` per Update auf NULL | `repeat_interval_days` wird mit genullt |
| `rotation_mode` `ordered`/`random` | mindestens 2 `participants`, alle Mitglieder des Haushalts, keine Duplikate; `assigned_to` ∈ Teilnehmer, sonst auf kleinste Position gesetzt |
| `rotation_mode` `none` | `participants` werden ignoriert und geleert; `assigned_to` = Mitglied oder NULL (offen) |
| Offen (`assigned_to` NULL) | nur bei `none`; bei Rotation immer ein Zuständiger |
| `assigned_to` ändern | erlaubt für alle Mitglieder bei Policy `anyone`; bei `assignee` nur Zuständiger oder Admin (verhindert Umgehung) |
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

Das Backend erzwingt `tasks_feature` nicht (wie Planner, bewusste Entscheidung); `tasks_complete_policy` wird erzwungen.

**`done`-Logik** (Reihenfolge der Prüfungen: 404 → 403 Policy → 400 bereits erledigt → 409 Konflikt):
- Body: `expected_assigned_to` (Pflichtfeld, `null` = erwartet offen) und `done_on` (lokales Datum des Clients, nur erlaubt ±1 Tag zur Server-UTC-Zeit; Server nutzt es als "heute"). Bei Abweichung des aktuellen `assigned_to`: 409, Client lädt neu (verhindert doppeltes Weiterrotieren).
- Policy `assignee`: nur der Zuständige (oder Admin) darf, offene Tasks darf jedes Mitglied; bei `anyone` jedes Mitglied.
- Eine Transaktion: Completion schreiben, `last_done_at` setzen, dann:
  - `recurring=false`: `completed_at` setzen, Rotation irrelevant.
  - `recurring=true`: Rotation `ordered`: nächster nach dem *bisherigen Zuständigen* (nicht nach dem Erledigenden), zyklisch; `random`: zufällig unter den anderen Teilnehmern; `none`: unverändert.
  - `recurring=true` mit Intervall: neue Fälligkeit = alte `due_date` + Intervall; liegt sie vor `done_on`, dann `done_on` + Intervall (kein Aufholen).
- Intervalle sind Tage. UI-Presets: täglich (1), wöchentlich (7), alle 14 Tage, eigener Wert. Monatsintervall (Kalendermonat) bewusst nicht im MVP.

## 6. Frontend (Flutter, `kitchenowl/`)

**Tab:**
- `ViewsEnum.tasks` an Index 1; Default `ViewsEnum.values` ergibt: Einkauf, Aufgaben, Rezepte, Planer, Bilanzen, Mehr. Alle Index-Listen in `views_enum.dart` (`toLocalizedString`, `toLocalizedShortString`, `toIcon`, `toSelectedIcon`, `isOptional`) erweitern, besser auf `switch`-Ausdrücke umstellen (sonst Laufzeit-RangeError); `parse`, `floatingActionButton` (Task-FAB), `isViewActive` (`featureTasks ?? false`).
- `addMissing` ist heute "fehlende Views in Enum-Reihenfolge anhängen" (`more` wird in `household.dart` vorher entfernt und im Enum zuletzt eingefügt). Neu: fehlende View direkt hinter ihrem Vorgänger im Enum einfügen, falls vorhanden, sonst am Anfang. Für `tasks`: hinter `items`, sonst vorne; `more` zuletzt. Gilt generisch, daher mit Test absichern, dass Bestandshaushalte mit vollständiger Liste unverändert bleiben.
- Weitere Stellen: `household_page.dart` (Switch in `_onItemTapped`, Refresh-Zweig, `MultiBlocProvider` mit `TaskListCubit`), `router.dart` (Shell-Route `tasks`), `sliver_household_feature_settings.dart` (Toggle, Policy-Auswahl, Annahme "`more` zuletzt" bei Reset prüfen), drei Cubits `household_add_cubit`, `household_update_cubit`, `household_add_update_cubit` (jeweils Duplikat der Feature-Logik; für `tasks` ergänzen, besser eine Quelle in `ViewsEnum`).
- Ein älterer Client verwirft `tasks` aus `view_ordering` beim Speichern; akzeptiert.
- 6 Einträge in Bottom-Bar/Drawer/Rail visuell prüfen (Material empfiehlt max. 5). Fallback: Aufgaben-Tab ist ohnehin nur bei aktiviertem Feature sichtbar.

**Umbenennung:** neuer Key `shoppingShort` (de "Einkauf", en "Shopping") nur für den Tab-Kurznamen in `views_enum.dart`; `loc.list` bleibt (wird auch in `settings_page.dart` genutzt). Andere Sprachen fallen bis zur Weblate-Übersetzung auf en zurück.

**Aufgaben-Seite:** einspaltige Liste; Sortierung überfällig → nach Fälligkeit → eigene → alphabetisch; undatierte folgen den datierten. Zeile: Name, Zuständiger, Fälligkeit (überfällig rot). Long-Press = erledigt mit Bestätigung. Tap = Bearbeiten (Name, Zuweisung/offen, Rotation + Teilnehmer, wiederkehrend, Fälligkeit, Intervall). Chores nur online. ca. 20 neue l10n-Keys in `app_en.arb`.

## 7. Phasen

1. **MVP-A:** Toggle + Policy, Modelle/Migration, CRUD, `recurring`, Rotation, `done` mit 409, Tab, Liste, Tests.
2. **MVP-B:** Fälligkeit und Wiederholungsintervall, Completion-Endpunkt.
3. **Später:** Historie-/Statistik-UI pro Person (inkl. `created_by`), Undo (`previous_assigned_to`), Echtzeit via Socket.IO, ggf. Zeitintervall-Rotation, Kalendermonat.

## 8. Tests

Backend (Muster `test_api_planner.py`): CRUD, gesamte Validierungsmatrix, Rotation inkl. Randfälle, Intervallberechnung (Vergangenheit/Zukunft, `done_on`), Policy-403, 409, Berechtigung fremder Haushalte, User-/Mitglied-/Haushaltslöschung, Migration auf SQLite und PostgreSQL. Flutter: Tests für `addMissing` und Sortierung; vorhandene Teststruktur zuerst prüfen.

## 9. Risiken und Aufwand

- Aufwand realistisch ca. +50–80 % gegenüber dem ursprünglichen Chores-MVP (Backend ca. 10 Dateien, Flutter ca. 15, plus Tests und Migration), mehrere Tage bis 1–2 Wochen.
- Upstream-Fit: Der Maintainer wollte in #512 keine Fälligkeiten und dachte in #55 an ein Tab-Untermenü. Empfehlung: Konzept vorab als Issue-Kommentar abstimmen und den Fork-Commit "feat: Add household chores tracking feature" (1ARdotNO) vorher sichten (nicht geprüft).
- Zeitzonen: durch `done_on` entschärft, `due_date` bleibt zeitzonenfreies Datum.
- `tasks_complete_policy` wird serverseitig erzwungen, `tasks_feature` nicht: bewusst, aber zu dokumentieren.

## 10. Offene Entscheidungen

1. **F3-Auslegung:** Gemeint ist aktuell "Wiederholungsintervall frei definierbar, Rotation bei jedem Erledigen". Alternative: Die Rotation wechselt nach Zeitintervall (z. B. wöchentlich Putzplan). Das ändert das Schema (`rotation_interval_days`).
2. **F4-Auslegung:** Aktuell "Policy wer abhaken darf". Alternative: nur das Aktivieren pro Haushalt (dann entfällt die Policy-Spalte).
3. **Benennung:** intern `task`, Tab "Aufgaben"/"Tasks" (Alternative "Chores").
4. **Scope-Split:** MVP-A/B wie in §7 oder in einem Schritt?
5. Der dritte, leere Anforderungspunkt aus einer früheren Nachricht ist weiter offen.
