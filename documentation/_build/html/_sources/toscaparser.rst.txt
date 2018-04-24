Working with OpenStack's TOSCA-Parser
=====================================

We rely on the open-source, Apache-2.0 licensed TOSCA-Parser by OpenStack for
the initial mapping of TOSCA compliant ADTs into memory. Submitter engine adaptors
should be designed with ToscaTemplate objects in mind. Adaptors are expected to
use the methods provided by TOSCA-Parser in order to facilitate the extraction
of relevant data from an ADT.

Below you can find methods which were useful in the design of the first adaptor
which was implemented alongside the submitter engine. See also the source code
for this adaptor <component_submitter.adaptors.docker_adaptor>.

Useful links:

* https://wiki.openstack.org/wiki/TOSCA-Parser
* https://github.com/openstack/tosca-parser
* https://launchpad.net/tosca-parser

Passing a ToscaTemplate Object
==============================

.. code-block :: python

  toscaparser.tosca_template import ToscaTemplate

  MyAdaptor.translate(ToscaTemplate( <path_to_tosca.yaml> ))

The translate method of an adaptor class should accept as an argument a ToscaTemplate
object. The ToscaTemplate object is essentially a graph of the ADT which has been
submitted to MiCADO, with **most** of its links resolved. ToscaTemplate objects offer
various methods to facilitate the extraction of relevant data from the template.

*********************************
ToscaTemplate.\ **nodetemplates**
*********************************
Return a list of NodeTemplate objects.

NodeTemplate.\ **entity_tpl**
-----------------------------
  Return the raw representation of the node template as ``dict``

NodeTemplate.\ **get_properties()**
-----------------------------------
  Return a key:value dictionary of the properties of the node

  * key: ``str`` (name of property)
  * value: ``Property object``

      Property.\ **value**
        Return the value of the property

      Property.\ **default**
        Return the default value of the property

      Property.\ **required**
        Return true if the property is required

NodeTemplate.\ **get_property_value(**\ *name*\ **)**
-----------------------------------------------------
  Return the value of the named property. The *name* argument is a string.

  .. note::

    This may return a `<toscaparser.GetInput>` object
    which can be resolved using GetInput.result()

    Usage:
      >>> NodeTemplate.get_property_value(<name>).result()

NodeTemplate.\ **name**
-----------------------
  Return the name of the node

NodeTemplate.\ **related**
--------------------------
  Return a key:value dictionary of related nodes and their relationships

  * key: ``NodeTemplate object`` (the related node)
  * value: ``RelationshipType object``

    RelationshipType.\ **type**
      Return the type of relationship

NodeTemplate.\ **requirements**
-------------------------------
  Return a **list** of the raw representations of requirements as ``dict``

NodeTemplate.\ **type**
-----------------------
  Return the node type of the node

NodeTemplate.\ **type_definition**
----------------------------------
  Return the definition of the node type for this node

    NodeType.\ **defs**
      Return the raw representation of the definition as ``dict``

*************************************
ToscaTemplate.\ **repositories**
*************************************
Return a list of Repository objects.

Repository.\ **name**
------------------------
  Return the name of the repository

Repository.\ **reposit**
------------------------
  Return the path to the repository

*************************************
ToscaTemplate.\ **topology_template**
*************************************
Return a TopologyTemplate object.

TopologyTemplate.\ **custom_defs**
----------------------------------
  Return the raw representation of all associated custom TOSCA definitions as ``dict``

***********************
ToscaTemplate.\ **tpl**
***********************
Return the raw representation of the entire TOSCA topology as ``dict``
