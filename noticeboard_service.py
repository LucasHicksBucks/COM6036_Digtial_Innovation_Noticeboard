"""Business logic layer for notice validation, moderation and filtering."""
from datetime import date, datetime, timedelta
import sqlite3


CATEGORIES = ("Events", "Volunteering", "Lost & Found", "Services", "Announcements")
STATUSES = ("pending", "approved", "rejected")


class ValidationError(ValueError):
    pass


class NoticeboardService:
    def __init__(self, database_path):
        self.database_path = database_path
        self._create_schema()
        self._seed_data()

    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_schema(self):
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS notices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    location TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    expires_on TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    deleted_at TEXT
                )
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(notices)")}
            if "deleted_at" not in columns:
                connection.execute("ALTER TABLE notices ADD COLUMN deleted_at TEXT")

    def _seed_data(self):
        with self._connection() as connection:
            if connection.execute("SELECT COUNT(*) FROM notices").fetchone()[0]:
                return
            today = date.today()
            connection.executemany("""
                INSERT INTO notices
                (title, description, category, location, contact, expires_on, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'approved', ?)
            """, [
                ("Saturday repair cafe", "Bring small household items for friendly repairs and advice.", "Events", "Community Hall", "hello@example.org", str(today + timedelta(days=12)), datetime.now().isoformat(timespec="seconds")),
                ("Found: blue bicycle lock", "Found near the library entrance. Describe the keyring to claim it.", "Lost & Found", "Library reception", "hello@example.org", str(today + timedelta(days=5)), datetime.now().isoformat(timespec="seconds")),
            ])

    def categories(self):
        return list(CATEGORIES)

    def _validate(self, data):
        required = ("title", "description", "category", "location", "contact", "expires_on")
        missing = [field for field in required if not str(data.get(field, "")).strip()]
        if missing:
            raise ValidationError("Please complete: " + ", ".join(missing))
        if data["category"] not in CATEGORIES:
            raise ValidationError("Choose a valid category")
        try:
            expiry = date.fromisoformat(data["expires_on"])
        except ValueError as error:
            raise ValidationError("Expiry must be a valid date") from error
        if expiry < date.today():
            raise ValidationError("Expiry date must be today or later")
        if len(data["title"].strip()) > 80:
            raise ValidationError("Title must be 80 characters or fewer")
        if len(data["description"].strip()) > 500:
            raise ValidationError("Description must be 500 characters or fewer")

    def submit_notice(self, data):
        self._validate(data)
        with self._connection() as connection:
            cursor = connection.execute("""
                INSERT INTO notices
                (title, description, category, location, contact, expires_on, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (data["title"].strip(), data["description"].strip(), data["category"], data["location"].strip(), data["contact"].strip(), data["expires_on"], datetime.now().isoformat(timespec="seconds")))
            return self._get_notice(connection, cursor.lastrowid)

    def moderate_notice(self, notice_id, status):
        if status not in STATUSES or status == "pending":
            raise ValidationError("Invalid moderation status")
        with self._connection() as connection:
            cursor = connection.execute("UPDATE notices SET status = ? WHERE id = ? AND deleted_at IS NULL", (status, notice_id))
            if cursor.rowcount == 0:
                raise LookupError("Notice not found")
            return self._get_notice(connection, notice_id)

    def delete_notice(self, notice_id):
        with self._connection() as connection:
            cursor = connection.execute("UPDATE notices SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL", (datetime.now().isoformat(timespec="seconds"), notice_id))
            if cursor.rowcount == 0:
                raise LookupError("Notice not found")

    def final_delete_notice(self, notice_id):
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
            if cursor.rowcount == 0:
                raise LookupError("Notice not found")

    def restore_notice(self, notice_id):
        with self._connection() as connection:
            row = connection.execute("SELECT status, deleted_at FROM notices WHERE id = ?", (notice_id,)).fetchone()
            if row is None:
                raise LookupError("Notice not found")
            if row[1] is not None:
                connection.execute("UPDATE notices SET deleted_at = NULL, status = 'approved' WHERE id = ?", (notice_id,))
            elif row[0] == "rejected":
                connection.execute("UPDATE notices SET status = 'pending' WHERE id = ?", (notice_id,))
            else:
                raise ValidationError("Notice is not archived")
            return self._get_notice(connection, notice_id)

    def list_notices(self, filters):
        clauses = ["status = 'approved'", "deleted_at IS NULL", "date(expires_on) >= date('now')"]
        values = []
        search = filters.get("search", "").strip()
        category = filters.get("category", "").strip()
        if search:
            clauses.append("(title LIKE ? OR description LIKE ? OR location LIKE ?)")
            term = f"%{search}%"
            values.extend((term, term, term))
        if category and category in CATEGORIES:
            clauses.append("category = ?")
            values.append(category)
        query = "SELECT * FROM notices WHERE " + " AND ".join(clauses) + " ORDER BY expires_on ASC, created_at DESC"
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(query, values).fetchall()]

    def pending_notices(self):
        with self._connection() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM notices WHERE status = 'pending' AND deleted_at IS NULL ORDER BY created_at DESC").fetchall()]

    def public_archive(self):
        with self._connection() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM notices WHERE status = 'approved' AND deleted_at IS NULL AND date(expires_on) < date('now') ORDER BY expires_on DESC").fetchall()]

    def moderator_archive(self):
        with self._connection() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM notices WHERE status = 'rejected' OR deleted_at IS NOT NULL ORDER BY created_at DESC").fetchall()]

    @staticmethod
    def _get_notice(connection, notice_id):
        row = connection.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()
        return dict(row)
