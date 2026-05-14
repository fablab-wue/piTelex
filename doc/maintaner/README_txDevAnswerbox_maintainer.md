Hier ist eine technische Beschreibung für Maintainer.

# piTelex Answerbox / Nightbox

## Technische Beschreibung für Maintainer

Die **Answerbox** ist ein zusätzliches piTelex-Device, das außerhalb definierter Aktivzeiten den **logischen Druckerpfad** übernimmt. Ziel ist, eingehende Nachrichten nachts **nicht** auf dem realen Fernschreiber auszugeben, sondern kontrolliert mitzuschneiden, zu speichern und später wieder auszugeben.

Der Ansatz ist bewusst konservativ gehalten:

* möglichst wenig Eingriff in bestehende Gerätepfade
* keine Umdefinition der Buslogik
* Rohdaten bleiben Rohdaten
* Zustandswechsel nur an klar definierten Stellen

Die aktuelle Grundlage ist version `3.1.0`. 

---

## 1. Grundidee

Die Answerbox arbeitet als eigenes Device im Bus und unterscheidet drei Hauptbereiche:

1. **Zeitlogik**

   * Tag/Nacht nach Wochenplan
   * Umschaltung nur im lokalen `ZZ`-Kontext

2. **Nachtbetrieb**

   * bei eingehenden Verbindungen emuliert die Answerbox nachts den Drucker
   * sie beantwortet den Start mit `AA`
   * sie sammelt den Text mit
   * sie speichert die Nachricht in Dateien

3. **Replay**

   * gespeicherte Nachrichten werden später wieder an den lokalen Druckerpfad ausgegeben
   * normale Nachrichten nur innerhalb des Aktivzeitfensters
   * Urgent-Nachrichten mit Vorrang und Sonderbehandlung

---

## 2. Zeitmodell

Die Aktivzeiten werden über `weekly_schedule` definiert, z. B.:

```json
"weekly_schedule": {
  "mon": { "active": [["08:00", "22:00"]] },
  "tue": { "active": [["08:00", "22:00"]] },
  "wed": { "active": [["08:00", "22:00"]] },
  "thu": { "active": [["08:00", "22:00"]] },
  "fri": { "active": [["08:00", "23:00"]] },
  "sat": { "active": [["09:00", "23:00"]] },
  "sun": { "active": [["09:00", "13:00"], ["18:30", "22:00"]] }
}
```

Die Answerbox führt dafür lokal:

* `_mode_daytime`
* `_forced_daytime`
* `_urgent_daytime`
* `_zz_active`

`_desired_daytime()` entscheidet in dieser Reihenfolge:

1. `forced_daytime`
2. `urgent_daytime`
3. Zeitfenster

`DTM/NTM` werden nur gesendet, wenn die Box lokal noch in `ZZ` ist. Das ist Absicht, damit kein Zustandswechsel mitten im aktiven Ablauf in den Bus gedrückt wird. 

---

## 3. Nachtbetrieb

### 3.1 Eingehende Verbindung

Kommt nachts ein `A`, dann:

* startet die Box ihren Capture-Pfad
* sendet `AA`
* nimmt danach alle Zeichen mit

Das geschieht in `_handle_escape()` und `_start_capture()`. 

### 3.2 Mitschnitt

Die Box sammelt den Text in `_current_msg`.

Zusätzlich wird nachts:

* der „not printed“-Status über `~2` / `~0` signalisiert
* `#` abgefangen und durch einen WRU-Block ersetzt:

  * `CR CR LF + wru_id + CR CR LF`

Der WRU-Text wird aus der globalen `telex.json` gelesen. 

### 3.3 Ende der Nachricht

Bei `Z` im Capture:

* Capture wird beendet
* Text wird zusammengebaut
* normale Nachricht oder Urgent wird erkannt
* Nachricht wird gespeichert

---

## 4. Speicherung

### 4.1 Normale Nachrichten

Normale Nachrichten werden unter Zeitstempel-Dateinamen gespeichert:

`YYYY-MM-DD_HH-MM-SS-mmm.txt`

### 4.2 Urgent-Nachrichten

Urgent-Dateien werden mit Präfix gespeichert:

`urgent_YYYY-MM-DD_HH-MM-SS-mmm.txt`

Damit bleiben normale und dringende Nachrichten strikt getrennt. 

---

## 5. Urgent-Logik

### 5.1 Erkennung

Urgent wird über Schlüsselwörter erkannt:

* `=urgent=`
* `=eil=`
* `=blitz=`

Dabei wird **nicht** der gespeicherte Rohtext verändert.
Für die Erkennung wird nur ein Prüftext gebildet:

* `lower()`
* `<` und `>` werden entfernt

Das war nötig, weil in realen Mitschnitten Marker wie `=<BLITZ>=` vorkommen können. Der gespeicherte Text bleibt trotzdem unverändert roh. 

### 5.2 Verhalten

Wenn eine Urgent-Nachricht gespeichert wurde:

* setzt die Box `_urgent_daytime = True`
* stößt `DTM` an, sobald das lokal zulässig ist
* priorisiert Urgent-Dateien vor normalen Nachrichten

### 5.3 Replay von Urgent

Urgent-Replay darf **auch außerhalb** des normalen Zeitfensters starten, aber weiter nur in lokalem `ZZ`.

Beim Ausdruck bekommt die Urgent-Nachricht einen Weckrahmen:

* vor dem Text
* nach dem Text

Im aktuellen Code ist das als Bell-/Klingelmuster umgesetzt. 

### 5.4 Rückfall

Nach dem Abarbeiten einer Urgent-Datei:

* wird geprüft, ob noch weitere `urgent_*.txt` existieren
* falls ja, bleibt `_urgent_daytime = True`
* falls nein, fällt die Box wieder auf normale Zeitlogik zurück

---

## 6. Replay

`idle2Hz()` übernimmt das Replay-Starten.

Reihenfolge:

1. `update_mode()`
2. kein Replay, wenn Capture aktiv ist
3. kein Replay außerhalb von lokalem `ZZ`
4. zuerst `urgent_*.txt`
5. danach normale Dateien nur im aktiven Zeitfenster

Normale Nachrichten werden gesammelt ausgegeben und mit Trennern versehen:

* `+++ NEXT +++`
* `+++ LAST +++`

Urgent wird einzeln und bevorzugt behandelt. 

---

## 7. Nachts AT-taste nutzen

Die wichtigste Erkenntnis aus den TW39-Tests war:

**Die direkte Behandlung von `AT` in der Answerbox kommt zu spät.**

Der reale Ablauf am TW39 ist:

* User drückt Anruftaste
* Fernschaltgerät erhöht Strom
* Druckerpfad erkennt den lokalen Anrufwunsch
* erst danach folgen logisch `AT`, `WB`, später `A`, `AA`

Das war nur durch ein zusätzliches "Sake-Up-Signal zu lösen. 

### 7.1 Neue Architektur: `WUP`

Dafür wurde ein neues internes Wecksignal eingeführt:

`ESC+WUP`

Idee:

* der Druckerpfad erkennt nachts den **lokalen** AT-Wunsch
* er sendet **nicht sofort `AT`**, sondern zuerst `WUP`
* die Answerbox setzt dadurch temporär Daymode
* danach läuft der normale lokale AT-Ablauf weiter

### 7.2 Verhalten der Answerbox bei `WUP`

Im Version `3.1.0`:

* `WUP` setzt

  * `_forced_daytime = True`
  * `DTM` wird noch in lokalem `ZZ` gequeued
  * danach setzt die Box **nur lokal** `_zz_active = False`
* es wird **kein** zusätzliches `Z` oder anderes ESC erzeugt

Das ist wichtig:
`_zz_active` ist nur ein lokaler Merker der Answerbox, kein fremder Live-Zustand. Darum reicht lokales Rücksetzen. Ein zusätzliches `ESC Z` wäre unnötiger Seiteneffekt.

---

## 8. Schematische Drucker-Änderungen

Die Druckerpfade mussten für das neue AT-/Wake-Modell angepasst werden.

### 8.1 Alt

Bisher war das Modell sinngemäß:

* lokaler AT-Wunsch erkannt
* Druckerpfad sendet direkt `ESC+AT`
* nachts kollidierte das mit der Nightbox, weil Daymode noch nicht wirksam war

### 8.2 Neu

Jetzt ist die Zielarchitektur:

**Tagsüber**

* alter Pfad unverändert

**Nachts**

* normaler Druckerpfad bleibt gesperrt
* nur lokaler AT-Wunsch und Moduswechsel laufen über einen schmalen Sonderpfad

### 8.3 Schema

```
Lokaler AT-Wunsch am Drucker
        |
        v
Druckerpfad erkennt lokalen Start
        |
        +-- tagsüber --> sofort normales ESC AT
        |
        +-- nachts  --> ESC WUP
                        pending_local_at = True
                                |
                                v
                        Answerbox setzt forced_daytime
                        Answerbox queued DTM
                        Answerbox verlässt lokal ZZ
                                |
                                v
                        Druckerpfad erhält DTM
                        daytime = True
                        wenn pending_local_at:
                            ESC AT senden
                            pending_local_at = False
                                |
                                v
                        normaler Tagesablauf:
                        AT -> WB -> Wahl -> A -> AA
```

### 8.4 Gemeinsame Prinzipien für die Druckerpfade

Die umgebauten Druckerpfade benutzen sinngemäß:

* `_daytime`
* `_pending_mode_cmd`
* `_pending_local_at`

Nachts gilt:

* kein normaler Sende-/Druckpfad
* keine normale Zeichenverarbeitung
* kein normales Hardwarelesen in den Bus
* nur:

  * `DTM/NTM`
  * lokaler AT-Wunsch → `WUP`

Nach `DTM`:

* Daymode wird aktiv
* vorgemerkter lokaler `AT` wird erst dann sauber in den Bus gegeben

### 8.5 Betroffene Druckerpfade

Das Schema wurde vorbereitet für:

* `RPiTTY`
* `CH340TTY`
* `ED1000SC`

---

## 9. Teststand

Wichtig für Maintainer:

**Praktisch getestet wurde bisher nur die TW39-/RPiTTY-Variante.**

Die Abläufe für:

* `CH340TTY`
* `ED1000SC`

wurden analog umgesetzt, konnten aber von mir selbst **nicht unter realer Hardware** geprüft werden.

Darum wird ausdrücklich um Tests durch Dritte gebeten, insbesondere für:

* CH340-basierte Druckerpfade
* ED1000-Betrieb
* lokales AT-Verhalten bei Nacht
* Rückfall nach `ZZ`
* normales Replay / Urgent-Replay

Ohne solche Tests wäre es unredlich, diese Varianten als belastbar fertig zu bezeichnen.

---

## 10. Aktueller Status

Die Answerbox ist eine **Test- und Entwicklungsfunktion**, keine endgültig abgeschlossene Komponente.

Der Stand ist:

* Grundfunktion Nachtbetrieb vorhanden
* Replay vorhanden
* Urgent vorhanden
* Zeitfenster vorhanden
* neues Wake-/AT-Modell vorhanden
* TW39 praktisch getestet
* CH340 und ED1000 erst als übertragener Entwurf vorhanden

Für einen Vorschlag in den Testing-Zweig sollte vor allem noch geprüft werden:

* Verhalten an Tag/Nacht-Grenzen
* lokaler AT-Start nachts
* sauberes Zusammenspiel von `WUP -> DTM -> AT`
* CH340/ED1000 unter echter Hardware

