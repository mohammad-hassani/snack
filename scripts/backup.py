"""Snapshot and verify the local SQLite database and uploaded files without stopping Django."""
import argparse
import hashlib
import json
import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path


def backup(source, destination):
    source, destination = Path(source), Path(destination)
    if not (source / 'db.sqlite3').is_file():
        raise ValueError('No SQLite database found. Use pg_dump for PostgreSQL.')
    if destination.exists():
        raise ValueError('Choose a new backup path; existing backups are never overwritten.')
    with tempfile.TemporaryDirectory() as directory:
        snapshot = Path(directory)
        with sqlite3.connect(f'file:{source / "db.sqlite3"}?mode=ro', uri=True) as original:
            with sqlite3.connect(snapshot / 'db.sqlite3') as copied:
                original.backup(copied)
                if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Database integrity check failed.')
        if (source / 'uploads').exists():
            shutil.copytree(source / 'uploads', snapshot / 'uploads')
        manifest = {str(file.relative_to(snapshot)): hashlib.sha256(file.read_bytes()).hexdigest() for file in snapshot.rglob('*') if file.is_file()}
        (snapshot / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(destination, 'x:gz') as archive:
                for file in snapshot.iterdir():
                    archive.add(file, arcname=file.name)
            # Restore into an isolated folder and verify every byte before reporting success.
            with tempfile.TemporaryDirectory() as restored:
                with tarfile.open(destination, 'r:gz') as archive:
                    archive.extractall(restored, filter='data')
                for name, digest in manifest.items():
                    if hashlib.sha256((Path(restored) / name).read_bytes()).hexdigest() != digest:
                        raise ValueError(f'Restore verification failed: {name}')
                with sqlite3.connect(Path(restored) / 'db.sqlite3') as restored_db:
                    if restored_db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('Restored database integrity check failed.')
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return len(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, help='New .tar.gz backup file')
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    count = backup(args.source, args.destination)
    print(f'Backup created and restored successfully: {args.destination} ({count} verified files)')
