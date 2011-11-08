import unittest
import application
import settings
import logging


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        self.client = application.app.test_client()

    def test_index(self):
        resp = self.client.get('/')
        assert(resp.status_code == 200 or resp.status_code == 302)

    def tearDown(self):
        pass

if __name__=="__main__":
    unittest.main()
