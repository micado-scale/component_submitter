class ZorpManifests(object):
    @staticmethod
    def service_account():
        return {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": "zorp-ingress-service-account",
                "namespace": "micado-worker",
                "labels": {
                    "app.kubernetes.io/name": "zorp-ingress-service-account",
                    "app.kubernetes.io/managed-by": "micado",
                    "app.kubernetes.io/version": "1.0",
                },
            },
        }

    @staticmethod
    def cluster_role():
        return {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {
                "name": "zorp-ingress-cluster-role",
                "labels": {
                    "app.kubernetes.io/name": "zorp-ingress-cluster-role",
                    "app.kubernetes.io/managed-by": "micado",
                    "app.kubernetes.io/version": "1.0",
                },
            },
            "rules": [
                {
                    "apiGroups": [""],
                    "resources": [
                        "configmaps",
                        "endpoints",
                        "nodes",
                        "pods",
                        "secrets",
                        "services",
                        "namespaces",
                        "events",
                        "serviceaccounts",
                    ],
                    "verbs": ["get", "list", "watch"],
                },
                {
                    "apiGroups": ["extensions"],
                    "resources": ["ingresses", "ingresses/status"],
                    "verbs": ["get", "list", "watch"],
                },
            ],
        }

    @staticmethod
    def role_binding():
        return {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {
                "name": "zorp-ingress-cluster-role-binding",
                "namespace": "micado-worker",
                "labels": {
                    "app.kubernetes.io/name": "zorp-ingress-cluster-role-binding",
                    "app.kubernetes.io/managed-by": "micado",
                    "app.kubernetes.io/version": "1.0",
                },
            },
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": "zorp-ingress-cluster-role",
            },
            "subjects": [
                {
                    "kind": "ServiceAccount",
                    "name": "zorp-ingress-service-account",
                    "namespace": "micado-worker",
                }
            ],
        }

    @staticmethod
    def daemon_set(ports_list):
        return {
            "apiVersion": "apps/v1",
            "kind": "DaemonSet",
            "metadata": {
                "name": "zorp-ingress",
                "namespace": "micado-worker",
                "labels": {
                    "run": "zorp-ingress",
                    "app.kubernetes.io/name": "zorp-ingress",
                    "app.kubernetes.io/managed-by": "micado",
                    "app.kubernetes.io/version": "1.0",
                },
            },
            "spec": {
                "selector": {"matchLabels": {"run": "zorp-ingress"}},
                "template": {
                    "metadata": {"labels": {"run": "zorp-ingress"}},
                    "spec": {
                        "serviceAccountName": "zorp-ingress-service-account",
                        "containers": [
                            {
                                "name": "zorp-ingress",
                                "image": "balasys/zorp-ingress:1.0",
                                "args": [
                                    "--namespace=micado-worker",
                                    "--ingress.class=zorp",
                                    "--behaviour=tosca",
                                    "--ignore-namespaces=micado-system,kube-system",
                                ],
                                "livenessProbe": {
                                    "httpGet": {"path": "/healthz", "port": 1042}
                                },
                                "ports": ports_list,
                            }
                        ],
                    },
                },
            },
        }

    @staticmethod
    def ingress(ingress_conf):
        return {
            "apiVersion": "networking.k8s.io/v1beta1",
            "kind": "Ingress",
            "metadata": {
                "name": "zorp-ingress",
                "namespace": "micado-worker",
                "annotations": {
                    "kubernetes.io/ingress.class": "zorp",
                    "zorp.ingress.kubernetes.io/conf": ingress_conf,
                },
            },
            "spec": {"rules": [{"http": None}]},
        }
