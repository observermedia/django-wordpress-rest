from __future__ import unicode_literals

import logging
from optparse import make_option

from django.core.management.base import BaseCommand
from dateutil import parser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    args = '<site_id>'
    help = "loads data from the Wordpress.com API, for the given site_id"

    option_list = BaseCommand.option_list + (
        make_option('--purge',
                    action='store_true',
                    dest='purge',
                    default=False,
                    help='Purge data locally first.'),
        make_option('--full',
                    action='store_true',
                    dest='full',
                    default=False,
                    help='Full sweep of posts (update and insert as needed).'),
        make_option('--modified_after',
                    type='string',
                    dest='modified_after',
                    default=None,
                    help='Load posts modified after this date (iso format).'),
        make_option('--type',
                    type='choice',
                    choices=['all', 'ref_data', 'attachment', 'post', 'page'],
                    dest='type',
                    default='all',
                    help="The type of posts or information to update."),
        make_option('--status',
                    type='choice',
                    choices=['publish', 'private', 'draft', 'pending', 'future', 'trash', 'any'],
                    dest='status',
                    default='publish',
                    help="Update posts with a specific status, or 'any' status."),
    )

    def handle(self, *args, **options):
        from wordpress import loading

        site_id = args[0]

        purge_first = options.get("purge")
        full = options.get("full")

        modified_after = options.get("modified_after")
        if modified_after:
            # string to datetime
            modified_after = parser.parse(modified_after)

        type = options.get("type")
        status = options.get("status")

        loader = loading.WPAPILoader(site_id=site_id)
        loader.load_site(purge_first=purge_first,
                         full=full,
                         modified_after=modified_after,
                         type=type,
                         status=status)
