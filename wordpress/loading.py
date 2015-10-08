from __future__ import unicode_literals

import logging
from datetime import datetime, timedelta

from django.conf import settings
import requests
import six

from wordpress.models import Tag, Category, Author, Post, Media
from wordpress.utils import int_or_None


logger = logging.getLogger(__name__)


class WPAPILoader(object):

    def __init__(self, site_id=None, api_base_url=None):
        """
        Set up a loader object to sync content from a WordPress.com site to a local Django site.

        :param site_id: The identifier for the WordPress.com site from which we are loading content.
                        This must be int (to save local db space).
                        If not given, we use the WP_API_SITE_ID value in settings.
        :param api_base_url: Override WP API url for proxies, etc.
                             If not given, we use the standard URL: https://public-api.wordpress.com/rest/v1.1/
        :return: None
        """
        if site_id is not None:
            try:
                self.site_id = int(site_id)
            except ValueError:
                logger.exception("Must provide site_id as an integer.")
                raise
        else:
            try:
                self.site_id = int(settings.WP_API_SITE_ID)
            except:
                logger.exception("Must provide int site_id as an integer kwarg or in settings.")
                raise

        self.api_base_url = api_base_url or "https://public-api.wordpress.com/rest/v1.1/"

        # useful for displaying warnings only once, etc.
        self.first_get = True

    def get(self, path, params=None):
        """
        Send a GET request to the Wordpress REST API v1.1 and return the response
        :param path: aka resource
        :param params: querystring args
        :return: requests.reponse object
        """
        api_url = self.api_base_url + path

        headers = None
        try:
            headers = {
                "Authorization": 'Bearer {}'.format(settings.WP_API_AUTH_TOKEN)
            }
        except AttributeError:
            if self.first_get:
                logger.warning("WP_API_AUTH_TOKEN not found in settings. Only public APIs are available.")

        self.first_get = False

        return requests.get(api_url, headers=headers, params=params)

    def load_post(self, wp_post_id):
        """
        Refresh local content for a single post from the the WordPress REST API.
        This can be called from a webhook on the WordPress side when a post is updated.

        :param wp_post_id: the wordpress post ID
        :return: the fully loaded local post object
        """
        path = "sites/{}/posts/{}".format(self.site_id, wp_post_id)
        response = self.get(path)

        if response.ok and response.text:

            api_post = response.json()

            self.get_ref_data_map(bulk_mode=False)
            self.load_wp_post(api_post, bulk_mode=False)

            # the post should exist in the db now, so return it so that callers can work with it
            try:
                post = Post.objects.get(site_id=self.site_id, wp_id=wp_post_id)
            except Exception as ex:
                logger.exception("Unable to load post with wp_post_id={}:\n{}".format(wp_post_id, ex.message))
            else:
                return post
        else:
            logger.warning("Unable to load post with wp_post_id={}:\n{}".format(wp_post_id, response.text))

    def load_site(self, purge_first=False, full=False, modified_after=None, type=None, status=None):
        """
        Sync content from a WordPress.com site via the REST API.

        :param purge_first: Should we remove all local content first? Careful, destructive!
        :param full: If True, crawl backwards chronologically through all content, not just recently modified
                     Default is False, only load recently modified content.
        :param modified_after: If None, pick up where we left off last time; otherwise go back to this point in time
                               Default is None, pick up where we left off last time.
        :param type: the type(s) of processing:
            - all: loads all content
            - ref_data: just loads categories, tags, authors, and media
            - post: just loads posts with post_type=post, and related ref data
            - page: just loads posts with post_type=page, and related ref data
            - attachment: just loads posts with post_type=attachment, and related ref data
        :param status: the post statuses to load:
            - publish: loads published posts (default)
            - private: loads private posts
            - draft: loads draft posts
            - pending: loads pending posts
            - future: loads future posts
            - trash: loads posts in the trash
            - any: loads posts with any status

        :return: None
        """
        # capture loading vars
        self.purge_first = purge_first
        self.full = full
        self.modified_after = modified_after

        if type is None:
            type = "all"

        if status is None:
            status = "publish"

        if type in ["all", "ref_data"]:
            self.load_categories()
            self.load_tags()
            self.load_authors()
            self.load_media()

        # get ref data into memory for faster lookups
        if type in ["all", "attachment", "post", "page"]:
            self.get_ref_data_map()

        # load posts of each type that we need
        if type == "all":
            for post_type in ["attachment", "post", "page"]:
                self.load_posts(post_type=post_type, status=status)
        elif type in ["attachment", "post", "page"]:
            self.load_posts(post_type=type, status=status)

    def load_categories(self, max_pages=30):
        """
        Load all WordPress categories from the given site.

        :param max_pages: kill counter to avoid infinite looping
        :return: None
        """
        logger.info("loading categories")

        # clear them all out so we don't get dupes if requested
        if self.purge_first:
            Category.objects.filter(site_id=self.site_id).delete()

        path = "sites/{}/categories".format(self.site_id)
        params = {"number": 100}
        page = 1

        response = self.get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)

        while response.ok and response.text and page < max_pages:
            logger.info(" - page: %d", page)

            api_categories = response.json().get("categories")
            if not api_categories:
                # we're done here
                break

            categories = []
            for api_category in api_categories:

                # if it exists locally, update local version if anything has changed
                existing_category = Category.objects.filter(site_id=self.site_id, wp_id=api_category["ID"]).first()
                if existing_category:
                    self.update_existing_category(existing_category, api_category)
                else:
                    categories.append(self.get_new_category(api_category))

            if categories:
                Category.objects.bulk_create(categories)
            elif not self.full:
                # we're done here
                break

            # get next page
            page += 1
            params["page"] = page
            response = self.get(path, params)

            if not response.ok:
                logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
                return

    def get_new_category(self, api_category):
        """
        Instantiate a new Category from api data.

        :param api_category: the api data for the Category
        :return: the new Category
        """
        return Category(site_id=self.site_id,
                        wp_id=api_category["ID"],
                        **self.api_object_data("category", api_category))

    def load_tags(self, max_pages=30):
        """
        Load all WordPress tags from the given site.

        :param max_pages: kill counter to avoid infinite looping
        :return: None
        """
        logger.info("loading tags")

        # clear them all out so we don't get dupes if requested
        if self.purge_first:
            Tag.objects.filter(site_id=self.site_id).delete()

        path = "sites/{}/tags".format(self.site_id)
        params = {"number": 1000}
        page = 1

        response = self.get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)

        while response.ok and response.text and page < max_pages:
            logger.info(" - page: %d", page)

            api_tags = response.json().get("tags")
            if not api_tags:
                # we're done here
                break

            tags = []
            for api_tag in api_tags:

                # if it exists locally, update local version if anything has changed
                existing_tag = Tag.objects.filter(site_id=self.site_id, wp_id=api_tag["ID"]).first()
                if existing_tag:
                    self.update_existing_tag(existing_tag, api_tag)
                else:
                    tags.append(self.get_new_tag(api_tag))

            if tags:
                Tag.objects.bulk_create(tags)
            elif not self.full:
                # we're done here
                break

            # get next page
            page += 1
            params["page"] = page
            response = self.get(path, params)

            if not response.ok:
                logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
                return

    def get_new_tag(self, api_tag):
        """
        Instantiate a new Tag from api data.

        :param api_tag: the api data for the Tag
        :return: the new Tag
        """
        return Tag(site_id=self.site_id,
                   wp_id=api_tag["ID"],
                   **self.api_object_data("tag", api_tag))

    def load_authors(self, max_pages=10):
        """
        Load all WordPress authors from the given site.

        :param max_pages: kill counter to avoid infinite looping
        :return: None
        """
        logger.info("loading authors")

        # clear them all out so we don't get dupes if requested
        if self.purge_first:
            Author.objects.filter(site_id=self.site_id).delete()

        path = "sites/{}/users".format(self.site_id)
        params = {"number": 100}
        page = 1

        response = self.get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)

        while response.ok and response.text and page < max_pages:
            logger.info(" - page: %d", page)

            api_users = response.json().get("users")
            if not api_users:
                # we're done here
                break

            authors = []
            for api_author in api_users:

                # if it exists locally, update local version if anything has changed
                existing_author = Author.objects.filter(site_id=self.site_id, wp_id=api_author["ID"]).first()
                if existing_author:
                    self.update_existing_author(existing_author, api_author)
                else:
                    authors.append(self.get_new_author(api_author))

            if authors:
                Author.objects.bulk_create(authors)
            elif not self.full:
                # we're done here
                break

            # get next page
            # this endpoint doesn't have a page param, so use offset
            params["offset"] = page * 100
            page += 1
            response = self.get(path, params)

            if not response.ok:
                logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
                return

    def get_new_author(self, api_author):
        """
        Instantiate a new Author from api data.

        :param api_author: the api data for the Author
        :return: the new Author
        """
        return Author(site_id=self.site_id,
                      wp_id=api_author["ID"],
                      **self.api_object_data("author", api_author))

    def load_media(self, max_pages=150):
        """
        Load all WordPress media from the given site.

        :param max_pages: kill counter to avoid infinite looping
        :return: None
        """
        logger.info("loading media")

        # clear them all out so we don't get dupes
        if self.purge_first:
            logger.warning("purging ALL media from site %s", self.site_id)
            Media.objects.filter(site_id=self.site_id).delete()

        path = "sites/{}/media".format(self.site_id)
        params = {"number": 100}
        self.set_media_params_after(params)
        page = 1

        response = self.get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)

        while response.ok and response.text and page < max_pages:
            logger.info(" - page: %d", page)

            api_medias = response.json().get("media")
            if not api_medias:
                # we're done here
                break

            medias = []
            for api_media in api_medias:

                # exclude media items that are not attached to posts (for now)
                if api_media["post_ID"] != 0:

                    # if it exists locally, update local version if anything has changed
                    existing_media = Media.objects.filter(site_id=self.site_id, wp_id=api_media["ID"]).first()
                    if existing_media:
                        self.update_existing_media(existing_media, api_media)
                    else:
                        medias.append(self.get_new_media(api_media))

            if medias:
                Media.objects.bulk_create(medias)

            # get next page
            page += 1
            params["page"] = page
            response = self.get(path, params)

            if not response.ok:
                logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
                return

    def set_media_params_after(self, params):
        """
        If we're not doing a full run, limit to media uploaded to wordpress 'recently'.
        'Recently' in this case means 90 days before the date we're processing content from.
        The wp.com REST API doesn't have a way to limit based on media modification date,
          but this should be relatively close.

        :param params: the GET params dict, which may be updated to include the "after" key
        :return: None (side effect: possibly modified params dict)
        """
        if not self.full:
            if self.modified_after:
                ninety_days_ago = self.modified_after - timedelta(days=90)
            else:
                ninety_days_ago = datetime.utcnow() - timedelta(days=90)
            params["after"] = ninety_days_ago.isoformat()

    def get_new_media(self, api_media):
        """
        Instantiate a new Media from api data.

        :param api_media: the api data for the Media
        :return: the new Media
        """
        return Media(site_id=self.site_id,
                     wp_id=api_media["ID"],
                     **self.api_object_data("media", api_media))

    def get_ref_data_map(self, bulk_mode=True):
        """
        Get referential data from the local db into the self.ref_data_map dictionary.
        This allows for fast FK lookups when looping through posts.

        :param bulk_mode: if True, actually get all of the existing ref data
                          else this would be too much memory, so just build empty dicts
        :return: None
        """
        if bulk_mode:
            self.ref_data_map = {
                "authors": {a.wp_id: a for a in Author.objects.filter(site_id=self.site_id)},
                "categories": {c.wp_id: c for c in Category.objects.filter(site_id=self.site_id)},
                "tags": {t.wp_id: t for t in Tag.objects.filter(site_id=self.site_id)},
                "media": {m.wp_id: m for m in Media.objects.filter(site_id=self.site_id)}
            }
        else:
            # in single post mode, WP ref data is handled dynamically for the post
            self.ref_data_map = {
                "authors": {},
                "categories": {},
                "tags": {},
                "media": {}
            }

    def load_posts(self, post_type=None, max_pages=200, status="publish"):
        """
        Load all WordPress posts of a given post_type from a site.

        :param post_type: post, page, attachment, or any custom post type set up in the WP API
        :param max_pages: kill counter to avoid infinite looping
        :param status: load posts with the given status,
            including any of: "publish", "private", "draft", "pending", "future", and "trash", or simply "any"
            Note: non public statuses require authentication
        :return: None
        """
        logger.info("loading posts with post_type=%s", post_type)

        # clear them all out so we don't get dupes
        if self.purge_first:
            Post.objects.filter(site_id=self.site_id, post_type=post_type).delete()

        path = "sites/{}/posts".format(self.site_id)

        # type allows us to pull information about pages, attachments, guest-authors, etc.
        # you know, posts that aren't posts... thank you WordPress!
        if not post_type:
            post_type = "post"
        params = {"number": 100, "type": post_type, "status": status}
        self.set_posts_param_modified_after(params, post_type, status)

        # get first page
        response = self.get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)

        # process all posts in the response
        self.process_posts_response(response, path, params, max_pages)

    def set_posts_param_modified_after(self, params, post_type, status):
        """
        Set modified_after date to "continue where we left off" if appropriate

        :param params: the GET params dict, which may be updated to include the "modified_after" key
        :param post_type: post, page, attachment, or any custom post type set up in the WP API
        :param status: publish, private, draft, etc.
        :return: None
        """
        if not self.purge_first and not self.full and not self.modified_after:
            latest = Post.objects.filter(post_type=post_type, status=status).order_by("-modified").first()
            if latest:
                self.modified_after = latest.modified

        if self.modified_after:
            params["modified_after"] = self.modified_after.isoformat()
            logger.info("getting posts after: %s", params["modified_after"])

    def process_posts_response(self, response, path, params, max_pages):
        """
        Insert / update all posts in a posts list response, in batches.

        :param response: a response that contains a list of posts from the WP API
        :param path: the path we're using to get the list of posts (for subsquent pages)
        :param params: the path we're using to get the list of posts (for subsquent pages)
        :param max_pages: kill counter to avoid infinite looping
        :return: None
        """
        page = 1
        while response.ok and response.text and page < max_pages:

            logger.info(" - page: %d", page)

            posts = []
            post_categories = {}
            post_tags = {}
            post_media_attachments = {}

            api_json = response.json()
            api_posts = api_json.get("posts")

            # we're done if no posts left to process
            if not api_posts:
                break

            logger.info("post date: %s", api_posts[0]["date"])

            for api_post in api_posts:
                self.load_wp_post(api_post,
                                  bulk_mode=True,
                                  post_categories=post_categories,
                                  post_tags=post_tags,
                                  post_media_attachments=post_media_attachments,
                                  posts=posts)

            if posts:
                self.bulk_create_posts(posts, post_categories, post_tags, post_media_attachments)

            # get next page
            page += 1
            next_page_handle = api_json.get("meta", {}).get("next_page")
            if next_page_handle:
                params["page_handle"] = next_page_handle
            else:
                # no more pages left
                break

            response = self.get(path, params)

            if not response.ok:
                logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
                break

    def load_wp_post(self, api_post, bulk_mode=True, post_categories=None, post_tags=None, post_media_attachments=None, posts=None):
        """
        Load a single post from API data.

        :param api_post: the API data for the post
        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param post_categories: a mapping of Categories in the site, keyed by post ID
        :param post_tags: a mapping of Tags in the site, keyed by post ID
        :param post_media_attachments: a mapping of Media in the site, keyed by post ID
        :param posts: a list of posts to be created or updated
        :return: None
        """
        # initialize reference vars if none supplied
        if post_categories is None:
            post_categories = {}

        if post_tags is None:
            post_tags = {}

        if post_media_attachments is None:
            post_media_attachments = {}

        if posts is None:
            posts = []

        # process objects related to this post
        author = None
        if api_post["author"].get("ID"):
            author = self.process_post_author(bulk_mode, api_post["author"])

        # process many-to-many fields
        self.process_post_categories(bulk_mode, api_post, post_categories)
        self.process_post_tags(bulk_mode, api_post, post_tags)
        self.process_post_media_attachments(bulk_mode, api_post, post_media_attachments)

        # if this post exists, update it; else create it
        existing_post = Post.objects.filter(site_id=self.site_id, wp_id=api_post["ID"]).first()
        if existing_post:
            self.process_existing_post(existing_post, api_post, author, post_categories, post_tags, post_media_attachments)
        else:
            self.process_new_post(bulk_mode, api_post, posts, author, post_categories, post_tags, post_media_attachments)

        # if this is a real post (not an attachment, page, etc.), sync child attachments that haven been deleted
        # these are generally other posts with post_type=attachment representing media that has been "uploaded to the post"
        # they can be deleted on the WP side, creating an orphan here without this step.
        if api_post["type"] == "post":
            self.sync_deleted_attachments(api_post)

    def process_post_author(self, bulk_mode, api_author):
        """
        Create or update an Author related to a post.

        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param api_author: the data in the api for the Author
        :return: the up-to-date Author object
        """
        # get from the ref data map if in bulk mode, else look it up from the db
        if bulk_mode:
            author = self.ref_data_map["authors"].get(api_author["ID"])
            if author:
                self.update_existing_author(author, api_author)
            else:
                # if the author wasn't found (likely because it's a Byline or guest author, not a user),
                # go ahead and create the author now
                author = Author.objects.create(site_id=self.site_id,
                                               wp_id=api_author["ID"],
                                               **self.api_object_data("author", api_author))
        else:
            # do a direct db lookup if we're not in bulk mode
            author, created = self.get_or_create_author(api_author)
            if author and not created:
                self.update_existing_author(author, api_author)

        # add to the ref data map so we don't try to create it again
        if author:
            self.ref_data_map["authors"][api_author["ID"]] = author

        return author

    def get_or_create_author(self, api_author):
        """
        Find or create an Author object given API data.

        :param api_author: the API data for the Author
        :return: a tuple of an Author instance and a boolean indicating whether the author was created or not
        """
        return Author.objects.get_or_create(site_id=self.site_id,
                                            wp_id=api_author["ID"],
                                            defaults=self.api_object_data("author", api_author))

    def process_post_categories(self, bulk_mode, api_post, post_categories):
        """
        Create or update Categories related to a post.

        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param api_post: the API data for the post
        :param post_categories: a mapping of Categories keyed by post ID
        :return: None
        """
        post_categories[api_post["ID"]] = []
        for api_category in six.itervalues(api_post["categories"]):
            category = self.process_post_category(bulk_mode, api_category)
            if category:
                post_categories[api_post["ID"]].append(category)

    def process_post_category(self, bulk_mode, api_category):
        """
        Create or update a Category related to a post.

        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param api_category: the API data for the Category
        :return: the Category object
        """
        # get from the ref data map if in bulk mode, else look it up from the db
        if bulk_mode:
            category = self.ref_data_map["categories"].get(api_category["ID"])
        else:
            category, created = Category.objects.get_or_create(site_id=self.site_id,
                                                               wp_id=api_category["ID"],
                                                               defaults=self.api_object_data("category", api_category))

            if category and not created:
                self.update_existing_category(category, api_category)

            # add to ref data map so later lookups work
            if category:
                self.ref_data_map["categories"][api_category["ID"]] = category

        return category

    def process_post_tags(self, bulk_mode, api_post, post_tags):
        """
        Create or update Tags related to a post.

        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param api_post: the API data for the post
        :param post_tags: a mapping of Tags keyed by post ID
        :return: None
        """
        post_tags[api_post["ID"]] = []
        for api_tag in six.itervalues(api_post["tags"]):
            tag = self.process_post_tag(bulk_mode, api_tag)
            if tag:
                post_tags[api_post["ID"]].append(tag)

    def process_post_tag(self, bulk_mode, api_tag):
        """
        Create or update a Tag related to a post.

        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param api_tag: the API data for the Tag
        :return: the Tag object
        """
        # get from the ref data map if in bulk mode, else look it up from the db
        if bulk_mode:
            tag = self.ref_data_map["tags"].get(api_tag["ID"])
        else:
            tag, created = Tag.objects.get_or_create(site_id=self.site_id,
                                                     wp_id=api_tag["ID"],
                                                     defaults=self.api_object_data("tag", api_tag))
            if tag and not created:
                self.update_existing_tag(tag, api_tag)

            # add to ref data map so later lookups work
            if tag:
                self.ref_data_map["tags"][api_tag["ID"]] = tag

        return tag

    def process_post_media_attachments(self, bulk_mode, api_post, post_media_attachments):
        """
        Create or update Media objects related to a post.

        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param api_post: the API data for the Post
        :param post_media_attachments: a mapping of Media objects keyed by post ID
        :return: None
        """
        post_media_attachments[api_post["ID"]] = []

        for api_attachment in six.itervalues(api_post["attachments"]):
            attachment = self.process_post_media_attachment(bulk_mode, api_attachment)
            if attachment:
                post_media_attachments[api_post["ID"]].append(attachment)

    def process_post_media_attachment(self, bulk_mode, api_media_attachment):
        """
        Create or update a Media attached to a post.

        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param api_media_attachment: the API data for the Media
        :return: the Media attachment object
        """
        # get from the ref data map if in bulk mode, else look it up from the db
        if bulk_mode:
            attachment = self.ref_data_map["media"].get(api_media_attachment["ID"])
        else:
            # do a direct db lookup if we're not in bulk mode
            attachment, created = created = self.get_or_create_media(api_media_attachment)
            if attachment and not created:
                self.update_existing_media(attachment, api_media_attachment)

            # add to ref data map so later lookups work
            if attachment:
                self.ref_data_map["media"][api_media_attachment["ID"]] = attachment

        return attachment

    def get_or_create_media(self, api_media):
        """
        Find or create a Media object given API data.

        :param api_media: the API data for the Media
        :return: a tuple of an Media instance and a boolean indicating whether the Media was created or not
        """
        return Media.objects.get_or_create(site_id=self.site_id,
                                           wp_id=api_media["ID"],
                                           defaults=self.api_object_data("media", api_media))

    @staticmethod
    def process_existing_post(existing_post, api_post, author, post_categories, post_tags, post_media_attachments):
        """
        Sync attributes for a single post from WP API data.

        :param existing_post: Post object that needs to be sync'd
        :param api_post: the API data for the Post
        :param author: the Author object of the post (should already exist in the db)
        :param post_categories: the Categories to attach to the post (should already exist in the db)
        :param post_tags: the Tags to attach to the post (should already exist in the db)
        :param post_media_attachments: the Medias to attach to the post (should already exist in the db)
        :return: None
        """
        # don't bother checking what's different, just update all fields
        existing_post.author = author
        existing_post.post_date = api_post["date"]
        existing_post.modified = api_post["modified"]
        existing_post.title = api_post["title"]
        existing_post.url = api_post["URL"]
        existing_post.short_url = api_post["short_URL"]
        existing_post.content = api_post["content"]
        existing_post.excerpt = api_post["excerpt"]
        existing_post.slug = api_post["slug"]
        existing_post.guid = api_post["guid"]
        existing_post.status = api_post["status"]
        existing_post.sticky = api_post["sticky"]
        existing_post.password = api_post["password"]
        existing_post.parent = api_post["parent"]
        existing_post.post_type = api_post["type"]
        existing_post.likes_enabled = api_post["likes_enabled"]
        existing_post.sharing_enabled = api_post["sharing_enabled"]
        existing_post.like_count = api_post["like_count"]
        existing_post.global_ID = api_post["global_ID"]
        existing_post.featured_image = api_post["featured_image"]
        existing_post.format = api_post["format"]
        existing_post.menu_order = api_post["menu_order"]
        existing_post.metadata = api_post["metadata"]
        existing_post.post_thumbnail = api_post["post_thumbnail"]

        WPAPILoader.process_post_many_to_many_field(existing_post, "categories", post_categories)
        WPAPILoader.process_post_many_to_many_field(existing_post, "tags", post_tags)
        WPAPILoader.process_post_many_to_many_field(existing_post, "attachments", post_media_attachments)

        existing_post.save()

    @staticmethod
    def process_post_many_to_many_field(existing_post, field, related_objects):
        """
        Sync data for a many-to-many field related to a post using set differences.

        :param existing_post: Post object that needs to be sync'd
        :param field: the many-to-many field to update
        :param related_objects: the list of objects for the field, that need to be sync'd to the Post
        :return: None
        """
        to_add = set(related_objects.get(existing_post.wp_id, set())) - set(getattr(existing_post, field).all())
        to_remove = set(getattr(existing_post, field).all()) - set(related_objects.get(existing_post.wp_id, set()))

        if to_add:
            getattr(existing_post, field).add(*to_add)
        if to_remove:
            getattr(existing_post, field).remove(*to_remove)

    def process_new_post(self, bulk_mode, api_post, posts, author, post_categories, post_tags, post_media_attachments):
        """
        Instantiate a new Post object using data from the WP API.
        Related fields -- author, categories, tags, and attachments should be processed in advance

        :param bulk_mode: If True, minimize db operations by bulk creating post objects
        :param api_post: the API data for the Post
        :param posts: the potentially growing list of Posts that we are processing in this run
        :param author: the Author object for this Post
        :param post_categories: the list of Category objects that should be linked to this Post
        :param post_tags: the list of Tags objects that should be linked to this Post
        :param post_media_attachments: the list of Media objects that should be attached to this Post
        :return: None
        """
        post = Post(site_id=self.site_id,
                    wp_id=api_post["ID"],
                    author=author,
                    post_date=api_post["date"],
                    modified=api_post["modified"],
                    title=api_post["title"],
                    url=api_post["URL"],
                    short_url=api_post["short_URL"],
                    content=api_post["content"],
                    excerpt=api_post["excerpt"],
                    slug=api_post["slug"],
                    guid=api_post["guid"],
                    status=api_post["status"],
                    sticky=api_post["sticky"],
                    password=api_post["password"],
                    parent=api_post["parent"],
                    post_type=api_post["type"],
                    likes_enabled=api_post["likes_enabled"],
                    sharing_enabled=api_post["sharing_enabled"],
                    like_count=api_post["like_count"],
                    global_ID=api_post["global_ID"],
                    featured_image=api_post["featured_image"],
                    format=api_post["format"],
                    menu_order=api_post["menu_order"],
                    metadata=api_post["metadata"],
                    post_thumbnail=api_post["post_thumbnail"])
        posts.append(post)

        # if we're not in bulk mode, go ahead and create the post in the db now
        # otherwise this happens after all API posts are processed
        if not bulk_mode:
            self.bulk_create_posts(posts, post_categories, post_tags, post_media_attachments)

    def bulk_create_posts(self, posts, post_categories, post_tags, post_media_attachments):
        """
        Actually do a db bulk creation of posts, and link up the many-to-many fields

        :param posts: the list of Post objects to bulk create
        :param post_categories: a mapping of Categories to add to newly created Posts
        :param post_tags: a mapping of Tags to add to newly created Posts
        :param post_media_attachments: a mapping of Medias to add to newly created Posts
        :return: None
        """
        Post.objects.bulk_create(posts)

        # attach many-to-ones
        for post_wp_id, categories in six.iteritems(post_categories):
            Post.objects.get(site_id=self.site_id, wp_id=post_wp_id).categories.add(*categories)

        for post_id, tags in six.iteritems(post_tags):
            Post.objects.get(site_id=self.site_id, wp_id=post_id).tags.add(*tags)

        for post_id, attachments in six.iteritems(post_media_attachments):
            Post.objects.get(site_id=self.site_id, wp_id=post_id).attachments.add(*attachments)

    def sync_deleted_attachments(self, api_post):
        """
        Remove Posts with post_type=attachment that have been removed from the given Post on the WordPress side.

        Logic:
        - get the list of Posts with post_type = attachment whose parent_id = this post_id
        - get the corresponding list from WP API
        - perform set difference
        - delete extra local attachments if any

        :param api_post: the API data for the Post
        :return: None
        """
        existing_IDs = set(Post.objects.filter(site_id=self.site_id,
                                               post_type="attachment",
                                               parent__icontains='"ID":{}'.format(api_post["ID"]))
                                       .values_list("wp_id", flat=True))

        # can't delete what we don't have
        if existing_IDs:

            api_IDs = set()

            # call the API again to the get the full list of attachment posts whose parent is this post's wp_id
            path = "sites/{}/posts/".format(self.site_id)
            params = {
                "type": "attachment",
                "parent_id": api_post["ID"],
                "fields": "ID",
                "number": 100
            }
            page = 1

            response = self.get(path, params)

            if not response.ok:
                logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)

            # loop around since there may be more than 100 attachments (example: really large slideshows)
            while response.ok and response.text and page < 10:

                api_json = response.json()
                api_attachments = api_json.get("posts", [])

                # iteratively extend the set to include this page's IDs
                api_IDs |= set(a["ID"] for a in api_attachments)

                # get next page
                page += 1
                next_page_handle = api_json.get("meta", {}).get("next_page")
                if next_page_handle:
                    params["page_handle"] = next_page_handle
                else:
                    # no more pages left
                    break

                response = self.get(path, params)

                if not response.ok:
                    logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
                    return

            # perform set difference
            to_remove = existing_IDs - api_IDs

            # purge the extras
            if to_remove:
                Post.objects.filter(site_id=self.site_id,
                                    post_type="attachment",
                                    parent__icontains='"ID":{}'.format(api_post["ID"]),
                                    wp_id__in=list(to_remove)).delete()

    # ------- helpers to update existing objects ---------- #

    fields_mapping = {
        "category": [
            ("name", "name"),
            ("slug", "slug"),
            ("description", "description"),
            ("post_count", "post_count"),
            ("parent_wp_id", "parent"),
        ],
        "tag": [
            ("name", "name"),
            ("slug", "slug"),
            ("description", "description"),
            ("post_count", "post_count"),
        ],
        "author": [
            ("login", "login"),
            ("email", "email"),
            ("name", "name"),
            ("nice_name", "nice_name"),
            ("url", "URL"),
            ("avatar_url", "avatar_URL"),
            ("profile_url", "profile_URL"),
        ],
        "media": [
            ("url", "URL"),
            ("guid", "guid"),
            ("uploaded_date", "date"),
            ("post_ID", "post_ID", int_or_None),
            ("file_name", "file"),
            ("file_extension", "extension"),
            ("mime_type", "mime_type"),
            ("width", "width", int_or_None),
            ("height", "height", int_or_None),
            ("title", "title"),
            ("caption", "caption"),
            ("description", "description"),
            ("alt", "alt"),
            ("exif", "exif"),
        ]
    }

    @classmethod
    def update_existing_category(cls, existing_category, api_category):
        cls.update_existing_obj(cls.fields_mapping["category"], existing_category, api_category)

    @classmethod
    def update_existing_tag(cls, existing_tag, api_tag):
        cls.update_existing_obj(cls.fields_mapping["tag"], existing_tag, api_tag)

    @classmethod
    def update_existing_author(cls, existing_author, api_author):
        cls.update_existing_obj(cls.fields_mapping["author"], existing_author, api_author)

    @classmethod
    def update_existing_media(cls, existing_media, api_media):
        cls.update_existing_obj(cls.fields_mapping["media"], existing_media, api_media)

    @classmethod
    def update_existing_obj(cls, fields, existing_obj, api_data):
        save_it = False

        for field in fields:
            if getattr(existing_obj, field[0]) != api_data.get(field[1]):
                save_it = True
                if len(field) > 2 and callable(field[2]):
                    setattr(existing_obj, field[0], field[2](api_data.get(field[1])))
                else:
                    setattr(existing_obj, field[0], api_data.get(field[1]))

        if save_it:
            existing_obj.save()

    @classmethod
    def api_object_data(cls, type, api_data):
        data = {}

        for field in cls.fields_mapping[type]:
            if len(field) > 2 and callable(field[2]):
                data[field[0]] = field[2](api_data.get(field[1]))
            else:
                data[field[0]] = api_data.get(field[1])

        return data
