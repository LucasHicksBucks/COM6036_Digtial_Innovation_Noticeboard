import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from noticeboard_service import NoticeboardService, ValidationError


class NoticeboardServiceTests(unittest.TestCase):
    def setUp(self):
        self.database = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.service = NoticeboardService(Path(self.database.name))

    def tearDown(self):
        Path(self.database.name).unlink(missing_ok=True)

    def valid_notice(self, **overrides):
        values = {
            "title": "Community gardening morning",
            "description": "Bring gloves and meet new neighbours.",
            "category": "Events",
            "location": "Allotment gate",
            "contact": "garden@example.org",
            "expires_on": str(date.today() + timedelta(days=10)),
        }
        values.update(overrides)
        return values

    def test_new_notice_is_pending_and_hidden_from_public_list(self):
        notice = self.service.submit_notice(self.valid_notice())
        self.assertEqual(notice["status"], "pending")
        self.assertFalse(any(item["id"] == notice["id"] for item in self.service.list_notices({})))

    def test_approved_notice_is_public(self):
        notice = self.service.submit_notice(self.valid_notice())
        self.service.moderate_notice(notice["id"], "approved")
        public = self.service.list_notices({"category": "Events"})
        self.assertTrue(any(item["id"] == notice["id"] for item in public))

    def test_current_notice_is_public_and_searchable(self):
        notice = self.service.submit_notice(self.valid_notice(expires_on=str(date.today())))
        self.service.moderate_notice(notice["id"], "approved")
        self.assertTrue(any(item["id"] == notice["id"] for item in self.service.list_notices({})))
        self.assertEqual(self.service.list_notices({"search": "gardening"})[0]["id"], notice["id"])

    def test_invalid_category_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.submit_notice(self.valid_notice(category="Something else"))

    def test_notice_can_be_deleted(self):
        notice = self.service.submit_notice(self.valid_notice())
        self.service.delete_notice(notice["id"])
        with self.assertRaises(LookupError):
            self.service.moderate_notice(notice["id"], "approved")

    def test_expired_approved_notice_is_in_public_archive(self):
        notice = self.service.submit_notice(self.valid_notice(expires_on=str(date.today() + timedelta(days=1))))
        self.service.moderate_notice(notice["id"], "approved")
        with self.service._connection() as connection:
            connection.execute("UPDATE notices SET expires_on = ? WHERE id = ?", (str(date.today() - timedelta(days=1)), notice["id"]))
        archive = self.service.public_archive()
        self.assertTrue(any(item["id"] == notice["id"] for item in archive))

    def test_rejected_and_deleted_notices_are_in_moderator_archive(self):
        rejected = self.service.submit_notice(self.valid_notice(title="Rejected notice"))
        self.service.moderate_notice(rejected["id"], "rejected")
        deleted = self.service.submit_notice(self.valid_notice(title="Withdrawn notice"))
        self.service.delete_notice(deleted["id"])
        archive = self.service.moderator_archive()
        self.assertEqual({item["title"] for item in archive}, {"Rejected notice", "Withdrawn notice"})

    def test_rejected_notice_can_be_restored_to_review(self):
        notice = self.service.submit_notice(self.valid_notice())
        self.service.moderate_notice(notice["id"], "rejected")
        restored = self.service.restore_notice(notice["id"])
        self.assertEqual(restored["status"], "pending")

    def test_withdrawn_notice_can_be_restored_and_finally_deleted(self):
        notice = self.service.submit_notice(self.valid_notice())
        self.service.moderate_notice(notice["id"], "approved")
        self.service.delete_notice(notice["id"])
        restored = self.service.restore_notice(notice["id"])
        self.assertEqual(restored["status"], "approved")
        self.service.final_delete_notice(notice["id"])
        with self.assertRaises(LookupError):
            self.service.restore_notice(notice["id"])


if __name__ == "__main__":
    unittest.main()
