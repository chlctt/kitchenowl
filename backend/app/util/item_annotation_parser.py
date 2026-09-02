"""Parst Inline-Annotationen aus einer Artikeleingabe.

Erkannt werden zwei Dinge, die beim Hinzufügen eines Artikels direkt in
den Text geschrieben werden können:

* ``@name`` – weist den Artikel einem Haushaltsmitglied zu (unscharfe Suche
  über Anzeige- und Benutzername).
* ein Datum ("15.09.", "morgen", "next monday", "2026-09-15", "20. Sept") –
  legt fest, wann der Artikel eingekauft werden soll.

Die erkannten Bestandteile werden aus dem Text entfernt, sodass der
verbleibende Rest als eigentlicher Artikelname verwendet werden kann.
"""

from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from app.models import User


# --- Wörterbücher (Mehrsprachig, bewusst pragmatisch gehalten) ---------------

# Relative Tagesangaben -> Offset in Tagen ab dem Referenzdatum
_RELATIVE_DAYS: dict[str, int] = {
    # heute
    "today": 0,
    "heute": 0,
    "hoy": 0,
    "aujourd'hui": 0,
    "oggi": 0,
    "vandaag": 0,
    "hoje": 0,
    # morgen
    "tomorrow": 1,
    "morgen": 1,
    "mañana": 1,
    "manana": 1,
    "demain": 1,
    "domani": 1,
    "amanhã": 1,
    "amanha": 1,
    # übermorgen
    "overmorrow": 2,
    "übermorgen": 2,
    "uebermorgen": 2,
    "aftermorgen": 2,
    "dopodomani": 2,
    "overmorgen": 2,
}

# Wochentage -> Montag=0 .. Sonntag=6
_WEEKDAYS: dict[str, int] = {}
for _idx, _names in enumerate(
    [
        ("monday", "mon", "montag", "lunes", "lundi", "lunedì", "lunedi", "maandag"),
        ("tuesday", "tue", "dienstag", "martes", "mardi", "martedì", "martedi", "dinsdag"),
        ("wednesday", "wed", "mittwoch", "miércoles", "miercoles", "mercredi", "mercoledì", "mercoledi", "woensdag"),
        ("thursday", "thu", "donnerstag", "jueves", "jeudi", "giovedì", "giovedi", "donderdag"),
        ("friday", "fri", "freitag", "viernes", "vendredi", "venerdì", "venerdi", "vrijdag"),
        ("saturday", "sat", "samstag", "sonnabend", "sábado", "sabado", "samedi", "sabato", "zaterdag"),
        ("sunday", "sun", "sonntag", "domingo", "dimanche", "domenica", "zondag"),
    ]
):
    for _n in _names:
        _WEEKDAYS[_n] = _idx

# Monatsnamen -> 1..12
_MONTHS: dict[str, int] = {}
for _idx, _names in enumerate(
    [
        ("january", "jan", "januar", "jänner", "janvier", "enero", "gennaio", "januari", "janeiro"),
        ("february", "feb", "februar", "février", "fevrier", "febrero", "febbraio", "februari", "fevereiro"),
        ("march", "mar", "märz", "maerz", "mars", "marzo", "maart", "março", "marco"),
        ("april", "apr", "avril", "abril", "aprile"),
        ("may", "mai", "mayo", "maggio", "maio"),
        ("june", "jun", "juni", "juin", "junio", "giugno", "junho"),
        ("july", "jul", "juli", "juillet", "julio", "luglio", "julho"),
        ("august", "aug", "août", "aout", "agosto", "augustus"),
        ("september", "sep", "sept", "septembre", "septiembre", "settembre", "setembro"),
        ("october", "oct", "okt", "oktober", "octobre", "octubre", "ottobre", "outubro"),
        ("november", "nov", "novembre", "noviembre", "novembro"),
        ("december", "dec", "dez", "dezember", "décembre", "decembre", "diciembre", "dicembre", "december", "dezembro"),
    ],
    start=1,
):
    for _n in _names:
        _MONTHS[_n] = _idx

# "in 3 Tagen" / "in 2 weeks" ...
_IN_UNIT_DAYS: dict[str, int] = {
    "day": 1,
    "days": 1,
    "tag": 1,
    "tage": 1,
    "tagen": 1,
    "week": 7,
    "weeks": 7,
    "woche": 7,
    "wochen": 7,
}


@dataclass
class ParsedItemAnnotations:
    name: str
    assigned_to_id: int | None = None
    due_date: date | None = None
    # Beschreibung ohne die erkannten "@name"/Datums-Bestandteile
    description: str | None = None


def _clamp_day(year: int, month: int, day: int) -> date:
    last = monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _roll_forward(candidate: date, reference: date) -> date:
    """Verschiebt ein Datum ohne Jahresangabe auf das nächste Vorkommen."""
    if candidate >= reference:
        return candidate
    try:
        return _clamp_day(candidate.year + 1, candidate.month, candidate.day)
    except ValueError:
        return candidate


def _match_date(text: str, reference: date) -> tuple[date, int, int] | None:
    """Findet die erste Datumsangabe. Gibt (Datum, start, end) zurück."""

    lowered = text.lower()

    # ISO: 2026-09-15
    m = re.search(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)", lowered)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return _clamp_day(y, mo, d), m.start(), m.end()

    # Numerisch, tag-zuerst: 15.09 / 15.9.2026 / 15/09 / 15-9-26
    # Fallback monat-zuerst (z.B. "09/15"), wenn tag-zuerst unmöglich ist.
    for m in re.finditer(
        r"(?<!\d)(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\.?(?!\d)", lowered
    ):
        d, mo = int(m[1]), int(m[2])
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            if 1 <= mo <= 31 and 1 <= d <= 12 and "/" in m[0]:
                d, mo = mo, d  # amerikanische Schreibweise MM/DD
            else:
                continue
        if m[3]:
            y = int(m[3])
            if y < 100:
                y += 2000
            return _clamp_day(y, mo, d), m.start(), m.end()
        return _roll_forward(_clamp_day(reference.year, mo, d), reference), m.start(), m.end()

    # Monatsname: "20. September" / "September 20" / "20 sep 2026"
    month_alt = "|".join(sorted(map(re.escape, _MONTHS), key=len, reverse=True))
    m = re.search(
        rf"(?<!\w)(\d{{1,2}})\.?\s+({month_alt})\.?(?:\s+(\d{{4}}))?(?!\w)", lowered
    )
    if not m:
        m2 = re.search(
            rf"(?<!\w)({month_alt})\.?\s+(\d{{1,2}})(?:\.|,)?(?:\s+(\d{{4}}))?(?!\w)",
            lowered,
        )
        if m2:
            mo = _MONTHS[m2[1]]
            d = int(m2[2])
            y = int(m2[3]) if m2[3] else None
            if 1 <= d <= 31:
                base = _clamp_day(y or reference.year, mo, d)
                return (base if y else _roll_forward(base, reference)), m2.start(), m2.end()
    else:
        d = int(m[1])
        mo = _MONTHS[m[2]]
        y = int(m[3]) if m[3] else None
        if 1 <= d <= 31:
            base = _clamp_day(y or reference.year, mo, d)
            return (base if y else _roll_forward(base, reference)), m.start(), m.end()

    # "in 3 Tagen" / "in 2 weeks"
    unit_alt = "|".join(sorted(map(re.escape, _IN_UNIT_DAYS), key=len, reverse=True))
    m = re.search(rf"(?<!\w)in\s+(\d{{1,3}})\s+({unit_alt})(?!\w)", lowered)
    if m:
        return (
            reference + timedelta(days=int(m[1]) * _IN_UNIT_DAYS[m[2]]),
            m.start(),
            m.end(),
        )

    # Relative Tagesangaben
    rel_alt = "|".join(sorted(map(re.escape, _RELATIVE_DAYS), key=len, reverse=True))
    m = re.search(rf"(?<!\w)({rel_alt})(?!\w)", lowered)
    if m:
        return reference + timedelta(days=_RELATIVE_DAYS[m[1]]), m.start(), m.end()

    # Wochentage -> nächstes Vorkommen (heute zählt nicht mit)
    wd_alt = "|".join(sorted(map(re.escape, _WEEKDAYS), key=len, reverse=True))
    m = re.search(rf"(?<!\w)(?:next\s+|nächsten?\s+|kommenden?\s+)?({wd_alt})(?!\w)", lowered)
    if m:
        target = _WEEKDAYS[m[1]]
        delta = (target - reference.weekday()) % 7
        if delta == 0:
            delta = 7
        return reference + timedelta(days=delta), m.start(), m.end()

    return None


def _normalize(value: str) -> str:
    return re.sub(r"[\s._-]+", "", value.strip().lower())


def _match_member(token: str, members: Iterable["User"]) -> int | None:
    """Unscharfe Zuordnung eines @-Tokens zu einem Haushaltsmitglied."""

    needle = _normalize(token)
    if not needle:
        return None

    scored: list[tuple[int, int]] = []  # (score, user_id) – kleiner ist besser
    for user in members:
        candidates = {
            _normalize(user.username),
            _normalize(user.name),
            _normalize(user.name.split(" ")[0]) if user.name else "",
        }
        candidates.discard("")
        best: int | None = None
        for cand in candidates:
            if cand == needle:
                best = 0
            elif best is None or best > 1:
                if cand.startswith(needle) or needle.startswith(cand):
                    best = min(best if best is not None else 99, 1)
                elif needle in cand or cand in needle:
                    best = min(best if best is not None else 99, 2)
        if best is not None:
            scored.append((best, user.id))

    if not scored:
        return None
    scored.sort()
    return scored[0][1]


_ASSIGN_RE = re.compile(r"(?<!\S)@([^\s@]+)")


def parse_item_annotations(
    name: str,
    members: Iterable["User"] | None = None,
    *,
    description: str | None = None,
    reference_date: date | None = None,
) -> ParsedItemAnnotations:
    """Zerlegt eine Eingabe in Name, Zuweisung und Datum.

    ``description`` wird – falls angegeben – zusätzlich nach einem ``@name``
    und einem Datum durchsucht (der Name bleibt davon unberührt).
    """

    members = list(members or [])
    reference_date = reference_date or datetime.now().date()

    assigned_to_id: int | None = None
    due_date: date | None = None

    # Verbindungswörter, die typischerweise direkt vor einer Datumsangabe
    # stehen ("... Pizza am Freitag") und nach dem Entfernen übrig bleiben.
    _stop = r"am|um|bis|ab|im|on|at|by|per|fuer|für"

    def _extract(text: str, *, is_name: bool) -> str:
        nonlocal assigned_to_id, due_date

        # Zuweisung
        if assigned_to_id is None:
            m = _ASSIGN_RE.search(text)
            if m:
                match_id = _match_member(m[1], members)
                if match_id is not None:
                    assigned_to_id = match_id
                    text = (text[: m.start()] + " " + text[m.end() :]).strip()

        # Datum
        if due_date is None:
            found = _match_date(text, reference_date)
            if found:
                due_date, start, end = found
                before = text[:start]
                # ein direkt vorangehendes Verbindungswort mitentfernen
                before = re.sub(
                    rf"(?i)\s(?:{_stop})\s*$", " ", before
                )
                text = (before + " " + text[end:]).strip()

        return re.sub(r"\s{2,}", " ", text).strip(" ,")

    cleaned_name = _extract(name, is_name=True)
    cleaned_description = description
    if description:
        cleaned_description = _extract(description, is_name=False)

    return ParsedItemAnnotations(
        name=cleaned_name or name.strip(),
        assigned_to_id=assigned_to_id,
        due_date=due_date,
        description=cleaned_description,
    )
