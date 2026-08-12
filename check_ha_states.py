#!/usr/bin/env python3
"""Read the current PV charging states from Home Assistant's recorder database."""

import argparse
import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone


DEFAULT_DATABASE = r"\\192.168.2.125\config\home-assistant_v2.db"
ENTITY_IDS = (
    "input_boolean.adhoc_charging_enabled",
    "input_boolean.daily_charging_enabled",
    "input_boolean.wallbox_restart_latched",
    "input_select.adhoc_charge_mode",
    "input_number.adhoc_target_soc",
    "input_number.adhoc_charge_current_limit",
    "sensor.aceman_e_battery_hv_state_of_charge",
    "sensor.aceman_e_battery_ev_target_state_of_charge",
    "sensor.pv_estimated_auto_soc",
    "sensor.solarnet_pv_leistung",
    "sensor.solcast_pv_forecast_leistung_in_1_stunde",
    "sensor.solarnet_leistung_verbrauch",
    "sensor.go_echarger_325099_power_total",
    "sensor.go_echarger_325099_car_state",
    "binary_sensor.go_echarger_325099_allowed_to_charge",
    "sensor.pv_charge_target_power",
    "sensor.pv_adhoc_debug",
    "sensor.pv_daily_debug",
    "sun.sun",
    "select.go_echarger_325099_force_state",
    "select.go_echarger_325099_phase_switch_mode",
    "number.go_echarger_325099_set_max_ampere_limit",
    "script.pv_adhoc_lade_handler",
    "automation.pv_ladeplanung_und_adhoc_laden",
)


def format_timestamp(timestamp):
    if timestamp is None:
        return "unknown"
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat(
        timespec="seconds"
    )


def current_states(connection):
    columns = {row[1] for row in connection.execute("PRAGMA table_info(states)")}
    timestamp_column = "last_reported_ts" if "last_reported_ts" in columns else "last_updated_ts"
    placeholders = ", ".join("?" for _ in ENTITY_IDS)

    if "metadata_id" in columns:
        query = f"""
            WITH latest AS (
                SELECT s.metadata_id, MAX(s.state_id) AS state_id
                FROM states AS s
                JOIN states_meta AS sm ON sm.metadata_id = s.metadata_id
                WHERE sm.entity_id IN ({placeholders})
                GROUP BY s.metadata_id
            )
            SELECT sm.entity_id, s.state, s.{timestamp_column}
            FROM latest
            JOIN states AS s ON s.state_id = latest.state_id
            JOIN states_meta AS sm ON sm.metadata_id = s.metadata_id
            ORDER BY sm.entity_id
        """
    else:
        query = f"""
            WITH latest AS (
                SELECT entity_id, MAX(state_id) AS state_id
                FROM states
                WHERE entity_id IN ({placeholders})
                GROUP BY entity_id
            )
            SELECT s.entity_id, s.state, s.{timestamp_column}
            FROM latest
            JOIN states AS s ON s.state_id = latest.state_id
            ORDER BY s.entity_id
        """

    return {entity_id: (state, timestamp) for entity_id, state, timestamp in connection.execute(query, ENTITY_IDS)}


def rest_states(base_url, token):
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        server_time = response.headers.get("Date", "unknown")
        payload = json.load(response)

    state_map = {item["entity_id"]: item for item in payload}
    states = {}
    for entity_id in ENTITY_IDS:
        item = state_map.get(entity_id)
        if item is None:
            continue
        timestamp = datetime.fromisoformat(item["last_updated"].replace("Z", "+00:00")).timestamp()
        states[entity_id] = (item["state"], timestamp)
    return states, server_time


def call_service(base_url, token, domain, service, data=None):
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/services/{domain}/{service}",
        data=json.dumps(data or {}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


def check_config(base_url, token):
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/config/core/check_config",
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.load(response)


def error_log(base_url, token):
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/error_log",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, ""


def script_trace(base_url, token):
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/trace/script/pv_adhoc_lade_handler",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, {"error": error.read().decode("utf-8", errors="replace")}


def registered_scripts(base_url, token):
    headers = {"Authorization": f"Bearer {token}"}
    states_request = urllib.request.Request(f"{base_url.rstrip('/')}/api/states", headers=headers)
    services_request = urllib.request.Request(f"{base_url.rstrip('/')}/api/services", headers=headers)
    with urllib.request.urlopen(states_request, timeout=10) as response:
        states = json.load(response)
    with urllib.request.urlopen(services_request, timeout=10) as response:
        services = json.load(response)

    script_states = {
        item["entity_id"]: item["state"]
        for item in states
        if item["entity_id"].startswith("script.")
    }
    entity_ids = sorted(script_states)
    script_services = sorted(
        service_name for domain in services if domain["domain"] == "script" for service_name in domain["services"]
    )
    return script_states, script_services


def print_states(states, source):
    print(f"Source: {source}")
    print(f"Diagnostic time: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print()
    for entity_id in ENTITY_IDS:
        state, timestamp = states.get(entity_id, ("not recorded", None))
        print(f"{entity_id}: {state} (updated: {format_timestamp(timestamp)})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Path to home-assistant_v2.db")
    parser.add_argument("--url", default="http://192.168.2.125:8123", help="Home Assistant base URL")
    parser.add_argument(
        "--reload-scripts",
        action="store_true",
        help="Call Home Assistant's script.reload service before reading states",
    )
    parser.add_argument(
        "--reload-templates",
        action="store_true",
        help="Call Home Assistant's template.reload service before reading states",
    )
    parser.add_argument(
        "--reload-automations",
        action="store_true",
        help="Call Home Assistant's automation.reload service before reading states",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Ask Home Assistant to validate the active YAML configuration before reading states",
    )
    parser.add_argument(
        "--script-errors",
        action="store_true",
        help="Print Home Assistant error-log lines related to script loading",
    )
    parser.add_argument(
        "--list-scripts",
        action="store_true",
        help="List all script entities and script services currently registered in Home Assistant",
    )
    parser.add_argument(
        "--run-adhoc-handler",
        action="store_true",
        help="Run the loaded Adhoc handler once before reading states",
    )
    parser.add_argument(
        "--adhoc-trace",
        action="store_true",
        help="Print the latest Home Assistant trace for the Adhoc handler",
    )
    args = parser.parse_args()

    token = os.environ.get("HA_TOKEN")
    if token:
        if args.check_config:
            status, result = check_config(args.url, token)
            print(f"config check: HTTP {status}")
            print(json.dumps(result, indent=2, ensure_ascii=True))
        if args.script_errors:
            status, log = error_log(args.url, token)
            terms = ("script", "pv_adhoc", "pv_daily", "automation")
            lines = [line for line in log.splitlines() if any(term in line.lower() for term in terms)]
            print(f"error log: HTTP {status}; matching lines: {len(lines)}")
            print("\n".join(lines[-100:]))
        if args.list_scripts:
            script_states, script_services = registered_scripts(args.url, token)
            print("registered script entities:")
            print(
                "\n".join(
                    f"{entity_id}: {state}"
                    for entity_id, state in sorted(script_states.items())
                )
                or "none"
            )
            print("registered script services:")
            print("\n".join(script_services) or "none")
        if args.reload_scripts:
            status = call_service(args.url, token, "script", "reload")
            print(f"script.reload: HTTP {status}")
        if args.reload_templates:
            status = call_service(args.url, token, "template", "reload")
            print(f"template.reload: HTTP {status}")
        if args.reload_automations:
            status = call_service(args.url, token, "automation", "reload")
            print(f"automation.reload: HTTP {status}")
        if args.run_adhoc_handler:
            status = call_service(
                args.url,
                token,
                "script",
                "turn_on",
                {"entity_id": "script.pv_adhoc_lade_handler"},
            )
            print(f"Adhoc handler started: HTTP {status}")
        if args.adhoc_trace:
            status, trace = script_trace(args.url, token)
            print(f"Adhoc trace: HTTP {status}")
            print(json.dumps(trace, indent=2, ensure_ascii=True))
        states, server_time = rest_states(args.url, token)
        print(f"Home Assistant server time: {server_time}")
        print_states(states, "Home Assistant REST API")
        return

    connection = sqlite3.connect(args.database)
    try:
        states = current_states(connection)
    finally:
        connection.close()

    print_states(states, f"Recorder database: {args.database}")


if __name__ == "__main__":
    main()