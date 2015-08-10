# django-wordpress-rest



## Summary

Django-wordpress-rest is a Django application that syncs content from a WordPress.com site to a Django site.
This is done using the WordPress.com REST API: https://developer.wordpress.com/docs/api/.
A separate copy of the content data is stored on the Django side, which allows for loose coupling and extensability.


## Authentication

If you'd like to synchronize private content, create an OAuth2 access token using the instructions provided by WordPress:
https://developer.wordpress.com/docs/oauth2/

Add this token to your Django `settings.py` file. Use an environment variable to keep things secure:

    WP_API_AUTH_TOKEN = os.getenv("WP_API_AUTH_TOKEN")


## Quickstart

Install the module:

    pip install django-wordpress-rest

Add `"wordpress"` to your `INSTALLED_APPS` setting:

    INSTALLED_APPS = (
        # ...
        "wordpress",
        # ...
    )


## Load Options

Bring the site content up to date:

    $ python manage.py load_wp_api <site_id>  # first run gets everything
    $ python manage.py load_wp_api <site_id>  # second run gets content modified since previous run

Do a full sweep of the site content, inserting and updating as needed:

    $ python manage.py load_wp_api <site_id>  # first run gets everything
    $ python manage.py load_wp_api <site_id> --full  # second run gets/updates all content again

Load everything modified after a given date:

    $ python manage.py load_wp_api <site_id> --modified_after=2015-01-01

Just load posts, not pages, attachments, or reference data:

    $ python manage.py load_wp_api <site_id> --type=post

Purge local content before loading -- careful!

    $ python manage.py load_wp_api <site_id> --purge --full  # second run gets/updates all content again


## Webhook

If you'd like to use the webhook to sync a post immediately after it's updated, include the `urls` into your project's `urls.py`, like so:

    from django.conf.urls import include

    urlpatterns = [
        url(r'^wordpress/', include('wordpress.urls'))
    ]


Add `"after_response"` to your `INSTALLED_APPS` setting (this allows asynchronous processing):

    INSTALLED_APPS = (
        # ...
        "after_response",
        "wordpress",
        # ...
    )

Then from your WordPress.com site, submit a POST request with an `ID` data element in the body to trigger a sync of a single post. Note this should be the WordPress Post ID, not the Djano one!

    $ curl -X POST --data "ID=123456" http://mydjangosite.com/wordpress/load_post
    

