# Kubernetes Adaptor 

- #### The Basics (this page)
- #### [Services and container communication](services.md)
- #### [Exposing containers externally](expose.md)
- #### [Volumes and Configs](volumes.md)
- #### [Multi-Container Pods (Sidecars)](sidecars.md)
- #### [Special MiCADO/Kubernetes Types](custom.md)

# The Basics

## Properties and Interfaces

[In case you missed it](index.md#a-closer-look), there is a clear distinction between `properties` and `interfaces`. For the Kubernetes adaptor specficially:

* We use `properties` to define options and parameters that are general enough that they could be applied to _any_ Docker container, regardless of the orchestrator.
* We use `inputs` under `interfaces` to indicate that we want to overwrite the fields that one would find in a generated Kubernetes manifest

> Unless you've been explicit, the adaptor will try to orchestrate your container as a Kubernetes **Deployment**

## The bare minimum

At a minimum, you'll need a container image in DockerHub that you want to use. Here's a minimum working example:

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: nginx
  interfaces:
    Kubernetes:
      create:
```

For those familiar with Kubernetes, this will mount a single **container** (_nginx:latest_) inside a **Pod** owned by a **Deployment** using a set of labels based on [Kubernetes recommendations](https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/#labels). If you're interested, the final generated Kubernetes manifest [looks like this](mwe.md).

> If you're not familiar with Kubernetes, the above YAML snippet is good for creating a scalable unit of your specified container in MiCADO.

## Choosing a host

Often, you'll want to be sure that your container runs on a specific node (virtual machine) within your deployment. You can accomplish this by referencing the virtual machine node in the **requirements** section of your container description, like so:

```yaml
vm-node:
  type: tosca.nodes.MiCADO.EC2.Compute
  ...(truncated)...

app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: nginx
  requirements:
  - host: vm-node
  interfaces:
    Kubernetes:
      create:
```
> In Kubernetes-speak, this adds a NodeAffinity to the [generated manifest](affinity.md)

## More properties

You will likely need to provide more customisation for your container than simply specifying an image. The available list of properties is available in the [official documentation for MiCADO](https://micado-scale.readthedocs.io/en/latest/application_description.html#properties).

## Switching it up

If you need something more specific than the basic **Deployment** workload, you'll have to say as much using `inputs`. Here's how it would look:

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: nginx
  interfaces:
    Kubernetes:
      create:
        inputs:
          kind: DaemonSet
```

> The DaemonSet workload creates a replica of the container on each active node, like a _global_ service in Docker Swarm

We support all of the [Workload Controllers](https://kubernetes.io/docs/concepts/workloads/controllers/), though to get certain workloads to validate, you'll have to provide further parameters under `inputs`.

## More inputs

If you're comfortable with Kubernetes manifests, you can fully customise the final generated manifest by using `inputs`. There's no definitive list of available options - you are only restricted by what's in the [Kubernetes API](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.18/#-strong-workloads-apis-strong-). Here's an example with **StatefulSets**:

```yaml
app-stateful:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: nginx
  interfaces:
    Kubernetes:
      create:
        inputs:
          kind: StatefulSet
          metadata:
            labels:
              interesting_label: info
          spec:
            serviceName: app-stateful
            updateStrategy:
              type: RollingUpdate
            template:
              spec:
                hostNetwork: True
```
> Here we're adding lots of Kubernetes specific customisation, right down to the level of the **PodSpec**. [Here's the generated manifest](stateful-ex.md) if you're interested. As you can see, the container we've described using `properties` is still at the core of this StatefulSet.

## Next up: [Services and container communication](services.md)