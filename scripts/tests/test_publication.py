import contextlib
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_publication import verify


class PublicationTests(unittest.TestCase):
    def test_gemini_prefix_and_image_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'gemini/characters/050').mkdir(parents=True)
            (root / 'gemini/characters.json').write_text('[{"images":{"main":"/gemini/characters/050/main.webp"}}]')
            (root / 'gemini/numbering-audit.json').write_text('{}')
            (root / 'gemini/characters/050/main.webp').write_bytes(b'fixture-bytes')
            server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(SimpleHTTPRequestHandler, directory=d))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                verify(root, f'http://127.0.0.1:{server.server_port}', 'gemini')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_exact_bytes_and_stale_or_spa_response(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'characters.json').write_text('[]')
            (root / 'numbering-audit.json').write_text('{}')
            handler = functools.partial(SimpleHTTPRequestHandler, directory=d)
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}'
                verify(root, url)
                with tempfile.TemporaryDirectory() as other:
                    expected = Path(other)
                    (expected / 'characters.json').write_text('[]')
                    (expected / 'numbering-audit.json').write_text('{"stale":false}')
                    with self.assertRaisesRegex(ValueError, 'publication mismatch'):
                        verify(expected, url)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
