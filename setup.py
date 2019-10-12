import setuptools
import os


# with open("README.md", "r") as fh:
#     long_description = fh.read()


setuptools.setup(
    name="nngrid",
    version="0.0.1",
    author="Nikita Krutoy",
    author_email="nikitakrutoy@gmail.com",
    description="A small example package",
    long_description="long_description",
    long_description_content_type="text/markdown",
    url="https://github.com/nikitakrutoy/nngrid",
    packages=setuptools.find_packages(),
    package_data={
        "nngrid": ["db.sqlite"]
    },
    install_requires=[
        "flask",
        "celery",
        "visdom",
        "redis",
        "click",
        "virtualenv",
        "gitpython",
        "torch",
        "filelock",
        "tqdm",
        "psycopg2-binary",
        "python-redis-lock",
    ],
    entry_points={
        'console_scripts': [
            'nngrid=scripts.cli:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3.6 ",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
    ],
)