import io
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from app import (
    ImageStorageError,
    PostgresCursor,
    app as flask_app,
    insert_and_get_id,
    require_persistent_hosted_database,
    row_value,
    store_uploaded_image,
)


class FakeCursor:
    def __init__(self, row=None):
        self.query = None
        self.params = None
        self.row = row

    def execute(self, query, params):
        self.query = query
        self.params = params
        return self

    def fetchone(self):
        return self.row or {"id": 42}


class FakeConnection:
    def __init__(self, cursor):
        self.test_cursor = cursor

    def cursor(self):
        return self.test_cursor

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class DeleteProductCursor:
    def execute(self, query, params):
        if query.startswith("DELETE"):
            raise sqlite3.IntegrityError("product referenced by an order")

    def fetchone(self):
        return {"id": 7, "artisan_id": 3}


class DeleteProductConnection(FakeConnection):
    def __init__(self):
        super().__init__(DeleteProductCursor())
        self.rolled_back = False
        self.closed = False


class DeleteOrderCursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, params):
        self.queries.append((query, params))

    def fetchone(self):
        return {"id": 3}


class DeleteOrderConnection(FakeConnection):
    def __init__(self):
        super().__init__(DeleteOrderCursor())
        self.committed = False
        self.closed = False

    def commit(self):
        self.committed = True


class DatabaseAdapterTests(unittest.TestCase):
    def test_render_requires_a_persistent_database_url(self):
        with patch.dict("os.environ", {"RENDER": "true"}), patch(
            "app.DATABASE_URL", ""
        ):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL is required on Render"):
                require_persistent_hosted_database()

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

    def test_cloudinary_upload_returns_secure_url(self):
        image = FileStorage(stream=io.BytesIO(b"image-bytes"), filename="craft.jpg")
        secure_url = "https://res.cloudinary.com/demo/image/upload/craft.jpg"

        with patch("app.CLOUDINARY_URL", "cloudinary://key:secret@demo"), patch(
            "app.cloudinary.uploader.upload", return_value={"secure_url": secure_url}
        ) as upload:
            result = store_uploaded_image(image)

        self.assertEqual(result, secure_url)
        upload.assert_called_once_with(
            image.stream,
            folder="kalakriti/products",
            resource_type="image",
            use_filename=False,
            unique_filename=True,
        )

    def test_postgres_upload_uses_database_without_cloudinary_configuration(self):
        image = FileStorage(stream=io.BytesIO(b"image-bytes"), filename="craft.jpg")
        cursor = FakeCursor()

        with patch("app.USE_POSTGRES", True), patch(
            "app.CLOUDINARY_URL", ""
        ), patch("app.BACKEND_PUBLIC_URL", "https://api.example"), patch.dict(
            os.environ, {"RENDER": "true"}
        ):
            image_url = store_uploaded_image(image, cursor)

        self.assertRegex(image_url, r"^https://api\.example/api/product-images/[0-9a-f]{32}$")
        self.assertEqual(
            cursor.query,
            "INSERT INTO product_images (id, content_type, image_data) VALUES (?, ?, ?)",
        )
        self.assertEqual(cursor.params[1:], ("image/jpeg", b"image-bytes"))

    def test_database_image_endpoint_returns_persisted_image_bytes(self):
        cursor = FakeCursor(
            {"content_type": "image/jpeg", "image_data": b"image-bytes"}
        )

        with patch("app.get_db", return_value=FakeConnection(cursor)):
            response = flask_app.test_client().get("/api/product-images/image-id")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        self.assertEqual(response.data, b"image-bytes")
        self.assertEqual(
            response.headers["Cache-Control"],
            "public, max-age=31536000, immutable",
        )

    def test_deleting_ordered_product_returns_conflict_and_preserves_data(self):
        connection = DeleteProductConnection()
        with patch("app.get_db", return_value=connection), patch.dict(
            "app.ACTIVE_TOKENS", {"admin-token": {"user_id": 1, "role": "admin"}}
        ):
            response = flask_app.test_client().delete(
                "/api/artisan/products/7",
                headers={"Authorization": "Bearer admin-token"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("part of an order", response.get_json()["error"])
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_admin_can_delete_order_and_its_line_items(self):
        connection = DeleteOrderConnection()
        with patch("app.get_db", return_value=connection), patch.dict(
            "app.ACTIVE_TOKENS", {"admin-token": {"user_id": 1, "role": "admin"}}
        ):
            response = flask_app.test_client().delete(
                "/api/admin/orders/3",
                headers={"Authorization": "Bearer admin-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("order_items", connection.test_cursor.queries[1][0])
        self.assertIn("DELETE FROM orders", connection.test_cursor.queries[2][0])
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_local_upload_falls_back_to_local_storage(self):
        image = FileStorage(stream=io.BytesIO(b"image-bytes"), filename="craft.JPG")

        with tempfile.TemporaryDirectory() as upload_folder, patch(
            "app.CLOUDINARY_URL", ""
        ), patch("app.UPLOAD_FOLDER", upload_folder), patch(
            "app.BACKEND_PUBLIC_URL", "https://api.example"
        ), patch.dict(os.environ, {"RENDER": "false"}):
            image_url = store_uploaded_image(image)

            filename = image_url.rsplit("/", 1)[1]
            with open(os.path.join(upload_folder, filename), "rb") as stored_image:
                self.assertEqual(stored_image.read(), b"image-bytes")
            self.assertTrue(image_url.startswith("https://api.example/uploads/"))

    def test_unsupported_upload_type_returns_bad_request_error(self):
        image = FileStorage(stream=io.BytesIO(b"not an image"), filename="craft.txt")

        with self.assertRaises(ImageStorageError) as error:
            store_uploaded_image(image)

        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
