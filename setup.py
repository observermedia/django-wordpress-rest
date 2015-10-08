import codecs

from os import path
from setuptools import find_packages, setup


def read(*parts):
    filename = path.join(path.dirname(__file__), *parts)
    with codecs.open(filename, encoding="utf-8") as fp:
        return fp.read()


setup(
    author="Observer Media",
    author_email="jsternberg@observer.com",
    description="Sync a WordPress site to Django via the WordPress.com REST API",
    name="django-wordpress-rest",
    long_description=read("README.rst"),
    version="0.1.3",
    url="https://github.com/observermedia/django-wordpress-rest",
    license="MIT",
    keywords='django wordpress wordpress.com REST API',
    packages=find_packages(),
    package_data={
        "django-wordpress-rest": []
    },
    test_suite="runtests.runtests",
    tests_require=[
        "mock>=1.3.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    install_requires=[
        "Django>=1.7.9",
        "django-after-response==0.2.1",
        "jsonfield>=1.0.3",
        "python-dateutil>=2.4.2",
        "requests>=2.7.0",
        "six>=1.9.0"
    ],
    zip_safe=False
)
