from __future__ import unicode_literals

import logging
import time

from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http.response import Http404, JsonResponse
import after_response

from wordpress.loading import WPAPILoader


logger = logging.getLogger(__name__)


@require_POST
@csrf_exempt
def load_post_webhook(request):
    """
    Webhook to insert/update a WordPress.com post on the local Django site.
    Call this after making changes to the post in WP Admin.
    The post is processed asynchronously so that a response can be returned to WordPress.com immediately.

    :param request: Should contain the WordPress post ID, named "ID", in POST form data
    :return: JsonResponse indicated the refresh is in progress.
    """
    try:
        wp_post_id = int(request.POST["ID"])
    except:
        raise Http404("Post does not exist")

    # load this asynchronously so that the webhook gets a fast response
    load_post.after_response(wp_post_id)
    return JsonResponse({"status": "Refreshing wp_post_id: {}".format(wp_post_id)})


@after_response.enable
def load_post(wp_post_id):
    """
    Called from load_post_webhook.
    This builds a generic WPAPILoader and uses its load_post() to insert/update content for the post.

    :param wp_post_id: the WordPress post ID to load
    :return: None
    """

    # wait a bit to give WordPress REST API a chance to catch up
    time.sleep(1)

    loader = WPAPILoader()
    post = loader.load_post(wp_post_id)

    if post:
        logger.info("Successfully loaded post wp_post_id=%s, pk=%s", wp_post_id, post.pk)
    else:
        logger.warning("Error loading post wp_post_id=%s", wp_post_id)
