import sqlite3
import tarfile
import tempfile
from pathlib import Path
from django.test import SimpleTestCase
from scripts.backup import backup


class BackupTests(SimpleTestCase):
    def test_database_and_upload_restore_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'
            source.mkdir()
            with sqlite3.connect(source / 'db.sqlite3') as database:
                database.execute('CREATE TABLE messages (body TEXT)')
                database.execute('INSERT INTO messages VALUES (?)', ('A persistent conversation 👋',))
            (source / 'uploads').mkdir()
            (source / 'uploads' / 'notes.txt').write_text('Private team notes')
            output = Path(directory) / 'snapshot.tar.gz'
            self.assertEqual(backup(source, output), 2)
            restored = Path(directory) / 'restored'
            with tarfile.open(output) as archive:
                archive.extractall(restored, filter='data')
            with sqlite3.connect(restored / 'db.sqlite3') as database:
                self.assertEqual(database.execute('SELECT body FROM messages').fetchone()[0], 'A persistent conversation 👋')
            self.assertEqual((restored / 'uploads' / 'notes.txt').read_text(), 'Private team notes')
            with self.assertRaises(ValueError):
                backup(source, output)
