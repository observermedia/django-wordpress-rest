django-wordpress-rest
=====================


.. image:: https://img.shields.io/badge/django--wordpress--rest-0.1.3-brightgreen.svg
    :target:  https://pypi.python.org/pypi/django-wordpress-rest/

.. image:: https://img.shields.io/badge/license-MIT-blue.svg
    :target:  https://pypi.python.org/pypi/django-wordpress-rest/

.. image:: https://circleci.com/gh/observermedia/django-wordpress-rest/tree/master.svg?style=shield&circle-token=d6ff8ea2fbb65de69536e1bacf6ce27fb95a533e
    :target: https://circleci.com/gh/observermedia/django-wordpress-rest/tree/master

.. image:: https://readthedocs.org/projects/django-wordpress-rest/badge/?badge=latest
    :target: http://django-wordpress-rest.readthedocs.org/en/latest/
    :alt: Documentation Status


Welcome to django-wordpress-rest!


Summary
-------

Django-wordpress-rest is a Django application that syncs content from a WordPress.com site to a Django site.

This is done using the `WordPress.com REST API <https://developer.wordpress.com/docs/api/>`_.
A separate copy of the content data is stored on the Django side, which allows for loose coupling and extensability.

Full documentation is available on `Read The Docs <http://django-wordpress-rest.readthedocs.org/>`_.


Quickstart
----------

Install the module:

::

    pip install django-wordpress-rest


Add ``"wordpress"`` to your ``INSTALLED_APPS`` setting:

::

    INSTALLED_APPS = (
        # ...
        "wordpress",
        # ...
    )


Create the database tables that will persist the sync'd WordPress content:

::

    $ python manage.py migrate


Sync WordPress content using the management command. The ``<site_id>`` can be found using the `/me/sites WordPress API call <https://developer.wordpress.com/docs/api/1.1/get/me/sites/>`_. This is useful for periodically updating the content with cron.

::

    $ python manage.py load_wp_api <site_id>


Authentication
--------------

If you'd like to synchronize private content, create an OAuth2 access token using the instructions provided by WordPress:
https://developer.wordpress.com/docs/oauth2/

Add this token to your Django ``settings.py`` file. Use an environment variable to keep things secure:

::

    WP_API_AUTH_TOKEN = os.getenv("WP_API_AUTH_TOKEN")


Load Options
------------

Bring the site content up to date:

::

    # first run gets everything
    $ python manage.py load_wp_api <site_id>

    # second run gets content modified since previous run
    $ python manage.py load_wp_api <site_id>


Do a full sweep of the site content, inserting and updating as needed:

::

    # first run gets everything
    $ python manage.py load_wp_api <site_id>

    # second run gets/updates all content again
    $ python manage.py load_wp_api <site_id> --full


Load everything modified after a given date:

::

    $ python manage.py load_wp_api <site_id> --modified_after=2015-01-01


Just load posts, not pages, attachments, or reference data:

::

    $ python manage.py load_wp_api <site_id> --type=post


Load posts with a specific status (note this requires authentication):

::

    $ python manage.py load_wp_api <site_id> --status=draft


Purge local content before loading -- careful!

::

    $ python manage.py load_wp_api <site_id> --purge --full



Webhook
-------

If you'd like to use the webhook to sync a post immediately after it's updated, include the ``urls`` into your project's ``urls.py``, like so:

::

    from django.conf.urls import include

    urlpatterns = [
        url(r'^wordpress/', include('wordpress.urls'))
    ]


Add ``"after_response"`` to your ``INSTALLED_APPS`` setting (this allows asynchronous processing):

::

    INSTALLED_APPS = (
        # ...
        "after_response",
        "wordpress",
        # ...
    )


The webhook looks for your ``<site_id>`` in Django settings. So add this your ``settings.py``, and use an environment variable to keep things secure:

::

    WP_API_SITE_ID = os.getenv("WP_API_SITE_ID")


Finally from your WordPress.com site, submit a POST request with an ``ID`` data element in the body to trigger a sync of a single post. Note this should be the WordPress Post ID, not the Django one!

::

    $ curl -X POST --data "ID=123456" http://mydjangosite.com/wordpress/load_post



Running the Tests
-----------------

::

    $ pip install detox
    $ detox

