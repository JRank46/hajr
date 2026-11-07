# Energieabrechnung mit InfluxDB

## Zweck

Der Reiter `Abrechnung` im Dashboard `Energie_JR` ermittelt Energiedifferenzen
fuer einen frei waehbaren, einschliesslichen Zeitraum und berechnet daraus
Kosten und Einspeiseerloese. Als historische Datenquelle dient InfluxDB, weil
die Home-Assistant-Recorder-Statistiken nicht den gesamten benoetigten
Zeitraum enthalten.

## Konfiguration

`configuration.yaml` bindet die REST-Sensoren ein:

```yaml
rest: !include sensors/energy_billing_influx.yaml
```

Die folgenden Secrets muessen in `secrets.yaml` vorhanden sein. Zugangsdaten
werden nicht im Repository gespeichert.

```yaml
influxdb_username: ...
influxdb_password: ...
```

Die REST-Sensoren fragen die InfluxDB `HomeAssistant` unter
`http://192.168.2.125:8086/query` ab und verwenden Basic Authentication.

## Datenmodell in InfluxDB

Home Assistant speichert die Werte nicht einheitlich in einer Messung `state`.
Die Energie-Messungen heissen nach ihrer Einheit und enthalten das Feld
`value`:

- `kWh` fuer Batterie, Waermepumpe, Haus 1A und Haus 1B
- `Wh` fuer Wallbox, Netzbezug und Einspeisung

Das Tag `entity_id` enthaelt nur die Objekt-ID, also beispielsweise
`entladene_energie`, nicht `sensor.entladene_energie`.

## Abrechnungsquellen

| Auswertung | Influx-Messung | `entity_id`-Tag | Umrechnung |
| --- | --- | --- | --- |
| Batteriespeicher entladen | `kWh` | `entladene_energie` | keine |
| Wallbox geladen | `Wh` | `go_echarger_325099_total_energy_charged` | durch 1000 teilen |
| Waermepumpe | `kWh` | `warmepumpe_shelly3em63g3_48f6eeaa67bc_energie` | keine |
| Haus 1A | `kWh` | `shelly3em63g3_e4b063f69434_energie` | keine |
| Haus 1B | `kWh` | `shelly_3em_2_energie` | keine |
| Netzbezug | `Wh` | `smart_meter_ts_65a_3_bezogene_wirkenergie` | durch 1000 teilen |
| Einspeisung | `Wh` | `smart_meter_ts_65a_3_eingespeiste_wirkenergie` | durch 1000 teilen |

Fuer jede Quelle wird der letzte Zaehlerstand vor dem Zeitraumende minus dem
letzten Zaehlerstand vor dem Zeitraumstart verwendet. Das Ende wird um einen
Tag erhoeht, damit der ausgewaehlte Endtag vollstaendig enthalten ist.

Die Haus-1B-Auswertung ist bereinigt, da die Wallbox hinter diesem Zaehler
liegt:

$$Haus\ 1B_{bereinigt} = Haus\ 1B_{Zaehler} - Wallbox$$

## 24h-Statistik im Energiefluss-Reiter

Die Tageswerte werden nicht ueber einen REST-Sensor, sondern ueber den
`rest_command` `energy_daily_influx_query` (`sensors/energy_daily_rest_command.yaml`)
und einen trigger-basierten Template-Block in `sensors/pv_charge_estimates.yaml`
geliefert. Grund: REST-Sensoren teilen sich einen Coordinator mit 10 s
Debounce; `homeassistant.update_entity` auf mehrere Entitaeten fuehrte dadurch
zu verzoegerten oder ausbleibenden Aktualisierungen beim Tageswechsel.

Der Template-Block loest bei Aenderung von
`input_number.energy_dashboard_day_offset`, alle 5 Minuten und beim
Home-Assistant-Start aus. Tagesgrenzen werden mit `today_at('00:00')` plus
Offset gebildet; pro Quelle wird der letzte Zaehlerstand vor Tagesende minus
dem letzten Zaehlerstand vor Tagesbeginn gerechnet. Schlaegt die Abfrage fehl,
werden die Sensoren `unavailable`, statt Werte eines anderen Tages anzuzeigen.

| Sensor | Influx-Messung | `entity_id`-Tag | Umrechnung |
| --- | --- | --- | --- |
| `sensor.energy_day_house_1a` | `kWh` | `shelly3em63g3_e4b063f69434_energie` | keine |
| `sensor.energy_day_house_1b` | `kWh` | `shelly_3em_2_energie` | Wallbox abziehen |
| `sensor.energy_day_heat_pump` | `kWh` | `warmepumpe_shelly3em63g3_48f6eeaa67bc_energie` | keine |
| `sensor.energy_day_wallbox` | `Wh` | `go_echarger_325099_total_energy_charged` | durch 1000 teilen |
| `sensor.energy_day_battery_charged` | `kWh` | `geladene_energie` | keine |
| `sensor.energy_day_battery_discharged` | `kWh` | `entladene_energie` | keine |
| `sensor.energy_day_pv` | `kWh` | `pv_energie` | keine |
| `sensor.energy_day_grid_export` | `Wh` | `smart_meter_ts_65a_3_eingespeiste_wirkenergie` | durch 1000 teilen |
| `sensor.energy_day_grid_import` | `Wh` | `smart_meter_ts_65a_3_bezogene_wirkenergie` | durch 1000 teilen |
| `sensor.energy_day_total_consumption` | `kWh` | `haus_energie` | keine |

Der Autarkiegrad `sensor.energy_day_self_sufficiency` wird im selben Block aus
Tages-Gesamtverbrauch und Tages-Netzbezug berechnet:

$$Autarkiegrad = \frac{Gesamtverbrauch - Netzbezug}{Gesamtverbrauch} \cdot 100\ \%$$

`configuration.yaml` benoetigt dafuer zusaetzlich (Neustart erforderlich):

```yaml
rest_command: !include sensors/energy_daily_rest_command.yaml
```

## Zustaendige Dateien

- `sensors/energy_billing_influx.yaml`: InfluxDB-REST-Abfragen und
  Energiedifferenzen fuer den Abrechnungszeitraum
- `sensors/energy_daily_rest_command.yaml`: InfluxDB-Tagesabfrage der
  24h-Statistik
- `sensors/pv_charge_estimates.yaml`: Template-Sensoren fuer Kosten, Erloese,
  Netzsaldo sowie die 24h-Statistik mit Autarkiegrad
- `automations/energy_billing.yaml`: Aktualisiert die REST-Sensoren bei
  Zeitraumwechsel oder nach dem Berechnungsbutton
- `helpers/input_datetime.yaml`: Start- und Enddatum
- `helpers/input_number.yaml`: Tarife fuer Waermestrom, Hausstrom und
  Einspeisung sowie `energy_dashboard_day_offset`
- `helpers/input_button.yaml`: Button `energy_billing_calculate`
- `dashboards/energy_dashboard.yaml`: Abrechnungsreiter und Energiefluss-Reiter

## Wichtige Template-Regeln

Influx liefert die Messwerte als JSON-Schluessel `values`. In Home-Assistant-
Jinja darf dieser Schluessel nicht per Punktnotation gelesen werden, weil
`.values` mit der Python-Methode `dict.values()` kollidiert.

```jinja
{# korrekt #}
{{ value_json.results[0].series[0]['values'][0][1] }}

{# nicht verwenden #}
{{ value_json.results[0].series[0].values[0][1] }}
```

Stringwerte aus Jinja-Bedingungen immer in einer Inline-Expression ausgeben,
damit keine unsichtbaren Zeilenumbrueche in Home-Assistant-Servicewerten
entstehen:

```jinja
{{ 'Force_3' if bedingung else 'Force_1' }}
```

## Bereitstellung und Pruefung

Dateien auf Home Assistant uebertragen:

```powershell
python syncPvCharge.py --mode samba --share "\\192.168.2.125\config"
```

Anschliessend Home Assistant neu starten oder die passende YAML-/REST-
Konfiguration neu laden. Im Dashboard zuerst `Berechnung durchfuehren` waehlen.
Bei Problemen zeigt `sensor.influx_billing_connection_test`, ob die REST-
Anfrage einen aktuellen Batterie-Zaehlerstand aus InfluxDB lesen kann.