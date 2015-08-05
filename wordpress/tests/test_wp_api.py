from __future__ import unicode_literals

import logging
from mock import patch, call, DEFAULT
from django.test import TestCase

from .. import wp_api


class WPAPIGetTest(TestCase):

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


class WPAPILoadTest(TestCase):

    @patch.multiple('wordpress.wp_api', load_categories=DEFAULT, load_tags=DEFAULT, load_authors=DEFAULT, load_media=DEFAULT, get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_wp_api(self, load_categories, load_tags, load_authors, load_media, get_ref_data_map, load_posts):

        get_ref_data_map.return_value = {"test": "map"}

        wp_api.load_wp_api(123)

        load_categories.assert_called_once_with(123, purge_first=False, full=False)
        load_tags.assert_called_once_with(123, purge_first=False, full=False)
        load_authors.assert_called_once_with(123, purge_first=False, full=False)
        load_media.assert_called_once_with(123, purge_first=False, full=False, modified_after=None)
        get_ref_data_map.assert_called_once_with(123)

        calls = []
        for post_type in ["attachment", "post", "page"]:
            calls.append(call(123, {"test": "map"}, purge_first=False, full=False, modified_after=None, post_type=post_type))

        load_posts.assert_has_calls(calls)
