MiCADO Project
==============

Here you can find all the useful information on the MiCADO and COLA project:

http://project-cola.eu/


How to create your Adaptor:
===========================

At the moment we have the abstract base Adaptor that is describing three abstract
sub methods:

 - translate()
 - execute()
 - unbuild()

Translate
----------

this method should create a configuration file for your external component,
and store it in a temporary directory where all the configuration file from the
different other Adaptors. It also create and return an ID that will be link to
this particular component.

Execute
--------

this method should execute the wanted commands from the wanted Adaptor. It takes as
parameter the ID link to the wanted component to be executed.

Unbuild
--------

this method takes as parameter the Id of the wanted component and unbuild it.


generator
---------

we do give access to a method that creates the random ID.
