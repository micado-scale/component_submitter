# Kubernetes Adaptor 

- #### [The Basics](k8s.md)
- #### [Services and container communication](services.md)
- #### [Exposing containers externally](expose.md)
- #### Volumes and Configs (this page)
- #### [Multi-Container Pods (Sidecars)](sidecars.md)
- #### [Special MiCADO/Kubernetes Types](custom.md)

# Volumes and Configs

For persisting configurations and data across different deployments, we support [Kubernetes Volumes](https://kubernetes.io/docs/concepts/storage/volumes/) and [Kubernetes ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/). 

Volumes and ConfigMaps are described under `node_templates` of a `topology_template`, and get their own description, just like a container or virtual machine. We can then reference a volume or config under the `requirements` section of a container, in the same way we [specify a host](k8s.md#choosing-a-host). Here's an example:

```yaml
node_templates:

  app-container:
    type: tosca.nodes.MiCADO.Container.Application.Docker
    properties:
      ...
    requirements:
    - host: worker-virtualmachine
    - volume: persistent-storage

  worker-virtualmachine:
    type: tosca.nodes.MiCADO.EC2.Compute
    properties:
      ...

  persistent-storage:
    type: tosca.nodes.MiCADO.Container.Volume
    properties:
      ...
```

## Creating Common Volumes

In theory, the adaptor supports any of the Kubernetes Volume types. Here are three common examples to get you started:

### EmptyDir

This is a volatile volume for very temporary storage purposes. It will survive a Pod crash, but will be deleted when the Pod is removed.

```yaml
temporary-storage:
  type: tosca.nodes.MiCADO.Container.Volume
  interfaces:
    Kubernetes:
      create:
        inputs:
          spec:
            emptyDir: {}
```
> That's it!

### HostPath

These volumes are for when you want to share data to and/or from the host. In a multi-node setting this gets tricky since your Pod might jump to different nodes, with different stored data.

```yaml
docker-socket:
  type: tosca.nodes.MiCADO.Container.Volume
  interfaces:
    Kubernetes:
      create:
        inputs:
          spec:
            hostPath:
              path: /var/run/docker.sock
```
> Here we define the path on the host

### NFS

Network File System shares are a common solution for persisting data. You can host an NFS server outside of a MiCADO deployment, and then use MiCADO to mount shares into your deployed containers.

```yaml
docker-socket:
  type: tosca.nodes.MiCADO.Container.Volume
  interfaces:
    Kubernetes:
      create:
        inputs:
          spec:
            nfs:
              server: 192.168.1.1
              path: /nfs/shared
```
> **Note** You'll need to install `nfs-common` on your virtual machines - [you can see it done here](https://github.com/micado-scale/ansible-micado/blob/master/demos/wordpress/wordpress_azure.yaml#L24)

## Using Volumes

[As we saw](#volumes-and-configs), we can mount volumes inside our containers by specifying them under `requirements` in the container description. By default, MiCADO creates a mount point in our container for volumes mounted in this way at `/mnt/volumes/name-of-volume`. 

Most of the time, we need more control over where our volumes are mounted, and we can accomplish that by using the following syntax:

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    ...
  requirements:
  - volume:
      name: persistent-storage
      relationship:
        type: tosca.relationships.AttachesTo
        properties:
          location: /var/www/html
          
persistent-storage:
  type: tosca.nodes.MiCADO.Container.Volume
  properties:
    ...
```
> Define the mount point inside your container using `location`

**Note** You may be able to save a few lines in your ADT by specifying the `path` property when you first define your volumes. The Adaptor will use `path` (if it exists) as the mount point if `location` is not defined, before generating the `/mnt/micado` path. For example:

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    ...
  requirements:
  - volume: persistent-storage
          
persistent-storage:
  type: tosca.nodes.MiCADO.Container.Volume
  properties:
    path: /var/www/html
  ...
```
> Since we've not specified `location` under `requirements`, the adaptor will set the mount point of the volume to the `path` provided in the volume definition (*/var/www/html*).

## Creating Configs

Configs are even easier than volumes. Simply pass a set of `key:value` pairs to `data` like so:

```yaml
hdfs-config:
  type: tosca.nodes.MiCADO.Container.Config
  interfaces:
    Kubernetes:
      create:
        inputs:
          data:
            HDFS-SITE.XML_dfs.namenode: "/data/namenode"
            HDFS-SITE.XML_dfs.datanode: "/data/datanode"
```
> For binary data, use `binaryData` under inputs

## Using Configs (Environment)

We can load all the `key:value` pairs from a created ConfigMap into environment variables like so:

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: hadoop
    envFrom:
    - configMapRef:
        name: hdfs-config
  interfaces:
    Kubernetes:
      create:
```
> Here we're using the `envFrom` property

Alternatively we can select a single value from the ConfigMap and assign it to a new environment variable, like so:

```yaml
...
  properties:
    image: hadoop
    env:
    - name: HDFS_NAMENODE_DIR
      valueFrom:
        configMapKeyRef:
          name: hdfs-config
          key: HDFS-SITE.XML_dfs.namenode
...
```
> Here we're using the regular `env` property, with `valueFrom`

## Using Configs (Mounts)

Instead of using environment variables, we can mount a created ConfigMap in a container, just like we would a volume:

```yaml
app-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: hadoop
  requirements:
  - volume:
      name: hdfs-config
      relationship:
        type: tosca.relationships.AttachesTo
        properties:
          location: /etc/hdfs/config
  interfaces:
    Kubernetes:
      create:
```
> **Pro tip:** Just like with volumes, if you define the `path` property on your ConfigMap, the adaptor will use it as a default mount point (meaning you can just write `- volume: hdfs-config`)

When a ConfigMap gets mounted into a container, Kubernetes creates a file named after each key in the ConfigMap. Each file is then populated with its matching value. This can be useful for creating configuration files in a container, for example:

```yaml
nginx-config:
  type: tosca.nodes.MiCADO.Container.Config.Kubernetes
  interfaces:
    Kubernetes:
      create:
        inputs:
          data:
            nginx.conf: |
              events {}

              http {
                  server {
                      listen 8000;
                  }
              }
```
> When this ConfigMap gets mounted, the file `nginx.conf` will be created at the mount point, populated with the given value

## Next up: [Multi-Container Pods (Sidecars)](sidecars.md)