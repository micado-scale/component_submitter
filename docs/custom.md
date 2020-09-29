# Kubernetes Adaptor 

- #### [The Basics](k8s.md)
- #### [Services and container communication](services.md)
- #### [Exposing containers externally](expose.md)
- #### [Volumes and Configs](volumes.md)
- #### [Multi-Container Pods (Sidecars)](sidecars.md)
- #### Special MiCADO/Kubernetes Types (this page)

# Stripping away some complexity

You should now have a stronger understanding of TOSCA and our ADTs. To save you some typing when you're preparing your next ADT, we have pre-prepared a number of TOSCA types for Kubernetes in MiCADO that we hope you find convenient.

These TOSCA types either have default interfaces, default properties, or both - meaning that you won't have to write them out again unless you need to overwrite them.

You can always find the current custom TOSCA types for Kubernetes in [the main TOSCA repository](https://github.com/micado-scale/tosca/blob/develop/custom_types/container/kubernetes.yaml). Here are four of our favourites:

## The Deployment type
##### tosca.nodes.MiCADO.Container.Application.Docker.Deployment

We use plain Kubernetes Deployments all the time, [so we made a type](https://github.com/micado-scale/tosca/blob/develop/custom_types/container/kubernetes.yaml#L19) that includes a Kubernetes interface by default.

Use it like this:

```yaml
my-easy-deployment:
  type: tosca.nodes.MiCADO.Container.Application.Docker.Deployment
  properties:
    image: uowcpc/nginx:v1.2
  requirements:
  - host: my-host
```
> No need to define any interfaces here, that's taken care of by the type!

> There are also similar types for DaemonSet and StatefulSet

## The EmptyDir Volume type
##### tosca.nodes.MiCADO.Container.Volume.EmptyDir

Again, we use these alot, so we created a type for them.

Use it like this:

```yaml
my-easy-deployment:
  type: tosca.nodes.MiCADO.Container.Application.Docker.Deployment
  properties:
    image: uowcpc/nginx:v1.2
  requirements:
  - volume: my-empty

my-empty:
  type: tosca.nodes.MiCADO.Container.Volume.EmptyDir
```
> No properties, no interfaces, just two lines!

## The NFS Volume type
##### tosca.nodes.MiCADO.Container.Volume.NFS

With this type we worked a bit of magic, and moved the NFS `server` and `path` options up out of `inputs` and into `properties`.

Use it like this:

```yaml
my-easy-deployment:
  type: tosca.nodes.MiCADO.Container.Application.Docker.Deployment
  properties:
    image: uowcpc/nginx:v1.2
  requirements:
  - volume: my-nfs

my-nfs:
  type: tosca.nodes.MiCADO.Container.Volume.NFS
  properties:
    path: /nfs/share
    server: 10.0.0.2
```
> The `path` property here still serves as the default mount point in the container, if you don't specify one otherwise.

> There is a similar type for HostPath!

## The ConfigMap type
##### tosca.nodes.MiCADO.Container.Config.ConfigMap

We did a similar thing to above, and moved the `data` and `binaryData` options up out of `inputs` and into `properties`.

Use it like this:

```yaml
my-easy-deployment:
  type: tosca.nodes.MiCADO.Container.Application.Docker.Deployment
  properties:
    image: uowcpc/nginx:v1.2
    envFrom:
    - configMapRef:
        name: my-config

my-config:
  type: tosca.nodes.MiCADO.Container.Config.ConfigMap
  properties:
    data:
      some: interesting_data
```
> Enjoy!

## That's all! [Back to the start...](index.md)