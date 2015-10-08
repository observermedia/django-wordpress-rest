from __future__ import unicode_literals

import logging
import json
import os
import datetime

from mock import patch, call, DEFAULT, Mock
from django.test import TestCase
from requests import Response

from .. import loading
from ..models import Post, Tag


class WPAPIInitTest(TestCase):

    def setUp(self):
        logging.getLogger('wordpress.loading').addHandler(logging.NullHandler())

    def test_init(self):
        # bad inputs
        with self.assertRaises(ValueError):
            loading.WPAPILoader(site_id="bad")
        with self.assertRaises(AttributeError):
            loading.WPAPILoader()

        # good inputs
        loading.WPAPILoader(site_id=-1)
        with self.settings(WP_API_SITE_ID=-1):
            loading.WPAPILoader()


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
            calls.append(call(post_type=post_type, status="publish"))

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
        self._test_load_site__one_type_one_status(get_ref_data_map, load_posts, "post", "publish")

    @patch.multiple('wordpress.loading.WPAPILoader', get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_site__page(self, get_ref_data_map, load_posts):
        self._test_load_site__one_type_one_status(get_ref_data_map, load_posts, "page", "publish")

    @patch.multiple('wordpress.loading.WPAPILoader', get_ref_data_map=DEFAULT, load_posts=DEFAULT)
    def test_load_site__attachment(self, get_ref_data_map, load_posts):
        self._test_load_site__one_type_one_status(get_ref_data_map, load_posts, "attachment", "publish")

    def _test_load_site__one_type_one_status(self, get_ref_data_map, load_posts, type, status):

        # call we're testing
        self.loader.load_site(type=type, status=status)

        # validate loading vars
        self.assertFalse(self.loader.purge_first)
        self.assertFalse(self.loader.full)
        self.assertIsNone(self.loader.modified_after)

        # expected internal calls
        get_ref_data_map.assert_called_once_with()
        load_posts.assert_called_once_with(post_type=type, status=status)


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


class WPAPIProcessPostTest(TestCase):

    def setUp(self):
        logging.getLogger('wordpress.loading').addHandler(logging.NullHandler())
        self.test_site_id = -1
        self.loader = loading.WPAPILoader(site_id=self.test_site_id)

    def test_process_post_many_to_many_field(self):

        test_existing_post = Post.objects.create(site_id=self.test_site_id,
                                                 wp_id=-123,
                                                 title="Test Post Y'all",
                                                 post_date=datetime.date(2015, 10, 1),
                                                 modified=datetime.date(2015, 10, 1))
        test_tags = [
            Tag.objects.create(site_id=self.test_site_id,
                               wp_id=-201,
                               name="Test Tag 1",
                               slug="test-tag-1",
                               post_count=1),
            Tag.objects.create(site_id=self.test_site_id,
                               wp_id=-202,
                               name="Test Tag 2",
                               slug="test-tag-2",
                               post_count=1)
        ]

        test_related_tags = {
            -123: test_tags
        }

        # test both tags get attached
        self.loader.process_post_many_to_many_field(test_existing_post, "tags", test_related_tags)
        self.assertEqual(list(test_existing_post.tags.all().order_by("id")), test_tags)

        # remove one and make sure it goes away
        del test_tags[1]

        self.loader.process_post_many_to_many_field(test_existing_post, "tags", test_related_tags)
        self.assertEqual(list(test_existing_post.tags.all().order_by("id")), test_tags)
