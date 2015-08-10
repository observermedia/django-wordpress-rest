from __future__ import unicode_literals

import collections

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from jsonfield import JSONField


class DateTracking(models.Model):
    """
    An abstract model that adds tracking fields for creation and modification dates
    """
    created_date = models.DateTimeField(blank=False, null=False, auto_now_add=True)
    updated_date = models.DateTimeField(blank=False, null=False, auto_now=True)

    class Meta:
        abstract = True


class WordPressIDs(models.Model):
    """
    An abstract model that adds basic WordPress API IDs
    """
    site_id = models.IntegerField(blank=False, null=False,
                                  help_text=_("The site ID on Wordpress.com"))
    wp_id = models.IntegerField(blank=False, null=False,
                                help_text=_("The object ID on Wordpress.com"))

    class Meta:
        abstract = True
        unique_together = ("wp_id", "site_id")


class Category(WordPressIDs, DateTracking, models.Model):
    name = models.CharField(max_length=1000, blank=False, null=False)
    slug = models.SlugField(max_length=1000, blank=False, null=False, unique=True)
    description = models.TextField(blank=True, null=False)
    post_count = models.IntegerField(blank=False, null=False)
    parent_wp_id = models.IntegerField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "categories"

    def __unicode__(self):
        return "{}: {}".format(self.pk, self.name)


class Tag(WordPressIDs, DateTracking, models.Model):
    name = models.CharField(max_length=1000, blank=False, null=False)
    slug = models.SlugField(max_length=1000, blank=False, null=False, unique=True)
    description = models.TextField(blank=True, null=False)
    post_count = models.IntegerField(blank=False, null=False)

    def get_absolute_url(self):
        return reverse('tag', kwargs={"tag_slug": self.slug})

    def __unicode__(self):
        return "{}: {}".format(self.pk, self.name)


class Author(WordPressIDs, DateTracking, models.Model):
    login = models.CharField(max_length=255, blank=False, null=False)
    email = models.CharField(max_length=1000, blank=False, null=False)
    name = models.CharField(max_length=1000, blank=False, null=False)
    nice_name = models.CharField(max_length=1000, blank=False, null=False)
    url = models.CharField(max_length=1000, blank=False, null=False)
    avatar_url = models.CharField(max_length=1000, blank=False, null=False)
    profile_url = models.CharField(max_length=1000, blank=False, null=False)

    def __unicode__(self):
        return self.name


class Media(WordPressIDs, DateTracking, models.Model):
    url = models.CharField(max_length=1000, blank=False, null=False,
                           help_text=_("The full URL to the media file"))
    guid = models.CharField(max_length=1000, blank=True, null=True, db_index=True)
    uploaded_date = models.DateTimeField(blank=False, null=False)
    post_ID = models.IntegerField(blank=True, null=True,
                                  help_text=_("ID of the post this media is attached to"))
    file_name = models.CharField(max_length=500, blank=True, null=True)
    file_extension = models.CharField(max_length=10, blank=True, null=True)
    mime_type = models.CharField(max_length=200, blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    caption = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    alt = models.TextField(blank=True, null=True)
    exif = JSONField(load_kwargs={'object_pairs_hook': collections.OrderedDict})

    def __unicode__(self):
        return "{}: {}".format(self.pk, self.url)


class Post(WordPressIDs, DateTracking, models.Model):
    author = models.ForeignKey("Author", blank=True, null=True)
    post_date = models.DateTimeField(blank=False, null=False)
    modified = models.DateTimeField(blank=False, null=False,
                                    help_text=_("The post's most recent update time"))
    title = models.TextField(blank=True, null=True)
    url = models.CharField(max_length=1000, blank=False, null=False,
                           help_text=_("The full permalink URL to the post"))
    short_url = models.CharField(max_length=1000, blank=False, null=False,
                                 help_text=_("The wp.me short URL"))
    content = models.TextField(blank=True, null=True)
    excerpt = models.TextField(blank=True, null=True)
    slug = models.SlugField(max_length=200, blank=True, null=True, db_index=True)
    guid = models.CharField(max_length=1000, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=20, blank=True, null=True)
    sticky = models.BooleanField(default=False,
                                 help_text=_("Show this post at the top of the chronological list, even if old."))
    password = models.CharField(max_length=1000, blank=True, null=True)
    parent = JSONField(load_kwargs={'object_pairs_hook': collections.OrderedDict}, blank=True, null=True)
    post_type = models.CharField(max_length=20, blank=True, null=True)
    likes_enabled = models.NullBooleanField()
    sharing_enabled = models.NullBooleanField()
    like_count = models.IntegerField(blank=True, null=True)
    global_ID = models.CharField(max_length=1000)
    featured_image = models.CharField(max_length=1000)
    post_thumbnail = JSONField(blank=True, null=True, load_kwargs={'object_pairs_hook': collections.OrderedDict})
    attachments = models.ManyToManyField("Media", blank=True)
    format = models.CharField(max_length=20)
    menu_order = models.IntegerField(blank=True, null=True)
    tags = models.ManyToManyField("Tag", blank=True)
    categories = models.ManyToManyField("Category", blank=True)
    metadata = JSONField(load_kwargs={'object_pairs_hook': collections.OrderedDict})

    def __unicode__(self):
        return "{}: {}".format(self.pk, self.slug)
