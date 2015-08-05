from __future__ import unicode_literals

import logging
from mock import patch
from django.test import TestCase

from .. import wp_api


class WPAPITestGet(TestCase):

    def setUp(self):
        logging.getLogger('wordpress.wp_api').addHandler(logging.NullHandler())

    @patch("requests.get")
    def test_get__basic(self, RequestsGetMock):
        wp_api.get("test")
        RequestsGetMock.assert_called_once_with(wp_api.api_base_url + "test",
                                                headers=None,
                                                params=None)
        self.assertFalse(wp_api.public_api_warnings)

    @patch("requests.get")
    def test_get__params(self, RequestsGetMock):
        wp_api.get("test", params={"x": 1})
        RequestsGetMock.assert_called_once_with(wp_api.api_base_url + "test",
                                                headers=None,
                                                params={"x": 1})
        self.assertFalse(wp_api.public_api_warnings)

    @patch("requests.get")
    def test_get__token(self, RequestsGetMock):
        with self.settings(WP_API_AUTH_TOKEN="abcxyz123456"):
            wp_api.get("test")
            RequestsGetMock.assert_called_once_with(wp_api.api_base_url + "test",
                                                    headers={"Authorization": "Bearer abcxyz123456"},
                                                    params=None)
            self.assertFalse(wp_api.public_api_warnings)

    @patch("requests.get")
    def test_get__params_token(self, RequestsGetMock):
        with self.settings(WP_API_AUTH_TOKEN="abcxyz123456"):
            wp_api.get("test", params={"x": 1})
            RequestsGetMock.assert_called_once_with(wp_api.api_base_url + "test",
                                                    headers={"Authorization": "Bearer abcxyz123456"},
                                                    params={"x": 1})
            self.assertFalse(wp_api.public_api_warnings)
