"""
Creates one Web Clip configuration profile per iPad in Jamf Pro, each scoped
to a single device and pointing at that device's unique fleet-tracker URL.

This replaces the manual "open Safari, Add to Home Screen" step from Step 2 --
Jamf pushes the Home Screen icon automatically via MDM. You still need to
enable Guided Access / Single App Mode separately for a fully hands-off
driver experience (Single App Mode automation is a separate, riskier script
-- see the note at the bottom of this file).

Reads jamf_sync_results.csv (produced by jamf_sync.py) and, for every row
with a tracking_url, creates a matching Web Clip profile in Jamf.

Requires the same JAMF_URL / JAMF_CLIENT_ID / JAMF_CLIENT_SECRET as
jamf_sync.py, PLUS the API Role needs two more privileges added:
    - "Read Mobile Devices"                  (already had this)
    - "Create Mobile Device Configuration Profiles"
    - "Read Mobile Device Configuration Profiles"

Usage:
    python create_webclips.py --dry-run
    python create_webclips.py
"""
import os
import sys
import csv
import argparse
import plistlib
import uuid
import xml.sax.saxutils as saxutils
import requests

JAMF_URL = os.getenv("JAMF_URL", "").rstrip("/")
JAMF_CLIENT_ID = os.getenv("JAMF_CLIENT_ID", "")
JAMF_CLIENT_SECRET = os.getenv("JAMF_CLIENT_SECRET", "")


def require_config():
    missing = [n for n, v in [("JAMF_URL", JAMF_URL), ("JAMF_CLIENT_ID", JAMF_CLIENT_ID),
                               ("JAMF_CLIENT_SECRET", JAMF_CLIENT_SECRET)] if not v]
    if missing:
        print("Missing required environment variables:", ", ".join(missing))
        sys.exit(1)


def get_jamf_token() -> str:
    resp = requests.post(
        f"{JAMF_URL}/api/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "client_id": JAMF_CLIENT_ID, "client_secret": JAMF_CLIENT_SECRET},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_jamf_device_id_by_serial(token: str, serial: str) -> str:
    """Looks up a mobile device's Jamf-internal ID (needed for scoping) from its serial number."""
    resp = requests.get(
        f"{JAMF_URL}/JSSResource/mobiledevices/serialnumber/{serial}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return str(resp.json()["mobile_device"]["general"]["id"])


def build_webclip_plist(label: str, url: str) -> str:
    """
    Builds a valid Apple configuration profile (.mobileconfig) XML string
    containing a single managed Web Clip payload, using Python's plistlib
    so the XML structure is guaranteed well-formed.
    """
    payload_uuid = str(uuid.uuid4())
    profile_uuid = str(uuid.uuid4())

    webclip_payload = {
        "PayloadType": "com.apple.webClip.managed",
        "PayloadUUID": payload_uuid,
        "PayloadIdentifier": f"com.fleettracker.webclip.{payload_uuid}",
        "PayloadVersion": 1,
        "PayloadDisplayName": label,
        "Label": label,
        "URL": url,
        "IsRemovable": False,
        "FullScreen": True,
        "Precomposed": True,
    }

    profile = {
        "PayloadContent": [webclip_payload],
        "PayloadDisplayName": label,
        "PayloadIdentifier": f"com.fleettracker.profile.{profile_uuid}",
        "PayloadUUID": profile_uuid,
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadScope": "System",
    }

    return plistlib.dumps(profile, fmt=plistlib.FMT_XML).decode("utf-8")


def create_webclip_profile(token: str, device_id: str, label: str, url: str) -> dict:
    plist_xml = build_webclip_plist(label, url)
    # Classic API requires the plist content wrapped in CDATA inside the request XML
    request_xml = f"""<mobile_device_configuration_profile>
  <general>
    <name>{saxutils.escape(label)}</name>
    <description>Fleet tracker Web Clip, auto-generated per device</description>
    <payloads><![CDATA[{plist_xml}]]></payloads>
  </general>
  <scope>
    <mobile_devices>
      <mobile_device>
        <id>{device_id}</id>
      </mobile_device>
    </mobile_devices>
  </scope>
</mobile_device_configuration_profile>"""

    resp = requests.post(
        f"{JAMF_URL}/JSSResource/mobiledeviceconfigurationprofiles/id/0",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/xml"},
        data=request_xml.encode("utf-8"),
        timeout=30,
    )
    resp.raise_for_status()
    return {"status_code": resp.status_code, "request_xml": request_xml}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="jamf_sync_results.csv")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-serial", default="", help="If set, only process this one serial number (for testing before a full rollout)")
    args = parser.parse_args()

    require_config()

    with open(args.input, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("tracking_url")]

    if args.only_serial:
        rows = [r for r in rows if r["serial_number"] == args.only_serial]
        if not rows:
            print(f"No row found with serial_number == {args.only_serial}")
            return

    if not rows:
        print(f"No rows with a tracking_url found in {args.input}. Nothing to do.")
        return

    print(f"Found {len(rows)} device(s) with tracking URLs to push Web Clips for.")

    token = get_jamf_token()
    created = 0
    for row in rows:
        serial = row["serial_number"]
        url = row["tracking_url"]
        label = f"Fleet Tracker ({serial})"

        try:
            device_id = get_jamf_device_id_by_serial(token, serial)
        except requests.HTTPError as e:
            print(f"  SKIP {serial}: couldn't look up Jamf device ID ({e})")
            continue

        if args.dry_run:
            print(f"  [dry-run] Would create Web Clip for {serial} (Jamf ID {device_id}) -> {url}")
            continue

        try:
            create_webclip_profile(token, device_id, label, url)
            print(f"  Created Web Clip profile for {serial} (Jamf ID {device_id})")
            created += 1
        except requests.HTTPError as e:
            print(f"  FAILED {serial}: {e} -- response: {e.response.text[:300] if e.response is not None else 'no response'}")

    print(f"\nDone. Created {created} Web Clip profile(s).")
    print("Each iPad will pick up its profile on its next Jamf check-in (usually within minutes).")


if __name__ == "__main__":
    main()

# --- Note on Single App Mode ---
# Locking each iPad into this Web Clip (so drivers can't leave it) requires a
# separate step: enabling Single App Mode via MDM, targeting the Web Clip's
# generated bundle identifier. That ID doesn't exist until *after* the Web
# Clip has actually installed on the device, so it's a two-phase process
# (push Web Clips -> wait for install -> look up each bundle ID -> send
# Single App Mode command) and needs testing against your real Jamf instance
# before relying on it. Guided Access (manual, from Step 2) remains the
# proven fallback in the meantime.
