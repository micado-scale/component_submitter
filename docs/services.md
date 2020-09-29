# Kubernetes Adaptor 

- #### [The Basics](k8s.md)
- #### Services and container communication (this page)
- #### [Exposing containers externally](expose.md)
- #### [Volumes and Configs](volumes.md)
- #### [Multi-Container Pods (Sidecars)](sidecars.md)
- #### [Special MiCADO/Kubernetes Types](custom.md)

# Services and container communication

Permitting communication between your containers (more specifically - your **Pods**) is handled via the `ports` property of an application in container. Under the hood, we use a [**Kubernetes Service**](https://kubernetes.io/docs/concepts/services-networking/service/).

## Creating a service

Let's say we want to give other Pods running on the cluster the ability to communicate with our database container. Here's the simplest way to do it:

```yaml
sql-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: mysql
    ports:
    - port: 3306
  interfaces:
    Kubernetes:
      create:
```

> If you're familiar with Kubernetes, the one little snippet above generates [these two manifests](service-ex.md).

Now, any other container can access port 3306 on this container at `sql-container:3306`. You can see the **hostname** defaults to the name of the TOSCA node you've defined.

If you have multiple ports to expose using the same hostname, you can simply add to the list of ports, like so:

```yaml
...
  properties:
    image: mysql
    ports:
    - port: 3306
    - port: 33062
...
```
> Other containers can reach both `sql-container:3306` and `sql-container:33062`

## Protocols and TargetPort

Ports default to TCP. For UDP connections, simply:

```yaml
...
  properties:
    image: flannel
    ports:
    - port: 8285
      protocol: UDP
...
```
> Kubernetes also supports the SCTP protocol

Sometimes, you may want/need to expose your container on a different port than that configured by the container by default. Consider an NGINX container listening on **port 80**, that we intend to expose to other containers using **port 8080**:

```yaml
webserver:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: nginx
    ports:
    - port: 8080
      targetPort: 80
...
```
> Other containers on the cluster can point at `webserver:8080` to hit `:80` inside the container


## Hostnames and Port names

As we've seen, the name of the generated **Service** (also the hostname for ingress to the container) defaults to the name of the parent container. You can change this by overriding the Service **metadata** like so:

```yaml
sql-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: mysql
    ports:
    - port: 3306
      metadata:
        name: database
...
```
> Using the above snippet, you would now reach your container at `database:3306`

It is important not to confuse this with the **name of the port**, which is generated automatically based on the **port** number and **protocol** (see the [previously generated manifests](service-ex.md) for an example of this).

If you have the urge to specify your own port names, you can: 

```yaml
...
  properties:
    image: mysql
    ports:
    - name: myport
      port: 3306
      metadata:
        name: database
...
```
> The port name has changed, but has no effect on our route to this container. It is still reachable at `database:3306`

## ClusterIPs

When we create a service, Kubernetes randomly assigns a **ClusterIP** to it, restricted by default to the range `10.96.0.0/12`.

If you have a requirement for IP addressing over using hostnames, you can specify a **ClusterIP** like so:

```yaml
sql-container:
  type: tosca.nodes.MiCADO.Container.Application.Docker
  properties:
    image: mysql
    ports:
    - port: 3306
      clusterIP: 10.97.101.98
...
```
> **Fun fact:** you can specify a clusterIP of `None`

We can now hit this container at `10.97.101.98:3306`. It is also still available at `sql-container:3306`.

## Next up: [Exposing containers externally](expose.md)