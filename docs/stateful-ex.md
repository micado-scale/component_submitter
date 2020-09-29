## Lots of inputs for a StatefulSet...

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  labels:
    interesting_label: info
    app.kubernetes.io/name: app-stateful
    app.kubernetes.io/instance: stateful-ex
    app.kubernetes.io/managed-by: micado
    app.kubernetes.io/version: latest
  name: app-stateful
spec:
  serviceName: app-stateful
  updateStrategy:
    type: RollingUpdate
  template:
    spec:
      containers:
      - image: nginx
        name: app-stateful
      hostNetwork: true
    metadata:
      labels:
        app.kubernetes.io/name: app-stateful
        app.kubernetes.io/instance: stateful-ex
        app.kubernetes.io/managed-by: micado
        app.kubernetes.io/version: latest
  selector:
    matchLabels:
      app.kubernetes.io/name: app-stateful
      app.kubernetes.io/instance: stateful-ex
      app.kubernetes.io/managed-by: micado
      app.kubernetes.io/version: latest
```