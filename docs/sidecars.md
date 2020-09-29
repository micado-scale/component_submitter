# Kubernetes Adaptor 

- #### [The Basics](k8s.md)
- #### [Services and container communication](services.md)
- #### [Exposing containers externally](expose.md)
- #### [Volumes and Configs](volumes.md)
- #### Multi-Container Pods (Sidecars) (this page)
- #### [Special MiCADO/Kubernetes Types](custom.md)

# Peas in a Pod

Sometimes its useful to have more than just one container in a Pod - say if you're following [the Sidecar Pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/sidecar), or need [an Init Container](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/). Here are a few ways you can create multi-container Pods in an ADT:

## Attach sidecar to main

First, define your main container as you normally would. It can be as complex or as simple as you like.

Define your sidecar container as well, but **do not** specify any interface for it - after all, it won't be independently orchestrated by Kubernetes.

Lastly, reference the dependent sidecar in the `requirements` section of you main container. Here's how it looks:

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: uowcpc/nginx:v1.2
  requirements:
  - host: virtual-machine-one
  - container: sidecar-container
  - volume: my-volume
  interfaces:
    Kubernetes:
      create:

sidecar-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: logstack
    args: ["log", "now"]
```
> As you can see, our sidecar container has no interface defined for it

## Init Containers

Init Containers run as a second container in your Pod to assert that your primary container is ready. Only when the Init Container has run to completion and `exit 0`, will your main container transition to a ready state. 

The method of attaching an Init Container is the same as the method above, though the type of the Init Container must be `tosca.nodes.MiCADO.Container.Application.Docker.Init`. 

Ensure that the Init Container is properly configured to evaluate the ready state of the main container and `exit 0` when done.

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: uowcpc/nginx:v1.2
  requirements:
  - container: init-container
  ...(truncated)...

init-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker.Init
  properties:
    image: busybox
    args: ["curl", "localhost:5000"]
```
> Make sure you specify the correct type for the Init Container, otherwise it will be included in the Pod as a regular sidecar.


## Attach two containers to a Pod

Define your containers as you normally would. You can attach volumes to both of them, but **do not** specify a host virtual machine, and **do not** specify any interface for these containers. 

Now define your empty Pod using the type `tosca.nodes.MiCADO.Container.Application.Pod`. You are welcome to define a host virtual machine requirement, and you **must** specify the interface so Kubernetes knows to create this Pod. Any `inputs` to the interface will be added to the manifest as normal.

Lastly, reference the two containers you created in the `requirements` section of you main container. Like this:

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: uowcpc/nginx:v1.2
  requirements:
  - volume: my-volume

sidecar-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: logstack
    args: ["log", "now"]

my-pod:
  type: tosca.nodes.MiCADO.Container.Application.Pod
  requirements:
  - container: app-container
  - container: sidecar-container
  - host: virtual-machine-one
  interfaces:
    Kubernetes:
      create:
```
> The end result will be the same as in our previous example - a Pod with the two containers - but here we take a different approach.


## Next up: [Special MiCADO/Kubernetes Types](custom.md)