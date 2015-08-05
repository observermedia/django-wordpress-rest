import codecs

from os import path
from setuptools import find_packages, setup


def read(*parts):
    filename = path.join(path.dirname(__file__), *parts)
    with codecs.open(filename, encoding="utf-8") as fp:
        return fp.read()


setup(
    author="",
    author_email="",
    description="",
    name="django-wordpress-rest",
    long_description=read("README.rst"),
    version="0.1",
    url="http://django-wordpress-rest.rtfd.org/",
    license="MIT",
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
        "requests>=2.7.0",
        "jsonfield>=1.0.3",
        "python-dateutil>=2.4.2"
    ],
    zip_safe=False
)
