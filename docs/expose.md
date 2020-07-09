# Kubernetes Adaptor 

- #### [The Basics](k8s.md)
- #### [Services and container communication](services.md)
- #### Exposing containers externally (this page)
- #### [Volumes and Configs](volumes.md)
- #### [Multi-Container Pods (Sidecars)](sidecars.md)
- #### [Special MiCADO/Kubernetes Types](custom.md)

# Exposing containers externally

We've seen how services enable communication between our containers inside the cluster. Now we'll look at how we can expose containers (actually **Pods**) to allow ingress from outside the cluster.

> **Before you start**, make sure the firewall rules for your cloud instances are configured to allow ingress on the ports you choose.

## NodePort Service

NodePort is a special type of Kubernetes service that exposes our container at a random high number port, by default in the range **30000-32767**. That port can be accessed **on any node in the cluster**. Here's how it looks in the ADT:

```yaml
web-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: nginx
    ports:
    - port: 80
      type: NodePort
  interfaces:
    Kubernetes:
      create:
```
> Since we're creating a service, we'll also get a ClusterIP and the container will be available internally at `web-container:80`.

When a random port doesn't cut it, we can provide our own (so long as it falls in the **30000-32767** range) like so:
```yaml
...
  properties:
    image: nginx
    ports:
    - port: 80
      nodePort: 30080
```
> **Note** we forgot `type: NodePort` here. The adaptor sees a nodePort defined, so it fills this in for us.

We can now reach **port 80** of the NGINX container by pointing to `:30080` on **any node in the cluster**. Since we generally know the IP of the MiCADO Master, the easiest endpoint would be `ip.of.micado.master:30080`.

> If multiple replicas of a container exist, Kubernetes will generally apply a **round-robin** technique for deciding which container to route a request to.

## HostPort

Sometimes, the port range of NodePort isn't convenient. Using **HostPort**, we can expose our container outside the cluster using **any available** port number. However, since it's binding to the host, the container can **only be accessed on the node where it is running**. Here's how it looks in the ADT:

```yaml
web-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: nginx
    ports:
    - hostPort: 80
      containerPort: 80    
  interfaces:
    Kubernetes:
      create:
```
> Here, **HostPort** indicates the port on the node, and **ContainerPort** indicates the port in the container. 

Port 80 of the container defined in the above snippet can be accessed at `ip.of.host.node:80`.

## Services and not services

HostPort is **not** a Kubernetes Service. So - under the ports key, we **cannot** put the `containerPort`/`hostPort` options in the **same list item** as Service options like `port`/`targetPort`. 

Doing something like the following, however, **is perfectly valid**:

```yaml
web-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: nginx
    ports:
    - containerPort: 80
      hostPort: 80
    - port: 8080
      targetPort: 80
  interfaces:
    Kubernetes:
      create:
```
> **Inside the cluster**, other containers can reach this one at `web-container:8080`  
> **Outside the cluster** it is served at `ip.of.host.node:80`

## Next up: [Volumes and Configs](volumes.md)