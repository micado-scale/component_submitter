## Minimum working example...

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-container
  labels:
    app.kubernetes.io/name: app-container
    app.kubernetes.io/instance: mwe
    app.kubernetes.io/managed-by: micado
    app.kubernetes.io/version: latest
spec:
  template:
    metadata:
      labels:
        app.kubernetes.io/name: app-container
        app.kubernetes.io/instance: mwe
        app.kubernetes.io/managed-by: micado
        app.kubernetes.io/version: latest
    spec:
      containers:
      - image: nginx
        name: app-container
  selector:
    matchLabels:
      app.kubernetes.io/name: app-container
      app.kubernetes.io/instance: mwe
      app.kubernetes.io/managed-by: micado
      app.kubernetes.io/version: latest
```