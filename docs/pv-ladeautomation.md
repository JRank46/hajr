# PV-Ladeautomation: Betrieb und Technik

## Zweck und Zustaendigkeiten

Die Automation steuert eine go-eCharger-Wallbox fuer zwei Betriebsarten:

- **Tagesladen:** PV-Ueberschuss laden; der Tages-Ziel-SOC dient zudem als
  Grundlage fuer eine spaetere Zwangsladung.
- **Adhoc-Laden:** Laden bis zum Adhoc-Ziel-SOC, entweder nur mit
  PV-Ueberschuss oder mit der konfigurierten Maximalleistung.

Die Ablaufsteuerung liegt in `automations/pv_charging_schedule.yaml`; sie
startet pro Sekunde den Adhoc- oder Tages-Handler. Der Takt darf schneller sein
als die Stellwertaenderungen: Phasenmodus und Stromlimit sind separat gegen
haeufiges Umschalten abgesichert.

## Wallbox-Steuerung

Fuer die vorhandene go-eCharger-Integration gelten diese Werte:

| Entity | Wert | Bedeutung |
| --- | --- | --- |
| `select.go_echarger_325099_force_state` | `Neutral` | Laden freigeben |
| `select.go_echarger_325099_force_state` | `Off` | Laden sperren |
| `select.go_echarger_325099_force_state` | `On` | Nicht fuer den Ladebeginn verwenden; startet auf dieser Anlage nicht zuverlaessig |
| `select.go_echarger_325099_phase_switch_mode` | `Force_1` / `Force_3` | Ein- bzw. dreiphasiger Ladebetrieb |
| `number.go_echarger_325099_set_max_ampere_limit` | 6 bis 16 A | Stromvorgabe der Wallbox |

`force_state` wird sofort gesetzt. Die 5-Minuten-Stabilitaetspruefung darf nur
Phasenmodus und Stromlimit begrenzen, nicht die Ladefreigabe. Beim Tagesladen
bleibt die Freigabe bei PV-Stopp auf `Neutral`; der Sollstrom wird auf `0 A`
gesetzt. `Off` wird dort beim erreichten Ziel-SOC verwendet.

Die Mindestleistung ist 6 A. Einphasig entspricht das rund 1,38 kW,
dreiphasig rund 4,14 kW. Ab 4.000 W wird `Force_3` angefordert, darunter
`Force_1`.

## PV-Ueberschuss und Phasenwechsel

Der rohe Ueberschuss ist PV-Leistung minus Hausverbrauch. Fuer die
Laderegelung wird daraus ein gefilterter Wert abgeleitet. Die relevanten
Hysterese-Sensoren sind:

- `binary_sensor.pv_charge_start_ready`: mindestens die konfigurierte
  Einschaltschwelle fuer 60 Sekunden (Vorgabe 750 W).
- `binary_sensor.pv_charge_stop_required`: mindestens die konfigurierte
  Ausschaltschwelle fuer 5 Minuten (Vorgabe -500 W).

Der Wechsel von `Force_3` auf `Force_1` erfolgt erst, wenn der Wunsch 30
Minuten ohne Unterbrechung besteht. Der Zeitpunkt und die Vormerkung liegen in
`input_datetime.phase_switch_to_1_requested_at` und
`input_boolean.phase_switch_to_1_pending`. Der Wechsel auf drei Phasen bleibt
unverzoegert.

## Tagesladen und Zwangsladung

Die Tagesroutine nutzt den Ziel-SOC der naechsten konfigurierten Abfahrt. Sie
berechnet den Energiebedarf und die fuer eine rechtzeitige Abfahrt erforderliche
Mindestleistung.

Die separate Automation `automations/pv_force_charge_notifications.yaml` ist
zustaendig fuer die Zwangsladung. Sie laeuft minuetlich und plant genau einmal
pro Abfahrtszyklus eine Zwangsladung, wenn alle folgenden Bedingungen gelten:

- Tagesladen ist aktiviert und Zwangsladen nicht ausgesetzt.
- Der geschaetzte SOC liegt unter dem Tagesziel.
- `sensor.solcast_pv_forecast_prognose_aktuelle_stunde` liegt unter 500 Wh.
- Die Wallbox meldet nicht `Idle`.

Die Automation setzt zuerst
`input_boolean.daily_force_charge_notification_sent` und speichert den Start
eine Stunde spaeter in `input_datetime.daily_force_charge_start_at`. Danach
werden persistente und mobile Benachrichtigungen erzeugt. Das Flag verhindert
wiederholte Meldungen aus der minuetlichen Pruefung.

Ab dem gespeicherten Start wird mit voller Leistung geladen: `Force_3` und
16 A beziehungsweise 11.040 W. Ist die Wallbox zu diesem Zeitpunkt auf
`Complete`, bleibt der Strom bei 0 A; um 21:00 und 21:30 erfolgt jeweils
maximal eine Hinweisbenachrichtigung. Bei `Idle` wird stattdessen um 22:00
einmalig ueber das nicht angeschlossene Fahrzeug informiert, sofern der
Ziel-SOC fehlt.

`automations/pv_force_charge_cycle.yaml` setzt Aussetzung, Ankuendigungs- und
Complete-Meldungsflags nach der zugeordneten Abfahrt zurueck.

`sensor.pv_force_charge_status` zeigt im Dashboard eine geplante Startzeit,
eine aktive Zwangsladung oder `keine Zwangsladung geplant`.

## SOC-Schaetzung und manuelle Korrektur

`sensor.pv_estimated_auto_soc` ist eine Delta-Schaetzung:

$$SOC_{geschaetzt} = SOC_{Basis} + \frac{E_{aktuell} - E_{Basis}}{Kapazitaet_{Wh}} \cdot 100$$

Die Energie der Wallbox kann ein Lebenszeitzaehler sein. Deshalb muessen
`input_number.charge_session_start_soc` und
`input_number.charge_session_start_energy` immer gemeinsam als Basis gesetzt
werden. Die Roh-SOC-Entitaet aktualisiert sich nur etwa alle 30 Minuten und ist
fuer schnelle Ladeentscheidungen ungeeignet; die Handler verwenden daher die
Schaetzung.

Die Automation `automations/pv_charge_session_tracking.yaml` aktualisiert die
Basis bei Ladebeginn, Fahrzeugverbindung und manueller Korrektur. Das Dashboard
setzt ueber `input_number.pv_estimated_auto_soc_correction` und
`input_button.pv_apply_estimated_auto_soc_correction` auch niedrigere Werte.
Kommt waehrend eines laufenden Ladevorgangs ein Roh-SOC, wird die Schaetzung nur
nach oben korrigiert, falls der Rohwert hoeher ist; niedrigere Rohwerte ziehen
sie nicht wieder herunter.

## Status und Diagnose

Wichtige Dashboard-Entitaeten:

- `sensor.pv_charge_status`: `Adhoc Laden`, `Zwangsladung geplant`,
  `Zwangsladung`, `PV Ueberschuss` oder `Bereit`.
- `sensor.pv_force_charge_status`: Startzeit einer geplanten bzw. aktiven
  Zwangsladung.
- `sensor.pv_daily_debug` und `sensor.pv_adhoc_debug`: Zwischenwerte fuer
  Ziel-SOC, Schaetzung, Leistung, Phasenmodus und Stabilitaetsbedingungen.
- `sensor.pv_charge_target_power` und `sensor.pv_charge_available_power`:
  Soll- und verfuegbare Ladeleistung.

Bei einer Fehlersuche zuerst die Debug-Sensoren sowie folgende interne Helper
pruefen: `daily_force_charge_notification_sent`,
`daily_force_charge_start_at`, `phase_switch_to_1_pending` und
`phase_switch_to_1_requested_at`.

## Template- und Zeitregeln

- Zeit-Helper ohne Datum liefern einen reinen Zeitstring. Fuer die naechste
  Abfahrt daher `today_at(states('input_datetime...'))` verwenden, nicht
  `as_datetime(states(...))`.
- Variablen, die einen String an Service-Daten weitergeben, als einzelne
  Inline-Expression ausgeben, zum Beispiel
  `{{ 'Force_3' if bedingung else 'Force_1' }}`. Block-`if` kann unsichtbare
  Zeilenumbrueche erzeugen.
- `departure` aus einer Template-Variablen ist bei der weiteren Verwendung ein
  String. Fuer `strftime` daher `as_datetime(departure).strftime(...)` nutzen.

## Bereitstellung und Kontrolle

Dateien mit dem Sync-Skript kopieren:

```powershell
python syncPvCharge.py --mode samba --share "\\192.168.2.18\config"
```

Unter Git Bash mit der gemeinsamen virtuellen Umgebung:

```bash
cd /d/Josef/GitRepos
source .venv/Scripts/activate
python hajr/syncPvCharge.py --mode samba --share '\\192.168.2.18\config'
```

Das Kopieren laedt Home Assistant nicht neu. Nach Aenderungen jeweils die
betroffenen Bereiche neu laden: Automatisierungen, Skripte, Template-Entitaeten
und bei neuen oder geaenderten `input_*`-Helpern Home Assistant neu starten.

`check_ha_states.py` kann Zustandswerte ueber die REST-API mit `HA_TOKEN` oder
ohne Token aus der Recorder-Datenbank auf der Samba-Freigabe lesen. Bei einer
Recorder-Abfrage eine Kopie der SQLite-Datenbank verwenden, wenn ein
gleichzeitiger Zugriff Probleme verursacht.