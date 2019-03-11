#!/usr/bin/env python
# coding=utf-8
import setuptools

setuptools.setup(
    name='aws-s3-glacier-restore',
    version='0.0.2',
    scripts=['aws-s3-glacier-restore'],
    author="Marko Baštovanović",
    author_email="marko.bast@gmail.com",
    description="Utility script to restore files on AWS S3 that have GLACIER "
                "storage class",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/marko-bast/aws-s3-glacier-restore",
    packages=setuptools.find_packages(),
    classifiers=[
        # 'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.7',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=['requests[security]>=2.18.3',
                      'six',
                      'boto3>=1.9']
)
