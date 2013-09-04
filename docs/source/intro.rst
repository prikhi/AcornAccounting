=============
Introduction
=============

The purpose of this Documentation is to define what this application does in
a simple language. If you have used `www.google.com <http://www.google.com>`_,
you should have enough knowledge to understand this document. If you are having
trouble, it's not because you lack technical experience but rather because the
author has failed to express themselves clearly.

The authors beg you to please inform us when you find any confusing or unclear
passages so they may be reviewed.

If Specifications and Documentation scare you, you may want to first read our
:ref:`Specification Explanation`.

Documentation Overview
-----------------------

This Document defines the AcornAccounting Application, and provides guides for
users and contributers.

The End-User experience is defined by the :ref:`Design Specifications`. The
:ref:`User Guide` will help new users become acquainted with interacting with
the application by providing an overview of all possible actions and effects.

Developers and Contributers should reference the :ref:`Development Standards`
and :ref:`Technical Specifications` Sections for information on Best Coding
Practices and the current public :term:`API`.

Program Overview
-----------------

AcornAccounting is an Open Source, Web-based, Double Entry Accounting System
for (Egalitarian) Communities.

Major Features
+++++++++++++++

AcornAccounting has these notable features:

* Trip Entry Form - Tripper-friendly entry form with Accountant approval
* People Tracking - Count the number of Intern/Visitor days, automatically pay
  monthly and yearly stipends
* Online Bank Statements - Download statements to make entry easy
* Open Source - Easily add custom reports or entry types

Goals
++++++

AcornAccounting strives to be both Accountant and Communard friendly.

Entry and Reporting should be streamlined for Accountants and the UI and
workflow should be accessible to Communards. Automation will be used to lighten
repetitive workloads for Accountants.

Non-accountants should feel comfortable checking their Account balances and
Project budgets.

Non-Goals
++++++++++

AcornAccounting does **not** try to be:

#. An international Accounting system(only English and USD is currently
   supported).
#. Customer Relationship Management Software
#. Enterprise Resource Planning Software
#. Payroll Accounting Software

Technology
+++++++++++

AcornAccounting is written in `Python`_, using the `Django`_ Web Framework. The
UI is built using the `Bootstrap`_ CSS and Javascript GUI Framework. Clientside
validation will be performed by custom Javascript and `Parsley.js
<http://parsleyjs.org/>`_.

`Django`_ contains many helper apps/plugins. Some apps we use include:

* `Cache Machine <https://github.com/jbalogh/django-cache-machine>`_ for
  caching querys and objects.
* `Djanjo-parsley <https://github.com/agiliq/django-parsley>`_ for integration
  with Parsley.js.
* `South <http://south.aeracode.org/>`_ to automate database
  changes/migrations.
* `MPTT <https://github.com/django-mptt/django-mptt>`_ for handling object
  hierarchies.

Version Control is handled with `Git`_. The automated deployment script uses
`Fabric`_.

Documentation and :term:`API` Specifications will be written in
`reStructuredText`_ for use with `Sphinx`_. UML diagrams will be generated from
the documentation using `plantUML`_.

.. _Bootstrap: http://getbootstrap.com/

.. _Django: https://www.djangoproject.com/

.. _Fabric: http://docs.fabfile.org/en/1.8/

.. _Git: http://gitscm.com/

.. _plantUML: http://plantuml.sourceforge.net/index.html

.. _Python: http://python.org/

.. _reStructuredText:
    http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html

.. _Sphinx: http://sphinx-doc.org/
