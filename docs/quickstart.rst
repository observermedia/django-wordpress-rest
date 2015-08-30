Quickstart
==========

Getting started with django-wordpress-rest is simple. Follow these quick steps to start.


Installation
------------

Install the module via pip:

::

    pip install django-wordpress-rest



Django settings
---------------

Add ``"wordpress"`` to your ``INSTALLED_APPS`` Django setting:

::

    INSTALLED_APPS = (
        # ...
        "wordpress",
        # ...
    )


Database migration
------------------

Create the database tables that will persist the sync'd WordPress content:

::

    $ python manage.py migrate



Sync your WordPress site
------------------------

Sync your WordPress content using the management command. The ``<site_id>`` can be found using the `/me/sites WordPress API call <https://developer.wordpress.com/docs/api/1.1/get/me/sites/>`_.

This is useful for periodically updating the content with cron. See :doc:`load_options` for more.

::

    $ python manage.py load_wp_api <site_id>
