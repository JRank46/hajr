# Netwatch (DHCP-Überwachung) in Home Assistant

Der Raspi (`Raspi46`) schneidet DHCP-Verkehr mit und sichert den PCAP-Ringpuffer bei
Auffälligkeiten (Rogue-DHCP-Server). Der Code liegt im Repo `Raspy46`
(`netwatch/netwatch.py`, `setup_netwatch.py`, `deploy_netwatch.py`). Dieses Repo enthält nur die
Home-Assistant-Seite.

## Anbindung

- Der Raspi meldet per MQTT an den Mosquitto-Broker auf Home Assistant (jede Minute und sofort
  bei einem neuen Vorfall).
- Die Entitäten legt HA per MQTT-Auto-Discovery selbst an (Gerät `Netwatch`), es ist keine YAML-
  Definition nötig:
  - `binary_sensor.netwatch_incident` – an, wenn der letzte Vorfall jünger als 24 h ist;
    Attribute `reason`, `detail`, `incident_folder`, `incident_time`, `host`, `path`
  - `sensor.netwatch_incident_count` – Anzahl gesicherter Vorfälle
  - `sensor.netwatch_last_incident` – Zeitpunkt des letzten Vorfalls
- Fällt der Raspi oder Dienst aus, setzt Mosquitto per Last Will alle Entitäten auf
  `unavailable`.
- Nach der ersten Verbindung die tatsächlichen Entity-IDs unter Einstellungen → Geräte & Dienste
  → MQTT → Netwatch prüfen. Weichen sie ab, in Dashboard und Automation anpassen.

## Dateien in diesem Repo

- `dashboards/netwatch_dashboard.yaml` – Dashboard-Ansicht (in `configuration.yaml` unter
  `lovelace: dashboards:` registrieren, siehe `configuration_example.yaml`)
- `automations/netwatch_notifications.yaml` – Push bei Vorfall und bei Ausfall des Dienstes

## Einrichtung auf dem Raspi

In Home Assistant einen MQTT-Benutzer anlegen (Mosquitto-Add-on nutzt HA-Benutzer, am besten
ein eigener Benutzer `netwatch`). Dann vom Windows-PC aus:

```powershell
python deploy_netwatch.py <raspi-ip> --run --mqtt-host <ha-ip> --mqtt-user netwatch
```

Das Passwort wird auf dem Raspi einmalig abgefragt und in `/etc/netwatch/mqtt_password`
(Modus 600) gespeichert, nicht in der Kommandozeile oder im systemd-Unit.

## Dateien abholen

```powershell
scp -r jr46@<raspi-ip>:/var/log/dhcp/incidents/<ordner> C:\Logs\
```

Auswertung in Wireshark mit Filter `bootp`.
