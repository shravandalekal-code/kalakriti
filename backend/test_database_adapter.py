import io
import os
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from app import (
    ImageStorageError,
    PostgresCursor,
    insert_and_get_id,
    require_persistent_hosted_database,
    row_value,
    store_uploaded_image,
)


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

    def test_render_upload_requires_cloudinary_configuration(self):
        image = FileStorage(stream=io.BytesIO(b"image-bytes"), filename="craft.jpg")

        with tempfile.TemporaryDirectory() as upload_folder, patch(
            "app.CLOUDINARY_URL", ""
        ), patch("app.UPLOAD_FOLDER", upload_folder), patch.dict(
            os.environ, {"RENDER": "true"}
        ):
            with self.assertRaisesRegex(ImageStorageError, "CLOUDINARY_URL"):
                store_uploaded_image(image)
            self.assertEqual(os.listdir(upload_folder), [])

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
