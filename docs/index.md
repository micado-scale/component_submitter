# MiCADO Submitter 

## TOSCA and the ADT by example


- #### [Topology and Orchestration Specification for Cloud Applications](https://oasis-open.org/committees/tosca/)
- #### [Application Description Templates](https://github.com/micado-scale/tosca/tree/master/ADT)

> ADTs are always TOSCA...  
> but TOSCA is not always an ADT

## The API

- #### [Swagger Documentation](swagger.html)

## The Adaptors

- #### [The Kubernetes Adaptor](k8s.md)
- #### [The Occopus Adaptor](https://micado-scale.readthedocs.io/en/latest/application_description.html#virtual-machine) (links to RTD)
- #### [The Terraform Adaptor](https://micado-scale.readthedocs.io/en/latest/application_description.html#virtual-machine) (links to RTD)
- #### [The PolicyKeeper Adaptor](https://micado-scale.readthedocs.io/en/latest/application_description.html#scaling-policy) (links to RTD)
- #### [The Security Adaptor](https://micado-scale.readthedocs.io/en/latest/application_description.html#network-policy) (links to RTD)

## A general refresher...

* Application Description Templates are the domain specific language of MiCADO.

* They describe the container, virtual machine and scaling/security policies that make up an application deployment.

* These different sections of the ADT get translated and orchestrated by the relevant underlying tools in MiCADO.

## A quick look...

ADTs are based on TOSCA, written in YAML and you can start writing one like this:

```yaml
tosca_definitions_version: tosca_simple_yaml_1_2

imports:
  - tosca/develop/micado_types.yaml

repositories:
  docker_hub: https://hub.docker.com/

description: ADT for stressng on EC2
```

Next up, the `topology_template` is where you describe your containers, virtual machines and policies, beginning with **container** and **virtual machines** under `node_templates`  like so:

```yaml
topology_template:
  node_templates:
  
    app-container:
      type: tosca.nodes.MiCADO.Container.Application.Docker
      properties:
        image: uowcpc/nginx:v1.2
      interfaces:
        Kubernetes:
          create:
            inputs:
              kind: Deployment


    worker-virtualmachine:
      type: tosca.nodes.MiCADO.EC2.Compute
      properties:
        instance_type: t2.small
      interfaces:
        Terraform:
          create:
      
```

## A closer look...

* Looking above, you can see we use a specific `type` to let our adaptors know what they are looking at.

* You can think of `properties` as providing the options and parameters specific to the **basic resource** that you want to orchestate (above, the **Docker container**, and the **EC2 compute instance**).
  
* The `interfaces` section, on the other hand, specifies the **orchestrator** that should be used to manage the defined resouce, with the option to pass in options and parameters for that tool (above, **Kubernetes** and **Terraform**).