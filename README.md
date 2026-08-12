# HA PV-Überschuss-Ladeautomation

Dieses Repo enthält ein Beispiel für die Umsetzung der Spezifikation "PV Überschuss laden" in Home Assistant.

## Ziel

- Lade das E-Auto mit möglichst viel PV-Strom
- Berücksichtige Tagesplan, Adhoc-Abfahrtszeit und Ziel-SOC
- Zeige Status und Steuerung in einer eigenen Lovelace-Ansicht
- Nutze YAML-Automationen mit Home Assistant Helpern

## Repo-Struktur

```
hajr/
  README.md
  configuration_example.yaml
  automations/
    pv_charging_schedule.yaml
  dashboards/
    pv_charging_dashboard.yaml
  helpers/
    entity_ids.example.yaml
    entity_ids.yaml
    input_boolean.yaml
    input_number.yaml
    input_datetime.yaml
    input_select.yaml
  scripts/
    pv_daily_charge_handler.yaml
    pv_adhoc_charge_handler.yaml
  sensors/
    pv_charge_estimates.yaml
  Spezifikation_PV_Ueberschussladen.txt
```

## Umsetzung

### Bedienung und GUI
- Anzeige: SOC Auto, Ladeleistung, Lade-Modus, Ladestrom, PV-Leistung, SOC Homespeicher
- Bedienung: tägliches Laden ein/aus, Adhoc Laden ein/aus, Adhoc Lade-Modus
- Tagesplan: Wochentage mit Startzeit und Ziel-SOC
- Adhoc: Abfahrtszeit, SOC-Ziel und Ladeoption
- Prognose: erwartetes SOC bei PV-Überschuss und bei maximaler Ladeleistung

### Logik
- Tägliche Ladeaufgabe startet am definierten Wochentag und Zeitpunkt
- Adhoc-Ladung prüft Abfahrtszeit und Ladeoption
- Wenn „Nur PV-Überschuss“ gewählt ist, wird nur bei genügend PV-Leistung geladen
- Bei „Maximale Ladeleistung“ wird die Wallbox mit dem aktuellen Limit betrieben

## Home Assistant Einbindung

In deiner `configuration.yaml`:

```yaml
automation: !include automations/pv_charging_schedule.yaml
input_number: !include helpers/input_number.yaml
input_datetime: !include helpers/input_datetime.yaml
input_boolean: !include helpers/input_boolean.yaml
input_select: !include helpers/input_select.yaml
script: !include_dir_merge_named scripts
template: !include sensors/pv_charge_estimates.yaml
```

Für Lovelace YAML:

```yaml
lovelace:
  mode: yaml
  resources: !include dashboards/resources.yaml
  views: !include dashboards/pv_charging_dashboard.yaml
```

## Was brauchst du an Sensoren

Achte darauf, deine tatsächlichen Entity-IDs einzusetzen, z. B.:

- `sensor.pv_power`
- `sensor.battery_soc`
- `sensor.auto_soc`
- `sensor.home_consumption`
- `sensor.solar_forecast_power`
- `switch.ev_charger`
- `sensor.wallbox_mode`
- `sensor.wallbox_current_limit`

## Zentrale Entity-ID-Datei

Ja, du kannst eine zentrale Datei anlegen, in der du alle Home-Assistant-Entity-IDs sammelst.

In diesem Repo findest du:

- `helpers/entity_ids.example.yaml` – Beispiel mit Platzhaltern
- `helpers/entity_ids.yaml` – Datei zum Befüllen mit deinen tatsächlichen IDs

Diese Datei ist eine Referenz, mit der du deine Entitäten an einer Stelle pflegen kannst.

### Empfohlene Nutzung

1. Trage in `helpers/entity_ids.yaml` deine echten Entity-IDs ein.
2. Nutze diese Datei als Vorlage, wenn du Automationen oder Dashboard-Konfigurationen erstellst.
3. Alternativ kannst du diese Werte in Home Assistant mit `secrets.yaml` noch besser zentral halten:

```yaml
pv_power_sensor: sensor.pv_power
```

Und in der Automation:

```yaml
entity_id: !secret pv_power_sensor
```

## Erweiterung

- Wenn die Logik noch komplexer wird, kannst du später AppDaemon, Python-Skripte oder ein Custom Component verwenden.
- Das aktuelle Setup deckt die Spec mit YAML, Helpern, Dashboard und Prognosesensoren ab.
