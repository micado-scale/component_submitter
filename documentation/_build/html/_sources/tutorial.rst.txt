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

The url path to deploy the application is this one:
.. code-block:: bash
    :linenos:

    http://[IP]:[PORT]/v1.0/app/launch/

To launch an application from an url you can use one of the following curl command line:

.. code-block:: bash
    :linenos:

    curl -d input="[url to TOSCA Template]" -X POST http://[IP]:[Port]/v1.0/app/launch/

    curl -d input="[url to TOSCA Template]" -d id=[ID] -X POST http://[IP]:[Port]/v1.0/app/launch/

    curl -d input="[url to TOSCA Template]" -d params='{"Input1": "value a", "Input2": "value b"}' -X POST http://[IP]:[Port]/v1.0/app/launch/

    curl -d input="[url to TOSCA Template]" -d id=[SOMEID] -d params='{"Input1": "value a", "Input2": "value b"}' -X POST http://[IP]:[Port]/v1.0/app/launch/

To launch an application from a file that you pass to the api you can use one of the following curl command line:

.. code-block:: bash
    :linenos:

    curl -F file=@[Path to the File] -X POST http://[IP]:[Port]/v1.0/app/launch/

    curl -F file=@[Path to the File] -F params='{"Input1": "value a", "Input2": "value b"}' -X POST http://[IP]:[Port]/v1.0/app/launch/

    curl -F file=@[Path to the File] -F id=[SOMEID] -F params='{"Input1": "value a", "Input2": "value b"}' -X POST http://[IP]:[Port]/v1.0/app/launch/

    curl -F file=@[Path to the File] -F id=[SOMEID]  -X POST http://[IP]:[Port]/v1.0/app/launch/


The url path to update the application is this one:
.. code-block:: bash
    :linenos:


     http://[IP]:[PORT]/v1.0/app/update/[ID_APP]


To update from an url a wanted application you can use one of this following curl command:

.. code-block:: bash
    :linenos:

    curl -d input="[url to TOSCA template]" -d params='{"Input1": "value a", "Input2": "value b"}' -X PUT http://[IP]:[Port]/v1.0/app/udpate/[ID_APP]

    curl -d input="[url to TOSCA template]" -X PUT http://[IP]:[Port]/v1.0/app/udpate/[ID_APP]


To update from a file a wanted application you can use one of this following curl command:

.. code-block:: bash
    :linenos:

    curl -F file=@"[Path to the file]" -d params='{"Input1": "value a", "Input2": "value b"}' -X PUT http://[IP]:[Port]/v1.0/app/udpate/[ID_APP]

    curl -F file=@"[Path to the file]" -X PUT http://[IP]:[Port]/v1.0/app/udpate/[ID_APP]


To undeploy a wanted application you need to feed it the id:

.. code-block:: bash
    :linenos:

    curl -X DELETE http://[IP]:[Port]/v1.0/app/undeploy/[ID_APP]


To query on application's adaptors:

.. code-block:: bash
    :linenos:

    curl -d query="query" -X GET http://[IP]:[PORT]/v1.0/app/query/[ID_APP]


To get information on the thread currently running and the one in the queue:

.. code-block:: bash
    :linenos:

    curl -X GET http://[IP]:[PORT]/v1.0/info_threads



To get the ids of the application deployed and its information related:

.. code-block:: bash
    :linenos:

    curl -X GET http://[IP]:[Port]/v1.0/list_app/

To get informations for only one app:

this will give information on which adaptor are used, their status and the outputs provided.
.. code-block:: bash
    :linenos:

    curl -X GET http://[IP]:[Port]/v1.0/app/[ID_APP]



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

    s.undeploy([ID of application stack to bring down])
