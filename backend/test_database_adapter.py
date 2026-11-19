import unittest
from unittest.mock import patch

from app import PostgresCursor, insert_and_get_id, row_value


class FakeCursor:
    def __init__(self):
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.query = query
        self.params = params
        return self

    def fetchone(self):
        return {"id": 42}


class DatabaseAdapterTests(unittest.TestCase):
    def test_postgres_cursor_translates_sqlite_placeholders(self):
        cursor = FakeCursor()

        PostgresCursor(cursor).execute(
            "UPDATE users SET name = ? WHERE id = ?", ("A", 7)
        )

        self.assertEqual(cursor.query, "UPDATE users SET name = %s WHERE id = %s")
        self.assertEqual(cursor.params, ("A", 7))

    def test_postgres_insert_returns_generated_id(self):
        cursor = FakeCursor()

        with patch("app.USE_POSTGRES", True):
            user_id = insert_and_get_id(
                PostgresCursor(cursor),
                "INSERT INTO users (name) VALUES (?)",
                ("A",),
            )

        self.assertEqual(user_id, 42)
        self.assertEqual(
            cursor.query, "INSERT INTO users (name) VALUES (%s) RETURNING id"
        )

    def test_row_value_supports_postgres_mapping_rows(self):
        self.assertEqual(row_value({"total": 3, "amount": 12.5}, 1), 12.5)


if __name__ == "__main__":
    unittest.main()
