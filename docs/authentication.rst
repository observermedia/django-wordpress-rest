Authentication
==============

If you'd like to synchronize private content (such as drafts) from your WordPress site to Django, create an OAuth2 access token using the instructions provided by WordPress:
https://developer.wordpress.com/docs/oauth2/

Add this token to your Django ``settings.py`` file. Use an environment variable to keep things secure:

::

    WP_API_AUTH_TOKEN = os.getenv("WP_API_AUTH_TOKEN")

