# Campus Lost & Found

A responsive Flask app for sharing found items on campus. Visitors can browse, search, and filter listings without an account. Registered users can post items and mark their own listings as returned.

## Run locally

Requirements: Python 3.10+.

```bash
cd /path/to/Lost-and-found-hw5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
flask --app app run --debug
```

Open the local URL printed by Flask (usually http://127.0.0.1:5000). To run the app directly instead, use `python app.py`; it listens on `0.0.0.0` and uses `PORT` or defaults to 8080.

The database defaults to `lostfound.db` in the current directory. Set `DATABASE_PATH` (or `DB_PATH`) to use another SQLite file. On first startup, the app creates the schema and seeds 6 demo accounts and 25 sample found items if there are no items. Seeding is idempotent. Demo login: **alice** / **password123**.

## Deploy to Google Cloud Run

Install and authenticate the Google Cloud CLI, select a project with billing enabled, and then run this exact command from the project directory (replace `<random>` with a securely generated secret):

```bash
gcloud run deploy lostfound --source . --region us-west1 --allow-unauthenticated --set-env-vars SECRET_KEY=<random>
```

Cloud Run's local filesystem is ephemeral: the app seeds sample records at startup so a fresh instance has listings, but SQLite changes are not durable across instance replacement or redeploy. Use a persistent database for real deployments.

To delete the service:

```bash
gcloud run services delete lostfound --region us-west1
```
