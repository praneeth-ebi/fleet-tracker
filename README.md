# Fleet Tracker — Backend (Step 1)

FastAPI + PostgreSQL backend with JWT auth and role-based access
(admin / operator / client), device management, and location check-ins.

## What's included in this step
- `app/models.py` — Users, Devices, LocationPings, DeviceAssignments (for client role), AuditLog
- `app/auth.py` — password hashing (bcrypt), JWT tokens, `require_role()` guard
- `app/routers/auth.py` — `POST /auth/login`
- `app/routers/users.py` — admin-only user CRUD
- `app/routers/devices.py` — create devices, list (role-filtered), location history
- `app/routers/locations.py` — `POST /checkin/` — this is what the iPad page will call (Step 2)
- `create_admin.py` — run once to create your first login

## Deploy to Render (free tier)

1. **Push this folder to a GitHub repo.**
   ```
   cd fleet-tracker
   git init
   git add .
   git commit -m "Fleet tracker backend"
   git branch -M main
   git remote add origin <your-empty-github-repo-url>
   git push -u origin main
   ```

2. **Create a free PostgreSQL instance on Render:**
   - render.com → New → PostgreSQL → free plan
   - Copy the "Internal Database URL" once it's ready

3. **Create a free Web Service on Render:**
   - New → Web Service → connect your GitHub repo
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Instance type: Free

4. **Set environment variables on the web service:**
   - `DATABASE_URL` → paste the Internal Database URL from step 2
   - `JWT_SECRET` → any long random string (e.g. generate with `openssl rand -hex 32`)

5. **Deploy.** Once it's live, open the Render "Shell" tab for the web service and run:
   ```
   python create_admin.py
   ```
   Follow the prompts to set your admin username/password.

6. **Test it:** your API docs are auto-generated at
   `https://<your-service>.onrender.com/docs` — you can log in and try
   every endpoint right from the browser.

### Note on Render's free tier
The free web service "spins down" after 15 minutes of no traffic and takes
~30-60 seconds to wake up on the next request. Fine for an ops dashboard
checked periodically; if that becomes annoying later, a $7/mo instance
removes the spin-down — no code changes needed.

## Next steps
- Step 2: iPad reporting page (posts to `/checkin/`)
- Step 3: React dashboard (map + device list + login)
- Step 4: Wire it all together on Render
