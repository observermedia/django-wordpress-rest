# django-wordpress-rest


## Quickstart

Install the module:

    pip install django-wordpress-rest

Add `wordpress` to your `INSTALLED_APPS` setting:

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

Then sumbit a POST request with an `ID` data element in the body to trigger a sync of a single post. Note this should be the WordPress Post ID, not the Djano one!

    $ curl -X POST --data "ID=123456" http://mydjangosite.com/wordpress/load_post
    

