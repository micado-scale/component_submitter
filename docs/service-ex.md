## Generated Service and Deployment manifests...

```yaml
apiVersion: v1
kind: Service
metadata:
  name: sql-container
  labels:
    app.kubernetes.io/name: sql-container
    app.kubernetes.io/instance: service-ex
    app.kubernetes.io/managed-by: micado
spec:
  selector:
    app.kubernetes.io/name: sql-container
    app.kubernetes.io/instance: service-ex
    app.kubernetes.io/managed-by: micado
    app.kubernetes.io/version: latest
  ports:
  - name: 3306-tcp
    port: 3306
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sql-container
  labels:
    app.kubernetes.io/name: sql-container
    app.kubernetes.io/instance: service-ex
    app.kubernetes.io/managed-by: micado
    app.kubernetes.io/version: latest
spec:
  template:
    metadata:
      labels:
        app.kubernetes.io/name: sql-container
        app.kubernetes.io/instance: service-ex
        app.kubernetes.io/managed-by: micado
        app.kubernetes.io/version: latest
    spec:
      containers:
      - image: mysql
  selector:
    matchLabels:
      app.kubernetes.io/name: sql-container
      app.kubernetes.io/instance: service-ex
      app.kubernetes.io/managed-by: micado
      app.kubernetes.io/version: latest
```