from __future__ import unicode_literals

import logging
from datetime import datetime, timedelta

from django.conf import settings
import requests

from wordpress.models import Tag, Category, Author, Post, Media


"""
Functions that use the WordPress.com REST API to sync remote content
"""

logger = logging.getLogger(__name__)


# keep track of whether we've warned about public API access
public_api_warnings = True


def get(path, params=None):
    """
    Send a GET request to the Wordpress REST API v1.1 and return the response
    :param path: aka resource
    :param params: querystring args
    :return: requests.reponse object
    """
    global public_api_warnings

    api_url = "https://public-api.wordpress.com/rest/v1.1/" + path

    headers = None
    if hasattr(settings, "WP_API_AUTH_TOKEN"):
        headers = {
            "Authorization": 'Bearer {}'.format(settings.WP_API_AUTH_TOKEN)
        }
    else:
        if public_api_warnings:
            logger.warning("WP_API_AUTH_TOKEN not found in settings. Only public APIs are available.")
            public_api_warnings = False

    return requests.get(api_url, headers=headers, params=params)


def load_wp_api_one_post(site_id, wp_post_id):
    """
    Refresh local content for a single post from the the WordPress REST API
    Called from a webhook on the WordPress side when a post is published (or updated after being published)
    """
    path = "sites/{}/posts/{}".format(site_id, wp_post_id)
    response = get(path)

    if response.ok and response.text:

        api_post = response.json()

        # need to tune this for the non bulk mode case, so that we don't have to get *all* ref data
        ref_data_map = get_ref_data_map(site_id, bulk_mode=False)
        load_wp_post(site_id, api_post, ref_data_map=ref_data_map, bulk_mode=False)

        # the post should exist in the db now, so return it so that callers can work with it
        try:
            post = Post.objects.get(site_id=site_id, wp_id=wp_post_id)
        except Exception as ex:
            logger.exception("Unable to load post with wp_post_id={}:\n{}".format(wp_post_id, ex.message))
        else:
            return post
    else:
        logger.warning("Unable to load post with wp_post_id={}:\n{}".format(wp_post_id, response.text))


def load_wp_api(site_id, purge_first=False, full=False, modified_after=None, type=None):
    """
    Sync content from a WordPress.com site via the REST API.

    :param site_id: The WordPress.com site identifier, either a number or a domain name
    :param purge_first: Should we remove all local content first? CAREFUL...
    :param full: If True, crawl backwards chronologically through all content, not just recently modified
    :param modified_after: If None, pick up where we left off last time; otherwise go back to this point in time
    :param type: the type(s) of processing:
        - all: loads all content
        - ref_data: just loads categories, tags, authors, and media
        - post: just loads posts with post_type=post, and related ref data
        - page: just loads posts with post_type=page, and related ref data
        - attachment: just loads posts with post_type=attachment, and related ref data
    :return: None
    """
    if type is None:
        type = "all"

    if type in ["all", "ref_data"]:
        load_categories(site_id, purge_first=purge_first, full=full)
        load_tags(site_id, purge_first=purge_first, full=full)
        load_authors(site_id, purge_first=purge_first, full=full)
        load_media(site_id, purge_first=purge_first, full=full, modified_after=modified_after)

    # get ref data into memory for faster lookups
    if type in ["all", "attachment", "post", "page"]:
        ref_data_map = get_ref_data_map(site_id)

    # load posts of each type that we need
    if type == "all":
        for post_type in ["attachment", "post", "page"]:
            load_posts(site_id, ref_data_map, purge_first=purge_first, full=full, modified_after=modified_after, post_type=post_type)
    elif type in ["attachment", "post", "page"]:
        load_posts(site_id, ref_data_map, purge_first=purge_first, full=full, modified_after=modified_after, post_type=type)


def load_categories(site_id, max_pages=30, purge_first=False, full=False):
    """
    Load all WordPress categories from the given site_id
    """
    logger.info("loading categories")

    # clear them all out so we don't get dupes
    if purge_first:
        Category.objects.filter(site_id=site_id).delete()

    path = "sites/{}/categories".format(site_id)
    params = {"number": 100}
    page = 1

    response = get(path, params)

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
            existing_category = Category.objects.filter(site_id=site_id, wp_id=api_category["ID"]).first()
            if existing_category:
                update_existing_category(existing_category, api_category)
            else:
                categories.append(get_new_category(site_id, api_category))

        if categories:
            Category.objects.bulk_create(categories)
        elif not full:
            # we're done here
            break

        # get next page
        page += 1
        params["page"] = page
        response = get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
            return


def get_new_category(site_id, api_category):
    return Category(site_id=site_id, wp_id=api_category["ID"], **api_object_data("category", api_category))


def load_tags(site_id, max_pages=30, purge_first=False, full=False):
    """
    Load all WordPress tags from the given site_id
    """
    logger.info("loading tags")

    # clear them all out so we don't get dupes
    if purge_first:
        Tag.objects.filter(site_id=site_id).delete()

    path = "sites/{}/tags".format(site_id)
    params = {"number": 1000}
    page = 1

    response = get(path, params)

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
            existing_tag = Tag.objects.filter(site_id=site_id, wp_id=api_tag["ID"]).first()
            if existing_tag:
                update_existing_tag(existing_tag, api_tag)
            else:
                tags.append(get_new_tag(site_id, api_tag))

        if tags:
            Tag.objects.bulk_create(tags)
        elif not full:
            # we're done here
            break

        # get next page
        page += 1
        params["page"] = page
        response = get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
            return


def get_new_tag(site_id, api_tag):
    return Tag(site_id=site_id, wp_id=api_tag["ID"], **api_object_data("tag", api_tag))


def load_authors(site_id, max_pages=10, purge_first=False, full=False):
    """
    Load all WordPress authors from the given site_id
    """
    logger.info("loading authors")

    # clear them all out so we don't get dupes
    if purge_first:
        Author.objects.filter(site_id=site_id).delete()

    path = "sites/{}/users".format(site_id)
    params = {"number": 100}
    page = 1

    response = get(path, params)

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
            existing_author = Author.objects.filter(site_id=site_id, wp_id=api_author["ID"]).first()
            if existing_author:
                update_existing_author(existing_author, api_author)
            else:
                authors.append(get_new_author(site_id, api_author))

        if authors:
            Author.objects.bulk_create(authors)
        elif not full:
            # we're done here
            break

        # get next page
        # this endpoint doesn't have a page param, so use offset
        params["offset"] = page * 100
        page += 1
        response = get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
            return


def get_new_author(site_id, api_author):
    return Author(site_id=site_id, wp_id=api_author["ID"], **api_object_data("author", api_author))


def load_media(site_id, max_pages=150, purge_first=False, full=False, modified_after=None):
    """
    Load all WordPress media from the given site_id
    """
    logger.info("loading media")

    # clear them all out so we don't get dupes
    if purge_first:
        logger.warning("purging ALL media from site %s", site_id)
        Media.objects.filter(site_id=site_id).delete()

    path = "sites/{}/media".format(site_id)
    params = {"number": 100}
    set_media_params_after(params, full, modified_after)
    page = 1

    response = get(path, params)

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
                existing_media = Media.objects.filter(site_id=site_id, wp_id=api_media["ID"]).first()
                if existing_media:
                    update_existing_media(existing_media, api_media)
                else:
                    medias.append(get_new_media(site_id, api_media))

        if medias:
            Media.objects.bulk_create(medias)

        # get next page
        page += 1
        params["page"] = page
        response = get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
            return


def set_media_params_after(params, full, modified_after):
    """
    If we're not doing a full run, limit to media uploaded to wordpress in the last 90 days.
    The wp.com REST API doesn't have a way to limit based on media modification date,
      but this should be close enough
    """
    if not full:
        if modified_after:
            ninety_days_ago = modified_after - timedelta(days=90)
        else:
            ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        params["after"] = ninety_days_ago.isoformat()


def get_new_media(site_id, api_media):
    return Media(site_id=site_id, wp_id=api_media["ID"], **api_object_data("media", api_media))


def get_ref_data_map(site_id, bulk_mode=True):
    """
    Get related data from the local db into a dictionary
    for fast FK lookups when looping through posts
    """
    if bulk_mode:
        return {
            "authors": {a.wp_id: a for a in Author.objects.filter(site_id=site_id)},
            "categories": {c.wp_id: c for c in Category.objects.filter(site_id=site_id)},
            "tags": {t.wp_id: t for t in Tag.objects.filter(site_id=site_id)},
            "media": {m.wp_id: m for m in Media.objects.filter(site_id=site_id)}
        }
    else:
        # in single post mode, WP ref data is handled dynamically for the post
        return {
            "authors": {},
            "categories": {},
            "tags": {},
            "media": {}
        }


def load_posts(site_id, ref_data_map, max_pages=200, purge_first=False, full=False, modified_after=None, post_type=None):
    """
    Load all WordPress posts from the given site_id
    """
    logger.info("loading posts with post_type=%s", post_type)

    # clear them all out so we don't get dupes
    if purge_first:
        Post.objects.filter(site_id=site_id, post_type=post_type).delete()

    path = "sites/{}/posts".format(site_id)

    # type allows us to pull information about pages, attachments, guest-authors, etc.
    # you know, posts that aren't posts... thank you WordPress!
    if not post_type:
        post_type = "post"
    params = {"number": 100, "type": post_type}
    set_posts_param_modified_after(params, purge_first, full, modified_after, post_type)
    page = 1

    # get first page
    response = get(path, params)

    if not response.ok:
        logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)

    # process all posts in the response
    process_posts(site_id, response, ref_data_map, path, params, page, max_pages)


def set_posts_param_modified_after(params, purge_first, full, modified_after, post_type):
    """
    Set modified_after to "continue where we left off" if appropriate
    """
    if not purge_first and not full and not modified_after:
        latest = Post.objects.filter(post_type=post_type).order_by("-modified").first()
        if latest:
            modified_after = latest.modified

    if modified_after:
        params["modified_after"] = modified_after.isoformat()
        logger.info("getting posts after: %s", params["modified_after"])


def process_posts(site_id, response, ref_data_map, path, params, page, max_pages):
    """
    Insert / update all posts, in batches.
    """
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
            load_wp_post(site_id,
                         api_post,
                         bulk_mode=True,
                         ref_data_map=ref_data_map,
                         post_categories=post_categories,
                         post_tags=post_tags,
                         post_media_attachments=post_media_attachments,
                         posts=posts)

        if posts:
            bulk_create_posts(site_id, posts, post_categories, post_tags, post_media_attachments)

        # get next page
        page += 1
        next_page_handle = api_json.get("meta", {}).get("next_page")
        if next_page_handle:
            params["page_handle"] = next_page_handle
        else:
            # no more pages left
            break

        response = get(path, params)

        if not response.ok:
            logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
            break


def load_wp_post(site_id, api_post, bulk_mode=True, ref_data_map=None, post_categories=None, post_tags=None, post_media_attachments=None, posts=None):
    """
    This does the heavy lifting, either in a loop processing a page of posts, or for a single post
    """
    # initialize reference vars if none supplied
    if ref_data_map is None:
        ref_data_map = {
            "authors": {},
            "categories": {},
            "tags": {},
            "media": {},
            "channels": {},
            "subchannels": {}
        }

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
        author = process_post_author(site_id, ref_data_map, bulk_mode, api_post["author"], api_post["metadata"])

    existing_post = Post.objects.filter(site_id=site_id, wp_id=api_post["ID"]).first()
    if existing_post:
        process_existing_post(existing_post, api_post, author, post_categories, post_tags, post_media_attachments)
    else:
        process_new_post(site_id, bulk_mode, api_post, posts, author, post_categories, post_tags, post_media_attachments)

    # if this is a real post, sync child attachments that haven been deleted
    # these are generally other posts with post_type=attachment
    # for media "uploaded to the post"
    # they can be deleted on the WP side, creating an orphan here without this step
    if api_post["type"] == "post":
        sync_deleted_attachments(site_id, api_post)


def process_post_author(site_id, ref_data_map, bulk_mode, api_author, api_metadata):
    # get from the ref data map if in bulk mode, else look it up from the db
    if bulk_mode:
        author = ref_data_map["authors"].get(api_author["ID"])
        if author:
            update_existing_author(author, api_author)
        else:
            # if the author wasn't found (likely because it's a Byline or guest author, not a user),
            # go ahead and create the author now
            author = Author.objects.create(site_id=site_id,
                                           wp_id=api_author["ID"],
                                           **api_object_data("author", api_author))
    else:
        # do a direct db lookup if we're not in bulk mode
        author, created = get_or_create_author(site_id, api_author)
        if author and not created:
            update_existing_author(author, api_author)

    # add to the ref data map so we don't try to create it again
    if author:
        ref_data_map["authors"][api_author["ID"]] = author

    return author


def get_or_create_author(site_id, api_author):
    return Author.objects.get_or_create(site_id=site_id,
                                        wp_id=api_author["ID"],
                                        defaults=api_object_data("author", api_author))


def process_post_categories(site_id, ref_data_map, bulk_mode, api_post, post_categories):

    channel, subchannel = None, None
    post_categories[api_post["ID"]] = []

    for api_category in api_post["categories"].itervalues():
        category = process_post_category(site_id, ref_data_map, bulk_mode, api_category)
        # derive channel and subchannel from category,
        # except if the current category is the root "channel" node
        if category:
            post_categories[api_post["ID"]].append(category)
            if category.slug != "channel":
                # first one wins if there are multiple
                if not channel:
                    channel = ref_data_map["channels"].get(category.slug)
                # first one wins if there are multiple
                if not subchannel:
                    subchannel = ref_data_map["subchannels"].get(category.slug)

    return channel, subchannel


def process_post_category(site_id, ref_data_map, bulk_mode, api_category):
    # get from the ref data map if in bulk mode, else look it up from the db
    if bulk_mode:
        category = ref_data_map["categories"].get(api_category["ID"])
    else:
        category, created = Category.objects.get_or_create(site_id=site_id,
                                                           wp_id=api_category["ID"],
                                                           defaults=api_object_data("category", api_category))

        if category and not created:
            update_existing_category(category, api_category)

        # add to ref data map so later lookups work
        if category:
            ref_data_map["categories"][api_category["ID"]] = category

    return category


def process_post_tags(site_id, ref_data_map, bulk_mode, api_post, post_tags):

    is_slideshow = False
    post_tags[api_post["ID"]] = []
    for api_tag in api_post["tags"].itervalues():
        tag = process_post_tag(site_id, ref_data_map, bulk_mode, api_tag)
        # determine if this post is a slideshow based on the existence of a magic tag
        # probably not the best way to do this, but it's legacy...
        if tag:
            post_tags[api_post["ID"]].append(tag)
            if tag.slug == "slideshow":
                is_slideshow = True

    return is_slideshow


def process_post_tag(site_id, ref_data_map, bulk_mode, api_tag):
    # get from the ref data map if in bulk mode, else look it up from the db
    if bulk_mode:
        tag = ref_data_map["tags"].get(api_tag["ID"])
    else:
        tag, created = Tag.objects.get_or_create(site_id=site_id,
                                                 wp_id=api_tag["ID"],
                                                 defaults=api_object_data("tag", api_tag))
        if tag and not created:
            update_existing_tag(tag, api_tag)

        # add to ref data map so later lookups work
        if tag:
            ref_data_map["tags"][api_tag["ID"]] = tag

    return tag


def process_post_media_attachments(site_id, ref_data_map, bulk_mode, api_post, post_media_attachments):

    post_media_attachments[api_post["ID"]] = []

    for api_attachment in api_post["attachments"].itervalues():
        attachment = process_post_media_attachment(site_id, ref_data_map, bulk_mode, api_attachment)
        if attachment:
            post_media_attachments[api_post["ID"]].append(attachment)


def process_post_media_attachment(site_id, ref_data_map, bulk_mode, api_media_attachment):
    # get from the ref data map if in bulk mode, else look it up from the db
    if bulk_mode:
        attachment = ref_data_map["media"].get(api_media_attachment["ID"])
    else:
        # do a direct db lookup if we're not in bulk mode
        attachment, created = created = get_or_create_media(site_id, api_media_attachment)
        if attachment and not created:
            update_existing_media(attachment, api_media_attachment)

        # add to ref data map so later lookups work
        if attachment:
            ref_data_map["media"][api_media_attachment["ID"]] = attachment

    return attachment


def get_or_create_media(site_id, api_media):
    return Media.objects.get_or_create(site_id=site_id,
                                       wp_id=api_media["ID"],
                                       defaults=api_object_data("media", api_media))


def process_existing_post(existing_post, api_post, author, post_categories, post_tags, post_media_attachments):

    post_id = api_post["ID"]

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

    categories_to_add = set(post_categories.get(post_id, set())) - set(existing_post.categories.all())
    categories_to_remove = set(existing_post.categories.all()) - set(post_categories.get(post_id, set()))

    if categories_to_add:
        existing_post.categories.add(*categories_to_add)
    if categories_to_remove:
        existing_post.categories.remove(*categories_to_remove)

    tags_to_add = set(post_tags.get(post_id, set())) - set(existing_post.tags.all())
    tags_to_remove = set(existing_post.tags.all()) - set(post_tags.get(post_id, set()))

    if tags_to_add:
        existing_post.tags.add(*tags_to_add)
    if tags_to_remove:
        existing_post.tags.remove(*tags_to_remove)

    attachments_to_add = set(post_media_attachments.get(post_id, set())) - set(existing_post.attachments.all())
    attachments_to_remove = set(existing_post.attachments.all()) - set(post_media_attachments.get(post_id, set()))

    if attachments_to_add:
        existing_post.attachments.add(*attachments_to_add)
    if attachments_to_remove:
        existing_post.attachments.remove(*attachments_to_remove)

    existing_post.save()


def process_new_post(site_id, bulk_mode, api_post, posts, author, post_categories, post_tags, post_media_attachments):

    # use bulk_create because it's faster when creating multiple posts in the db
    post = Post(site_id=site_id,
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

    if not bulk_mode:
        bulk_create_posts(site_id, posts, post_categories, post_tags, post_media_attachments)


def bulk_create_posts(site_id, posts, post_categories, post_tags, post_media_attachments):

    Post.objects.bulk_create(posts)

    # attach categories
    for post_wp_id, categories in post_categories.iteritems():
        Post.objects.get(site_id=site_id, wp_id=post_wp_id).categories.add(*categories)

    # attach tags
    for post_id, tags in post_tags.iteritems():
        Post.objects.get(site_id=site_id, wp_id=post_id).tags.add(*tags)

    # attach media attachments
    for post_id, attachments in post_media_attachments.iteritems():
        Post.objects.get(site_id=site_id, wp_id=post_id).attachments.add(*attachments)


def sync_deleted_attachments(site_id, api_post):
    """
    get the list of Posts with post_type = attachment whose parent_id = this post_id
    get the corresponding list from WP API
    perform set difference
    delete extra local attachments if any
    """
    existing_IDs = set(Post.objects.filter(site_id=site_id,
                                           post_type="attachment",
                                           parent__icontains='"ID":{}'.format(api_post["ID"]))
                                   .values_list("wp_id", flat=True))

    # can't delete what we don't have
    if existing_IDs:

        api_IDs = set()

        # call the API again to the get the full list of attachment posts whose parent is this post's wp_id
        path = "sites/{}/posts/".format(site_id)
        params = {
            "type": "attachment",
            "parent_id": api_post["ID"],
            "fields": "ID",
            "number": 100
        }
        page = 1

        response = get(path, params)

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

            response = get(path, params)

            if not response.ok:
                logger.warning("Response NOT OK! status_code=%s\n%s", response.status_code, response.text)
                return

        # perform set difference
        to_remove = existing_IDs - api_IDs

        # purge the extras
        if to_remove:
            Post.objects.filter(site_id=site_id,
                                post_type="attachment",
                                parent__icontains='"ID":{}'.format(api_post["ID"]),
                                wp_id__in=list(to_remove)).delete()


# ------- helpers to update existing objects ---------- #

def int_or_None(value):
    if value:
        try:
            return int(value)
        except ValueError:
            return None
    return None


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


def update_existing_category(existing_category, api_category):
    update_existing_obj(fields_mapping["category"], existing_category, api_category)


def update_existing_tag(existing_tag, api_tag):
    update_existing_obj(fields_mapping["tag"], existing_tag, api_tag)


def update_existing_author(existing_author, api_author):
    update_existing_obj(fields_mapping["author"], existing_author, api_author)


def update_existing_media(existing_media, api_media):
    update_existing_obj(fields_mapping["media"], existing_media, api_media)


def update_existing_obj(fields, existing_obj, api_data):
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


def api_object_data(type, api_data):
    data = {}

    for field in fields_mapping[type]:
        if len(field) > 2 and callable(field[2]):
            data[field[0]] = field[2](api_data.get(field[1]))
        else:
            data[field[0]] = api_data.get(field[1])

    return data
