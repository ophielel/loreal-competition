import json
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from server import Handler


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_first_snapshot_does_not_expose_future_ticket(self):
        with urlopen(self.url + '/api/session?id=S00010&cursor=1') as r:
            data = json.load(r)
        self.assertEqual(len(data['session']['messages']), 1)
        self.assertEqual(data['session']['tickets'], [])
        self.assertNotIn('label', data['session'])

    def test_out_of_range_returns_400(self):
        with self.assertRaises(HTTPError) as cm:
            urlopen(self.url + '/api/session?id=S00010&cursor=10000')
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_source_files_not_served(self):
        with self.assertRaises(HTTPError) as cm:
            urlopen(self.url + '/server.py')
        self.assertEqual(cm.exception.code, 404)
        cm.exception.close()

    def test_cross_origin_mutation_denied(self):
        req = Request(self.url+'/api/tasks', b'{}', headers={'Content-Type':'application/json', 'Origin':'https://example.com'})
        with self.assertRaises(HTTPError) as cm:
            urlopen(req)
        self.assertEqual(cm.exception.code, 403)
        cm.exception.close()

    def test_invalid_json_returns_400(self):
        req = Request(self.url+'/api/tasks', b'{oops', headers={'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as cm:
            urlopen(req)
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()
