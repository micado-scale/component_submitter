MiCADO Submitter Tutorial
=========================

This Tutorial will explain how to use the MiCADO Submitter to launch
an application described by a TOSCA templates on the MiCADO infrastructure.


REST API
---------

You can launch the REST API by calling the following command:

.. code-block:: bash
    :linenos:

    python api.py


To launch an application you can use the curl command line:

.. code-block:: bash
    :linenos:

    curl -d "input=[Path to TOSCA Template]" -X POST http://[IP]:[Port]/engine/

To launch an application with no default value for the inputs use the curl command line:

.. code-block:: bash
    :linenos:

    curl -d "input=[Path to TOSCA Template]" -d "params={Input1: value a, Input2: value b}" -X POST http://[IP]:[Port]/engine/

To undeploy a wanted application you need to feed it the id:

.. code-block:: bash
    :linenos:

    curl -d "id_app=[ID]" -X POST http://[IP]:[Port]/undeploy/

To get the ids of the application deploy:

.. code-block:: bash
    :linenos:

    curl -X GET http://[IP]:[Port]/list_app/

Python Interpreter
-------------------

To use the Python Interpreter, you will want to first import the submitter_engine p
package:

.. code-block:: python
    :linenos:

    from submitter_engine import SubmitterEngine

Once you imported this you can create a submitter engine object like so:

.. code-block:: python
    :linenos:

    s = SubmitterEngine()

This will initialize all the component needed.

To launch your application on the MiCADO infrastructure you will need to execute this command:

.. code-block:: python
    :linenos:

    s.launch(path_to_file=[path to TOSCA Template])

If you don't want to use the default value of the inputs section you can pass *parsed_params*
which will be a dictionary containing as key the input you want to modify and as value for the key
the actual value you want to use as input.

.. code-block:: python
    :linenos:

    s.launch(path_to_file=[path to TOSCA Template], parsed_params={Input1: value a, Input2: value b})

If you wish to undeploy a certain application, you will need to execute this command.


.. code-block:: python
    :linenos:

    s.undeploy([ID of app wanted])
