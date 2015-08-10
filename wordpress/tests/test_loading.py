from __future__ import unicode_literals

import logging
import json
import os

from mock import patch, call, DEFAULT, Mock
from django.test import TestCase
from requests import Response

from .. import loading
from ..models import Post


class WPAPIGetTest(TestCase):

    def setUp(self):
        logging.getLogger('wordpress.loading').addHandler(logging.NullHandler())
        self.loader = loading.WPAPILoader(site_id=-1)

    @patch("requests.get")
    def test_get__basic(self, RequestsGetMock):
        self.loader.get("test")
        RequestsGetMock.assert_called_once_with(self.loader.api_base_url + "test",
                                                headers=None,
                                                params=None)
        self.assertFalse(self.loader.first_get)

    @patch("requests.get")
    def test_get__params(self, RequestsGetMock):
        self.loader.get("test", params={"x": 1})
        RequestsGetMock.assert_called_once_with(self.loader.api_base_url + "test",
                                                headers=None,
                                                params={"x": 1})
        self.assertFalse(self.loader.first_get)

    @patch("requests.get")
    def test_get__token(self, RequestsGetMock):
        with self.settings(WP_API_AUTH_TOKEN="abcxyz123456"):
            self.loader.get("test")
            RequestsGetMock.assert_called_once_with(self.loader.api_base_url + "test",
                                                    headers={"Authorization": "Bearer abcxyz123456"},
                                                    params=None)
            self.assertFalse(self.loader.first_get)

    @patch("requests.get")
    def test_get__params_token(self, RequestsGetMock):
        with self.settings(WP_API_AUTH_TOKEN="abcxyz123456"):
            self.loader.get("test", params={"x": 1})
            RequestsGetMock.assert_called_once_with(self.loader.api_base_url + "test",
                                                    headers={"Authorization": "Bearer abcxyz123456"},
                                                    params={"x": 1})
            self.assertFalse(self.loader.first_get)


class WPAPILoadSiteTest(TestCase):

    def setUp(self):
        logging.getLogger('wordpress.loading').addHandler(logging.NullHandler())
        self.test_site_id = -1
        self.loader = loading.WPAPILoader(site_id=self.test_site_id)

    @patch.multiple('wordpress.loading.WPAPILoader', load_categories=DEFAULT, load_tags=DEFAULT, load_authors=DEFAULT, load_media=DEFAULT, get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_site(self, load_categories, load_tags, load_authors, load_media, get_ref_data_map, load_posts):

        # call we're testing
        self.loader.load_site()

        # validate loading vars
        self.assertFalse(self.loader.purge_first)
        self.assertFalse(self.loader.full)
        self.assertIsNone(self.loader.modified_after)

        # expected internal calls
        load_categories.assert_called_once_with()
        load_tags.assert_called_once_with()
        load_authors.assert_called_once_with()
        load_media.assert_called_once_with()
        get_ref_data_map.assert_called_once_with()

        calls = []
        for post_type in ["attachment", "post", "page"]:
            calls.append(call(post_type=post_type))

        load_posts.assert_has_calls(calls)

    @patch.multiple('wordpress.loading.WPAPILoader', load_categories=DEFAULT, load_tags=DEFAULT, load_authors=DEFAULT, load_media=DEFAULT)
    def test_load_site__ref_data(self, load_categories, load_tags, load_authors, load_media):

        # call we're testing
        self.loader.load_site(type="ref_data")

        load_categories.assert_called_once_with()
        load_tags.assert_called_once_with()
        load_authors.assert_called_once_with()
        load_media.assert_called_once_with()

    @patch.multiple('wordpress.loading.WPAPILoader', get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_site__post(self, get_ref_data_map, load_posts):
        self._test_load_site__one_type(get_ref_data_map, load_posts, "post")

    @patch.multiple('wordpress.loading.WPAPILoader', get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_site__page(self, get_ref_data_map, load_posts):
        self._test_load_site__one_type(get_ref_data_map, load_posts, "page")

    @patch.multiple('wordpress.loading.WPAPILoader', get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_site__attachment(self, get_ref_data_map, load_posts):
        self._test_load_site__one_type(get_ref_data_map, load_posts, "attachment")

    def _test_load_site__one_type(self, get_ref_data_map, load_posts, type):

        # call we're testing
        self.loader.load_site(type=type)

        # validate loading vars
        self.assertFalse(self.loader.purge_first)
        self.assertFalse(self.loader.full)
        self.assertIsNone(self.loader.modified_after)

        # expected internal calls
        get_ref_data_map.assert_called_once_with()
        load_posts.assert_called_once_with(post_type=type)


class WPAPILoadPostTest(TestCase):

    def setUp(self):
        logging.getLogger('wordpress.loading').addHandler(logging.NullHandler())
        self.test_site_id = -1
        self.loader = loading.WPAPILoader(site_id=self.test_site_id)

    @patch("requests.get")
    def test_load_post(self, RequestsGetMock):

        # set up a mock response with stubbed json to simulate the API
        def read_post_json():
            with open(os.path.join(os.path.dirname(__file__), "data", "post.json")) as post_json_file:
                return json.load(post_json_file)

        mock_response = Mock(Response)
        mock_response.ok = True
        mock_response.text = "some text"
        mock_response.json = read_post_json

        RequestsGetMock.return_value = mock_response

        # call we're testing
        post = self.loader.load_post(1)

        # some validations
        self.assertIsInstance(post, Post)
        self.assertEqual(post.wp_id, 1)
        self.assertEqual(post.title, "This is a Test Post")
        self.assertEqual(post.author.name, "testauthor")
        self.assertEqual(post.categories.first().name, "News")
        self.assertEqual(post.tags.first().name, "Testing")
        self.assertEqual(post.attachments.first().url, "https://test.local/testpost.jpg")