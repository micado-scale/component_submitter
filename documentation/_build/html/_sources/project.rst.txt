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

 - __init__()
 - translate()
 - execute()
 - update()
 - undeploy()
 - cleanup()

Init
----
This is the __init__ method, it can take 1 or 2 parameter, the id that is mandatory,
and the template which is a TOSCA Parser object, that would state it them for the whole
object.

Translate
----------

This method should create a configuration file for your external component,
and store it in the files/output_configs directory located in the package where all the configuration file produced by the
different other Adaptors are. This configuration file should be named after an ID.


Execute
--------

This method should execute the wanted commands for the wanted component.

Update
------

This method should take the template that would have been re-instantiated by the engine,
retranslate it and put it as a tmp file, then do a diff of both files (the already launch one and the tmp).
If there's a difference between both file (use the filecmp.cmp(old_file, tmp_file)) then move the tmp file to
the old_file, and launch the execute method.
If there's no difference, then just delete the tmp file.

Undeploy
--------

This method undeploy the component.

Cleanup
-------

This method remove all the files produced which was required for the execution of
this application, which should be located under files/output_configs.

Utils
---------

We do give access to utils method listed bellow:
  - dump_order_yaml: that dump in order into a yaml file

for more information go to the utils method to see how to use those methods.


Tosca-parser object
-------------------

.. toctree::
    :maxdepth: 1

    toscaparser

Also see the Docker Adaptor for examples. For any help contact: g.gesmier@westminster.ac.uk
