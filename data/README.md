# Local data boundary

Place optional local input packages here only after a monthly package contract is agreed. Everything except this README is excluded from Git. Existing research datasets can remain in their original folders; no duplicate is required for the current database-backed app.

SQLite currently lives at `backend/instance/churn.sqlite`, or the `CHURN_DB_PATH` override. Database files, snapshots and backups must not be committed. Source control is not a database backup.
