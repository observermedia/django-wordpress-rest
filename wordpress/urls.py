from __future__ import unicode_literals

from django.conf.urls import patterns, url


urlpatterns = patterns(
    "wordpress.views",
    url(r"^load_post$", "load_post_webhook", name="wp_rest_load_post_webhook"),
)
