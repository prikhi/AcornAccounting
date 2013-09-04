.. _Specification Explanation:

==============================
Specification Explanation
==============================

Use Cases
==========

Use Cases describe interactions with the application by multiple roles of
users(accountants, communards, administrators, budgeters, etc.). They are also
known as "User Stories".

In general, they describe "who uses this site" and "why?".

Use Cases include diagrams and short narratives. Each Use Case will direct the
reader to any relevant Screens.

Use Case Diagrams
==================

Diagrams will be used to display the use case associated with each role. Each
role is represented by a figure, known as an Actor. Use Cases are enclosed
in circles and similar Use Cases are grouped together by rectangles.

Lines between an Actor and a Use Case indicates the actor utilizes the Use
Case. A hollow arrow between two actors means that the actor is based off of
the actor the arrow is pointed at, and inherits the other actors Use Cases. A
dashed arrow from one Use Case to another indicates the source Use Case depends
on or includes the Use Case being pointed at.


.. uml::
    :includegraphics: scale=.5

    left to right direction
    :Sample Actor: as act
    :Similar Actor: as act2
    act2 --|> act : extends
    :Different Actor: as act3

    rectangle "Some Grouping" {
        act -- (A Use Case)
        (A shared Use Case) as SUC
        act3 -- SUC
        act2 -- SUC
        act -- (I depend on another Use Case)
        (I depend on another Use Case) .> (A Use Case) : depends on
    }

.. _Conditions Explanation:

Screens and Conditions
=======================

A 'screen' is a specific page in the application.

Every screen in the specification contains a description of the following
Conditions:

* Entry Conditions - The action required to get to the screen
* Initial Conditions - The initial appearance and state of the screen
* Intermediate Conditions - All possible changes in the screen before the
  screen is replaced
* Final Conditions - All possible exits from the page and any related
  behind-the-scenes actions

Each screen will contain a :term:`wireframe`, depicting the page's layout. The
wireframe is not meant to depict the final appearance of a page, but acts as a
rough guide or prototype.

Activity Diagrams
==================

Complex Screens may include flowcharts or activity diagrams. To read these,
start at the top circle, following the arrows until you reach diamonds, which
represent decisions. Continue down only one path from a decision point. Repeat
until you reach the end, represented by the bottom circle.

.. uml::
    :includegraphics: scale=.6

    (*) --> Start Here
    -> Then Do This
    if "Stop reading?" then
        -->[yes] "Bye."
        -> (*)
    else
        ->[no] "Then Read This"
        --> "Then Do This"
