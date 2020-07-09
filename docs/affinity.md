## An example with NodeAffinity

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-container
  labels:
    app.kubernetes.io/name: app-container
    app.kubernetes.io/instance: affinity
    app.kubernetes.io/managed-by: micado
    app.kubernetes.io/version: latest
spec:
  template:
    metadata:
      labels:
        app.kubernetes.io/name: app-container
        app.kubernetes.io/instance: affinity
        app.kubernetes.io/managed-by: micado
        app.kubernetes.io/version: latest
    spec:
      containers:
      - image: nginx      
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: micado.eu/node_type
                operator: In
                values:
                - vm-node
  selector:
    matchLabels:
      app.kubernetes.io/name: app-container
      app.kubernetes.io/instance: affinity
      app.kubernetes.io/managed-by: micado
      app.kubernetes.io/version: latest
```