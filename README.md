# Community Noticeboard

A prototype digital noticeboard for a small community. It helps residents find timely local information while giving a lightweight moderation workflow to reduce misleading or inappropriate posts.

## Run locally

```bash
./launch.sh
```

Open <http://127.0.0.1:8000>.

The app uses only the Python 3 standard library. The first run creates `noticeboard.db` and adds two demonstration notices.

The moderator password defaults to `noticeboard` for demonstration purposes. Set `NOTICEBOARD_ADMIN_PASSWORD` before launching to use a different password. The application signs an eight-hour, `HttpOnly` session cookie using `NOTICEBOARD_SESSION_SECRET`; moderation routes reject requests without a valid session. This is appropriate for demonstrating an authentication boundary in the prototype, but a production deployment would need HTTPS, account storage, rate limiting, password hashing, CSRF protection, and role management.

## How the project works

Residents can browse current notices, search by keyword, filter by category, and submit a notice with a location, contact detail, and expiry date. New notices are stored as `pending` and do not appear publicly until a signed-in moderator approves them. Rejected notices remain out of the public listing. Public queries include only approved notices whose expiry date has not passed, so old information is removed from the active board automatically. This keeps the board useful without asking residents to manually clean up old posts.

The password form protects the moderation view and the approve/reject API endpoints. Public browsing, category loading, and notice submission do not require moderator access.

## Architecture

- **Presentation layer:** `static/index.html`, `static/styles.css`, `static/app.js`
- **API layer:** `app.py` exposes HTTP endpoints and translates requests/responses
- **Business layer:** `noticeboard_service.py` validates input, applies expiry and moderation rules, and builds queries
- **Data layer:** SQLite database stored in `noticeboard.db`

## Prototype functionality

- Browse approved, unexpired notices
- Search by title, description, or location
- Filter by category
- Submit a notice for moderation
- Password-protected moderation queue for approving, rejecting, or deleting notices
- Sign-out control for shared or publicly accessible devices
- Public archive of expired approved notices
- Moderator archive of rejected and withdrawn notices
- Undo for archived notices and authenticated permanent deletion when records must be wiped
- Validate required fields, category, character limits, and expiry dates

This is an assessed prototype. Rate limiting, email verification, audit logs, and deployment configuration remain future work rather than being presented as production features.
