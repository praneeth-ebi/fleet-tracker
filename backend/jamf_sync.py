"""
Syncs iPads enrolled in Jamf Pro into the Fleet Tracker backend as devices,
using each iPad's serial number as its device name.

Safe to re-run: skips any serial number that's already registered.

Requires (set as environment variables, or edit the CONFIG block below):
    JAMF_URL              e.g. https://yourcompany.jamfcloud.com
    JAMF_CLIENT_ID        from Jamf Pro > Settings > API Roles and Clients
    JAMF_CLIENT_SECRET    generated alongside the client ID (shown once)
    FLEET_API_URL         e.g. https://fleet-tracker-008a.onrender.com
    FLEET_ADMIN_USERNAME  your fleet tracker admin username
    FLEET_ADMIN_PASSWORD  your fleet tracker admin password

Usage:
    python jamf_sync.py                 # sync all enrolled mobile devices
    python jamf_sync.py --dry-run       # show what would be created, change nothing
"""
import os
import sys
import csv
import argparse
import requests

JAMF_URL = os.getenv("JAMF_URL", "").rstrip("/")
JAMF_CLIENT_ID = os.getenv("JAMF_CLIENT_ID", "")
JAMF_CLIENT_SECRET = os.getenv("JAMF_CLIENT_SECRET", "")

FLEET_API_URL = os.getenv("FLEET_API_URL", "").rstrip("/")
FLEET_ADMIN_USERNAME = os.getenv("FLEET_ADMIN_USERNAME", "")
FLEET_ADMIN_PASSWORD = os.getenv("FLEET_ADMIN_PASSWORD", "")


def require_config():
    missing = [name for name, val in [
        ("JAMF_URL", JAMF_URL), ("JAMF_CLIENT_ID", JAMF_CLIENT_ID),
        ("JAMF_CLIENT_SECRET", JAMF_CLIENT_SECRET), ("FLEET_API_URL", FLEET_API_URL),
        ("FLEET_ADMIN_USERNAME", FLEET_ADMIN_USERNAME), ("FLEET_ADMIN_PASSWORD", FLEET_ADMIN_PASSWORD),
    ] if not val]
    if missing:
        print("Missing required environment variables:", ", ".join(missing))
        sys.exit(1)


def get_jamf_token() -> str:
    resp = requests.post(
        f"{JAMF_URL}/api/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": JAMF_CLIENT_ID,
            "client_secret": JAMF_CLIENT_SECRET,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_jamf_mobile_devices(token: str) -> list[dict]:
    """Paginates through /api/v2/mobile-devices and returns [{serial, name, udid}, ...]."""
    devices = []
    page = 0
    page_size = 100
    while True:
        resp = requests.get(
            f"{JAMF_URL}/api/v2/mobile-devices",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"page": page, "page-size": page_size},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        results = body.get("results", [])
        if not results:
            break
        for d in results:
            devices.append({
                "serial": d.get("serialNumber"),
                "name": d.get("name") or d.get("deviceName") or d.get("serialNumber"),
                "udid": d.get("udid"),
            })
        if len(results) < page_size:
            break
        page += 1
    return devices


def get_fleet_token() -> str:
    resp = requests.post(
        f"{FLEET_API_URL}/auth/login",
        json={"username": FLEET_ADMIN_USERNAME, "password": FLEET_ADMIN_PASSWORD},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_existing_fleet_devices(token: str) -> set[str]:
    resp = requests.get(
        f"{FLEET_API_URL}/devices/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return {d["name"] for d in resp.json()}


def create_fleet_device(token: str, name: str) -> dict:
    resp = requests.post(
        f"{FLEET_API_URL}/devices/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without creating anything")
    parser.add_argument("--tracker-url", default=os.getenv("TRACKER_PAGE_URL", ""),
                         help="Base URL of the deployed iPad tracker page, e.g. https://fleet-tracker-ipad.onrender.com")
    parser.add_argument("--output", default="jamf_sync_results.csv", help="Where to write the serial->URL mapping")
    args = parser.parse_args()

    require_config()

    print(f"Authenticating to Jamf at {JAMF_URL} ...")
    jamf_token = get_jamf_token()

    print("Fetching enrolled mobile devices from Jamf ...")
    jamf_devices = get_jamf_mobile_devices(jamf_token)
    print(f"Found {len(jamf_devices)} device(s) in Jamf.")

    if not jamf_devices:
        print("Nothing to sync.")
        return

    print(f"Authenticating to fleet tracker at {FLEET_API_URL} ...")
    fleet_token = get_fleet_token()

    existing_names = get_existing_fleet_devices(fleet_token)
    print(f"{len(existing_names)} device(s) already registered in fleet tracker.")

    rows = []
    created = 0
    skipped = 0
    for d in jamf_devices:
        serial = d["serial"]
        if not serial:
            print(f"  Skipping a Jamf device with no serial number (name={d['name']})")
            continue

        if serial in existing_names:
            skipped += 1
            rows.append({"serial_number": serial, "jamf_name": d["name"], "status": "already_registered",
                         "device_token": "", "tracking_url": ""})
            continue

        if args.dry_run:
            print(f"  [dry-run] Would create device for serial {serial} ({d['name']})")
            rows.append({"serial_number": serial, "jamf_name": d["name"], "status": "would_create",
                         "device_token": "", "tracking_url": ""})
            continue

        result = create_fleet_device(fleet_token, serial)
        token = result["device_token"]
        url = f"{args.tracker_url}/?token={token}" if args.tracker_url else ""
        print(f"  Created device for serial {serial} -> token {token}")
        rows.append({"serial_number": serial, "jamf_name": d["name"], "status": "created",
                     "device_token": token, "tracking_url": url})
        created += 1

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["serial_number", "jamf_name", "status", "device_token", "tracking_url"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Created: {created}, already registered: {skipped}, total in Jamf: {len(jamf_devices)}")
    print(f"Full mapping written to {args.output}")


if __name__ == "__main__":
    main()
