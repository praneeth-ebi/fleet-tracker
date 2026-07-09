"""
One-time migration: converts an existing single-tenant database (from before
the multi-tenant change) into the new multi-tenant schema, WITHOUT losing
any existing data. Specifically preserves:
    - Existing device_token values (so already-deployed iPads/Web Clips
      keep working with no changes on the device side)
    - Existing user login credentials (same username/password still works)

What it does:
    1. Creates the new `organizations` table
    2. Adds an `organization_id` column to `users` and `devices`
    3. Creates one Organization from the values you provide (this becomes
       your first real client, e.g. your existing 25-iPad fleet)
    4. Assigns all existing users and devices to that Organization
    5. Enforces the new NOT NULL + per-org-unique constraints

Safe to run multiple times -- it detects if the migration already happened
and does nothing on subsequent runs.

Usage:
    DATABASE_URL=<your production database URL> python migrate_to_multitenant.py \\
        --org-name "IDK Express" --org-subdomain idkexpress
"""
import os
import sys
import argparse
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text, inspect


def get_engine():
    url = os.getenv("DATABASE_URL", "sqlite:///./local_dev.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url)


def already_migrated(engine) -> bool:
    inspector = inspect(engine)
    if "organizations" not in inspector.get_table_names():
        return False
    user_columns = [c["name"] for c in inspector.get_columns("users")]
    return "organization_id" in user_columns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-name", required=True, help='e.g. "IDK Express"')
    parser.add_argument("--org-subdomain", required=True, help='e.g. "idkexpress"')
    args = parser.parse_args()

    engine = get_engine()
    is_postgres = engine.dialect.name == "postgresql"
    print(f"Connected to {'PostgreSQL' if is_postgres else engine.dialect.name} database.")

    if already_migrated(engine):
        print("Already migrated (organizations table + organization_id column both exist). Nothing to do.")
        return

    org_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    with engine.begin() as conn:  # single transaction -- all-or-nothing
        print("Step 1/5: Creating organizations table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS organizations (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                subdomain VARCHAR UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP
            )
        """))

        print(f"Step 2/5: Creating organization '{args.org_name}' ({args.org_subdomain})...")
        conn.execute(
            text("INSERT INTO organizations (id, name, subdomain, is_active, created_at) "
                 "VALUES (:id, :name, :subdomain, TRUE, :created_at)"),
            {"id": org_id, "name": args.org_name, "subdomain": args.org_subdomain, "created_at": now},
        )

        print("Step 3/5: Adding organization_id column to users and devices...")
        conn.execute(text("ALTER TABLE users ADD COLUMN organization_id VARCHAR"))
        conn.execute(text("ALTER TABLE devices ADD COLUMN organization_id VARCHAR"))

        print("Step 4/5: Assigning all existing users and devices to the new organization...")
        result_users = conn.execute(
            text("UPDATE users SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": org_id},
        )
        result_devices = conn.execute(
            text("UPDATE devices SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": org_id},
        )
        print(f"  {result_users.rowcount} user(s) and {result_devices.rowcount} device(s) assigned.")

        if is_postgres:
            print("Step 5/5: Enforcing NOT NULL and per-organization uniqueness (PostgreSQL)...")
            conn.execute(text("ALTER TABLE users ALTER COLUMN organization_id SET NOT NULL"))
            conn.execute(text("ALTER TABLE devices ALTER COLUMN organization_id SET NOT NULL"))

            # Drop the old globally-unique username constraint if it exists, replace with per-org uniqueness
            conn.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_username_key') THEN
                        ALTER TABLE users DROP CONSTRAINT users_username_key;
                    END IF;
                END $$;
            """))
            conn.execute(text(
                "ALTER TABLE users ADD CONSTRAINT uq_username_per_org UNIQUE (organization_id, username)"
            ))

            # Devices never had a uniqueness constraint on name before, safe to add now
            # (only fails if you already had duplicate device names, which is worth knowing about)
            try:
                conn.execute(text(
                    "ALTER TABLE devices ADD CONSTRAINT uq_device_name_per_org UNIQUE (organization_id, name)"
                ))
            except Exception as e:
                print(f"  WARNING: could not add device name uniqueness constraint -- "
                      f"you likely have duplicate device names already. Not fatal, continuing. ({e})")
        else:
            print("Step 5/5: Skipped (SQLite doesn't support ALTER COLUMN -- fine for local testing).")

    print()
    print(f"Migration complete. Organization '{args.org_name}' created with all existing data preserved.")
    print(f"Organization ID: {org_id}")
    print("All existing device tokens and user credentials are unchanged -- nothing on your")
    print("deployed iPads needs to change.")
    print()
    print("IMPORTANT: your existing admin user's login now also requires org_subdomain "
          f"'{args.org_subdomain}' in the login request (the dashboard will handle this automatically "
          "once it's subdomain-aware).")


if __name__ == "__main__":
    main()
