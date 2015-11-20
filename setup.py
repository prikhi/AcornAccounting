from setuptools import setup, find_packages


setup(
    name='AcornAccounting',
    version='0.11.2',
    author='Pavan Rikhi',
    author_email='pavan.rikhi@gmail.com',
    packages=find_packages(),
    license='LICENSE.txt',
    description='Accounting Software for Communities.',
    long_description=open('README.rst').read(),
    install_requires=[
        "Django >= 1.4",
        "django-cache-machine",
        "django-constance",
        "django-mptt",
        "django-parsley",
        "python-dateutil",
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Intended Audience :: Financial and Insurance Industry',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Topic :: Office/Business :: Financial :: Accounting'
    ],
    keywords="accounting django egalitarian community",
    include_package_data=True,
    zip_safe=False,
)
