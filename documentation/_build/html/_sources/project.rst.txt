MiCADO Project
==============
.. image:: _static/Cola_colored_kl.jpg
   :scale: 50 %
   :alt: alternate text
   :align: right

Here you can find all the useful information on the MiCADO and COLA project:

http://project-cola.eu/

Here you can find the github accounts:
  - for the whole project:
    https://github.com/micado-scale

  - for TOSCA topologies and custom types:
    https://github.com/COLAProject/COLARepo
    (This is the current repository but might change in the future)

  - for the submitter:
    https://github.com/micado-scale/component_submitter

How to create your Adaptor:
===========================

At the moment we have the abstract base Adaptor that is describing three abstract
sub methods:

 - translate()
 - execute()
 - undeploy()
 - cleanup()

Translate
----------

This method should create a configuration file for your external component,
and store it in the files/output_configs directory located in the package where all the configuration file produced by the
different other Adaptors are. This configuration file should be named after an ID that can be generated with the
generator we provide, or another one you'd like. This method return this ID.


Execute
--------

This method should execute the wanted commands from the wanted Adaptor. It takes as
parameter the ID link to the wanted component to be executed.

Undeploy
--------

This method takes as parameter the ID of the wanted component and unbuild it.

Cleanup
-------

This method takes the ID of the wanted component and remove all the files produced which was required for the execution of
this application, which should be located under files/output_configs.

Utils
---------

We do give access to utils method listed bellow:
  - id_generator: that creates the random ID.
  - dump_order_yaml: that dump in order into a yaml file

for more information go to the utils method to see how to use those methods.


Tosca-parser object
-------------------

.. toctree::
    :maxdepth: 1

    toscaparser

Also see the Docker Adaptor for examples. For any help contact: g.gesmier@westminster.ac.uk
