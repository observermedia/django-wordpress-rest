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

        # mock returns
        get_ref_data_map.return_value = {"test": "map"}

        # call we're testing
        wp_api.load_wp_api(123)

        # expected internal calls
        load_categories.assert_called_once_with(123, purge_first=False, full=False)
        load_tags.assert_called_once_with(123, purge_first=False, full=False)
        load_authors.assert_called_once_with(123, purge_first=False, full=False)
        load_media.assert_called_once_with(123, purge_first=False, full=False, modified_after=None)
        get_ref_data_map.assert_called_once_with(123)

        calls = []
        for post_type in ["attachment", "post", "page"]:
            calls.append(call(123, {"test": "map"}, purge_first=False, full=False, modified_after=None, post_type=post_type))

        load_posts.assert_has_calls(calls)

    @patch.multiple('wordpress.wp_api', load_categories=DEFAULT, load_tags=DEFAULT, load_authors=DEFAULT, load_media=DEFAULT)
    def test_load_wp_api__ref_data(self, load_categories, load_tags, load_authors, load_media):

        # call we're testing
        wp_api.load_wp_api(123, type="ref_data")

        load_categories.assert_called_once_with(123, purge_first=False, full=False)
        load_tags.assert_called_once_with(123, purge_first=False, full=False)
        load_authors.assert_called_once_with(123, purge_first=False, full=False)
        load_media.assert_called_once_with(123, purge_first=False, full=False, modified_after=None)

    @patch.multiple('wordpress.wp_api', get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_wp_api__post(self, get_ref_data_map, load_posts):
        self._test_load_wp_api__one_type(get_ref_data_map, load_posts, "post")

    @patch.multiple('wordpress.wp_api', get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_wp_api__page(self, get_ref_data_map, load_posts):
        self._test_load_wp_api__one_type(get_ref_data_map, load_posts, "page")

    @patch.multiple('wordpress.wp_api', get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_wp_api__attachment(self, get_ref_data_map, load_posts):
        self._test_load_wp_api__one_type(get_ref_data_map, load_posts, "attachment")

    def _test_load_wp_api__one_type(self, get_ref_data_map, load_posts, type):

        # mock returns
        get_ref_data_map.return_value = {"test": "map"}

        # call we're testing
        wp_api.load_wp_api(123, type=type)

        # expected internal calls
        get_ref_data_map.assert_called_once_with(123)
        load_posts.assert_called_once_with(123, {"test": "map"}, purge_first=False, full=False, modified_after=None, post_type=type)

