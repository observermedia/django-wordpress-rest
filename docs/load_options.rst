Load Options
============

The ``load_wp_api`` management command supports several extended options via command-line arguments.

Default (For Periodic Syncs)
----------------------------

The default, without any args except ``site_id``, is designed to bring the site content up to date when it runs. It uses the modified dates of posts to load only "new" content.

For example:

::

    # first run gets everything
    $ python manage.py load_wp_api <site_id>

    # second run gets content modified since previous run
    $ python manage.py load_wp_api <site_id>


Full
----

To do a full sweep of the site content, inserting and updating as needed, use the ``--full`` argument:

::

    # first run gets everything
    $ python manage.py load_wp_api <site_id>

    # second run gets/updates all content again
    $ python manage.py load_wp_api <site_id> --full


Modified Date
-------------

You can also load everything modified after a given date with ``--modified_after`` argument:

::

    $ python manage.py load_wp_api <site_id> --modified_after=2015-01-01


Content Type
------------

To load only a single type of content, such as posts, pages, attachments, or reference data (authors, tags, categories, media):

::

    $ python manage.py load_wp_api <site_id> --type=post
    $ python manage.py load_wp_api <site_id> --type=page
    $ python manage.py load_wp_api <site_id> --type=attachment
    $ python manage.py load_wp_api <site_id> --type=ref_data


Post Status
------------

To load posts with a specific post status, or any status, use the ``--status`` argument.

This takes a single status, which can be any of: "publish", "private", "draft", "pending", "future", and "trash", or simply "any". Defaults to "publish".

Note that non-public statuses generally require authentication to your WordPress site.

::

    $ python manage.py load_wp_api <site_id> --status=publish
    $ python manage.py load_wp_api <site_id> --status=private
    $ python manage.py load_wp_api <site_id> --status=draft
    $ python manage.py load_wp_api <site_id> --status=any


Purge and Reload
----------------

Purge local content before loading -- *careful*, this is destructive!

::

    $ python manage.py load_wp_api <site_id> --purge --full


