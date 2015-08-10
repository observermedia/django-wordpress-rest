from __future__ import unicode_literals

from django.contrib import admin
from django.db import models
from django import forms

from wordpress import models as wp_models


class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'post_count', 'wp_id', 'slug', 'created_date', 'updated_date')
    ordering = ('name',)
    search_fields = ('id', 'name', 'wp_id', 'slug', 'description',)

    # wider fields to show more of the entity names
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size': '100'})},
    }

    def view_on_site(self, obj):
        return obj.get_absolute_url()

admin.site.register(wp_models.Tag, TagAdmin)


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'post_count', 'wp_id', 'slug', 'created_date', 'updated_date')
    ordering = ('name',)
    search_fields = ('id', 'name', 'wp_id', 'slug', 'description',)

    # wider fields to show more of the entity names
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size': '100'})},
    }

admin.site.register(wp_models.Category, CategoryAdmin)


class AuthorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'login', 'email', 'url', 'created_date', 'updated_date')
    ordering = ('id',)
    search_fields = ('id', 'name', 'login', 'email', 'url',)

    # wider fields to show more of the entity names
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size': '100'})},
    }

    def view_on_site(self, obj):
        return obj.get_absolute_url()

admin.site.register(wp_models.Author, AuthorAdmin)


class MediaAdmin(admin.ModelAdmin):
    list_display = ('id', 'url', 'title', 'width', 'height', 'created_date', 'updated_date')
    ordering = ('id',)
    search_fields = ('id', 'url', 'title',)

    # wider fields to show more of the entity names
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size': '150'})},
    }

admin.site.register(wp_models.Media, MediaAdmin)


class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'wp_id', 'post_date', 'title', 'slug', 'post_type', 'status', 'author', 'created_date', 'updated_date')
    ordering = ('-post_date',)
    search_fields = ('id', 'wp_id', 'title', 'slug', 'author__name')
    list_filter = ('post_date', 'post_type', 'status', 'author')

    # wider fields to show more of the entity names
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size': '150'})},
    }

admin.site.register(wp_models.Post, PostAdmin)
