Webhook
=======

The webhook is designed to allow you to sync a post to Django immediatey after it's updated on the WordPress site.

This is helpful, for example, with corrections that need to be published as soon as possible. It also helps content authors preview their posts on the Django site more quickly.

urls.py
-------

If you'd like to use the webhook to sync a post immediately after it's updated, include the ``urls`` into your project's ``urls.py``, like so:

::

    from django.conf.urls import include

    urlpatterns = [
        url(r'^wordpress/', include('wordpress.urls'))
    ]


after_response library
----------------------


Add ``"after_response"`` to your ``INSTALLED_APPS`` setting (this allows asynchronous processing):

::

    INSTALLED_APPS = (
        # ...
        "after_response",
        "wordpress",
        # ...
    )


Django settings
---------------

The webhook looks for your ``<site_id>`` in Django settings. So add this your ``settings.py``, and use an environment variable to keep things secure:

::

    WP_API_SITE_ID = os.getenv("WP_API_SITE_ID")



WordPress save_post action
--------------------------

Finally from your WordPress.com site, submit a POST request with an ``ID`` data element in the body to trigger a sync of a single post. Note this should be the WordPress Post ID, not the Django one!

Something like this in your ``functions.php`` should work (note, how you implement this depends on your WordPress install):

.. code-block:: PHP

    <?php
    /**
     * Notify Django when saving a post
     * @param int $post_id
     * @return void
     */
    function django_webhook( $post_id ) {
        // don't do this for autosave
        if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
            return;
        }

        // if the post is live, or going live soon, notify Django that we created/updated it
        $post_status = get_post_status( $post_id );
        if ( in_array( $post_status, array("draft", "future", "publish"), true ) ) {
            $params = array(
                'ID' => $post_id,
            );
            wp_remote_post( "http://mydjangosite.com/wordpress/load_post",
                            array( 'method' => 'POST', 'body' => $params ) );
        }
    }
    add_action( 'save_post', 'django_webhook' );



Here's an example with curl for testing purposes:

.. code-block:: bash

    $ curl -X POST --data "ID=123456" http://mydjangosite.com/wordpress/load_post

