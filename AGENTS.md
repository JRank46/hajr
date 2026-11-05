# Arbeitsanweisungen

## Energieabrechnung

- Historische Abrechnungswerte aus InfluxDB beziehen, nicht aus Recorder-SQL.
- Die Details stehen in `docs/energieabrechnung-influxdb.md`.
- Messungen und Entity-ID-Tags nicht ohne eine direkte InfluxDB-Pruefung
  aendern: Die Messungen sind einheitenbasiert (`kWh` oder `Wh`) und die Tags
  enthalten kein `sensor.`-Praefix.
- `Wh`-Quellen vor der Ausgabe als kWh durch 1000 teilen.
- `sensor.influx_billing_house_1b_energy` muss die Wallbox-Energie abziehen.
- JSON-Feld `values` ausschliesslich per `['values']` lesen, nie per `.values`.
- Zugangsdaten nur ueber `!secret influxdb_username` und
  `!secret influxdb_password` verwenden; keine Werte in Dateien, Logs oder
  Antworten ausgeben.

## Bereitstellung

- Nach einer Aenderung erst die beruehrte YAML-Datei pruefen.
- Die Uebertragung erfolgt ueber `syncPvCharge.py` im Samba-Modus.
- Das Kopieren der Dateien laedt Home-Assistant-Konfigurationen nicht
  automatisch neu. Danach den passenden Reload ausfuehren oder Home Assistant
  neu starten.

## Bestehende PV-Ladelogik

- Vor einer Aenderung an der PV-Ladelogik zuerst
  `docs/pv-ladeautomation.md` sowie die direkt betroffenen Handler,
  Automationen, Sensoren und Helper lesen. Die technische Doku beschreibt den
  verifizierten Betriebsstand; bei Widerspruch entscheidet das aktuelle YAML
  zusammen mit dem Live-Zustand von Home Assistant.
- Fuer Wallbox-Freigabe bedeutet `Neutral` aktivieren und `Off` sperren.
  `On` startet das Laden auf dieser Anlage nicht zuverlaessig und darf nicht
  als Ersatz verwendet werden.
- Die 5-Minuten-Stabilitaetspruefung darf nur Aenderungen von Phasenmodus und
  Stromlimit bremsen. Die Ladefreigabe (`Neutral` oder `Off`) muss unmittelbar
  gesetzt werden.
- Eine Anforderung von `Force_3` nach `Force_1` erst nach 30 Minuten
  ununterbrochener Anforderung umsetzen. Vormerkung und Zeitstempel in
  `phase_switch_to_1_pending` und `phase_switch_to_1_requested_at` nicht
  umgehen.
- Fuer Ladeentscheidungen den schnellen Delta-SOC
  `sensor.pv_estimated_auto_soc` verwenden. Der Roh-SOC aktualisiert sich
  langsam und ist nur fuer die gemeinsame Aktualisierung der SOC-/Energie-
  Basis geeignet. Die Wallbox-Energie kann ein Lebenszeitzaehler sein, daher
  nie ohne Sitzungsbasis direkt in einen SOC umrechnen.
- Zeit-Helper ohne Datum sind mit `today_at(...)` zu einem Datum zu verbinden.
  Home-Assistant-Jinja-Strings fuer Servicewerte als Inline-Expression
  ausgeben, um unsichtbare Zeilenumbrueche zu vermeiden.
- Die minuetliche Zwangslade-Ankuendigung muss pro Abfahrtszyklus genau einmal
  erfolgen. Das Flag `daily_force_charge_notification_sent` zuerst setzen;
  Meldungen nicht in den sekundenweise laufenden Lade-Handler verschieben.
- `0 A` beim Tagesladen setzt voraus, dass die go-eCharger-Integration diesen
  Wert annimmt. Bei einer Integrationsaenderung dieses Verhalten zuerst gegen
  die reale Wallbox pruefen; die normale Ladegrenze liegt bei 6 bis 16 A.
- Nach einer Verhaltensaenderung nicht allein YAML-Syntax pruefen: betroffene
  Entitaeten, Debug-Sensoren und den geladenen Stand in Home Assistant
  kontrollieren. Bei Recorder-Diagnosen die SQLite-Datenbank zuerst lokal
  kopieren und dann pruefen, ob eine Entity nie geladen wurde oder nur einen
  falschen Zustand hat.
- Bei zeitbasierten `input_datetime`-Helpern ohne Datum `today_at(...)`
  verwenden, nicht `as_datetime(...)`.
- Weitere bestaetigte Details zur PV-Ladelogik stehen im Repository-Gedaechtnis
  und in der bestehenden Konfiguration. Speicher-Eintraege mit Datum sind
  historische Debugging-Erkenntnisse und duerfen aktuelles YAML nicht
  ueberstimmen.