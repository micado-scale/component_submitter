import unittest
from unittest.mock import Mock, patch
from collections import namedtuple

from toscaparser.tosca_template import ToscaTemplate
from adaptors.k8s_adaptor.k8s_adaptor import KubernetesAdaptor
from adaptors.k8s_adaptor.resources import (
    Resource,
    Workload,
    Pod,
    PersistentVolume,
    PersistentVolumeClaim,
    Container,
    Service,
    ConfigMap,
)
from adaptors.k8s_adaptor.resources import pod, container, service

VER_LABEL = "app.kubernetes.io/version"

DEFAULT_RESOURCE = {
    "apiVersion": "",
    "kind": "",
    "metadata": {
        "name": "",
        "labels": {
            "app.kubernetes.io/name": "",
            "app.kubernetes.io/instance": "",
            "app.kubernetes.io/managed-by": "",
            VER_LABEL: "",
        },
    },
    "spec": {},
}

APP = "app-name"
NODE = "node-name"

COMPUTE_HOST_KEY = "micado.eu/node_type"
EDGE_HOST_KEY = "name"


class TestResource(unittest.TestCase):
    """ UnitTests for Resource class """

    def test_resource_keys(self):
        resource = Resource(APP, NODE, {})
        compare = DEFAULT_RESOURCE.keys()
        self.assertEqual(compare, resource.manifest.keys())

    def test_resource_label_keys(self):
        resource = Resource(APP, NODE, {})
        compare = DEFAULT_RESOURCE["metadata"]["labels"].keys()
        self.assertEqual(compare, resource.labels.keys())

    def test_resource_metadata_keys(self):
        resource = Resource(APP, NODE, {})
        compare = DEFAULT_RESOURCE["metadata"].keys()
        self.assertEqual(compare, resource.manifest["metadata"].keys())

    def test_resource_custom_name(self):
        resource = Resource(APP, NODE, {"metadata": {"name": "custom"}})
        self.assertEqual(resource.labels["app.kubernetes.io/name"], "custom")
        self.assertEqual(resource.manifest["metadata"]["name"], "custom")
        self.assertEqual(resource.name, "custom")

    def test_resource_custom_label(self):
        resource = Resource(
            APP, NODE, {"metadata": {"labels": {"custom-label": "custom"}}}
        )
        compare = DEFAULT_RESOURCE["metadata"]["labels"].keys()
        self.assertGreaterEqual(resource.labels.keys(), compare)
        self.assertEqual(resource.labels["custom-label"], "custom")

    def test_resource_custom_kind(self):
        resource = Resource(APP, NODE, {"kind": "StatefulSet"})
        self.assertEqual(resource.manifest["kind"], "StatefulSet")

    def test_resource_custom_namespace(self):
        resource = Resource(APP, NODE, {"metadata": {"namespace": "custom"}})
        self.assertEqual(resource.manifest["metadata"]["namespace"], "custom")
        self.assertEqual(resource.namespace, "custom")

    def test_validate_kind(self):
        resource = Resource(APP, NODE, {"kind": ""})
        with self.assertRaises(ValueError):
            resource._validate()

    def test_validate_apiversion(self):
        resource = Resource(APP, NODE, {"kind": "BadKindName"})
        with self.assertRaises(ValueError):
            resource._validate()


class TestContainer(unittest.TestCase):
    """ UnitTests for Container Class """

    def setUp(self):
        """ Setup Validator object and prep a bad TOSCA template """
        info = Mock()
        self.container = Container(info)

    def test_remove_swarm_keys(self):
        self.container.spec = {"stop_signal": "9"}
        self.container._remove_swarm_keys()
        self.assertNotIn("stop_signal", self.container.spec)

    def test_remove_pod_labels(self):
        self.container.spec = {"labels": {"newlabel": "test"}}
        self.container._remove_pod_keys()
        self.assertEqual({"newlabel": "test"}, self.container.labels)

    def test_remove_pod_ports(self):
        self.container.spec = {"ports": [{"containerPort": "8080"}]}
        self.container._remove_pod_keys()
        self.assertIn({"containerPort": "8080"}, self.container.ports)

    def test_remove_pod_fields(self):
        self.container.spec = {"stop_grace_period": "10"}
        self.container._remove_pod_keys()
        self.assertEqual(self.container.pod_opts["grace"], "10")
        self.assertEqual(self.container.pod_opts["pid"], None)

    def test_translate_environment(self):
        environment = {"ENV1": "val1", "ENV2": "val2"}
        env = container._make_env(environment)
        try:
            self.assertEqual(env[0]["name"], "ENV1")
            self.assertEqual(env[0]["value"], "val1")
            self.assertEqual(env[1]["name"], "ENV2")
            self.assertEqual(env[1]["value"], "val2")
        except KeyError as err:
            self.fail(
                f"Missing key {err} when translating Docker environment vars"
            )
        except IndexError:
            self.fail(
                "Out of range on env list when translating Docker env vars"
            )

    def test_split_entrypoint(self):
        self.container.spec = {"entrypoint": "stress -l 85"}
        self.container._translate_docker_properties()
        self.assertIn("command", self.container.spec)
        self.assertEqual(
            self.container.spec["command"], ["stress", "-l", "85"]
        )

    def test_empty_property_cleanup(self):
        self.container.spec = {"working_dir": None}
        self.container._translate_docker_properties()
        self.assertNotIn("workingDir", self.container.spec)

    def test_find_image_with_parent(self):
        parent = {"artifacts": {"image": {"file": "parentname"}}}
        info = Mock(artifacts={})
        info.parent = parent
        self.container = Container(info)
        image = self.container._get_image_from_artifact()
        self.assertEqual(image, "parentname")

    def test_find_image_with_artifact(self):
        artifact = {"image": {"file": "imagename"}}
        parent = {"artifacts": {"image": {"file": "parentname"}}}

        info = Mock(artifacts=artifact)
        info.parent = parent
        self.container = Container(info)
        image = self.container._get_image_from_artifact()
        self.assertEqual(image, "imagename")

    def test_find_image_with_dockerhub(self):
        artifact = {"image": {"file": "imagename", "repository": "DOCKER hub"}}
        info = Mock(artifacts=artifact)
        self.container = Container(info)
        image = self.container._get_image_from_artifact()
        self.assertEqual(image, "imagename")

    def test_find_image_with_custom_undefined(self):
        artifact = {"image": {"file": "imagename", "repository": "myrepo"}}
        info = Mock(artifacts=artifact, repositories={})
        self.container = Container(info)
        with self.assertRaises(KeyError):
            self.container._get_image_from_artifact()

    def test_find_image_with_custom_defined(self):
        artifact = {"image": {"file": "imagename", "repository": "myrepo"}}
        repo = {"myrepo": "https://docker.io/registry"}
        info = Mock(artifacts=artifact, repositories=repo)
        self.container = Container(info)
        image = self.container._get_image_from_artifact()
        self.assertEqual(image, "docker.io/registry/imagename")

    def test_get_image_version(self):
        info = Mock(properties={"image": "nginx:v08-rc2"})
        self.container = Container(info)
        self.container._set_image()
        self.assertEqual(self.container.labels[VER_LABEL], "v08-rc2")

    def test_get_image_version_latest(self):
        info = Mock(properties={"image": "nginx"})
        self.container = Container(info)
        self.container._set_image()
        self.assertEqual(self.container.labels[VER_LABEL], "latest")

    def test_missing_image(self):
        info = Mock(artifacts={}, properties={})
        info.parent = {}
        self.container = Container(info)
        with self.assertRaises(LookupError):
            self.container._set_image()


class TestPod(unittest.TestCase):
    """ UnitTests for Pod Class """

    def setUp(self):
        """ Setup Validator object and prep a bad TOSCA template """
        self.pod = Pod(APP, NODE)
        self.mock_pod = Mock()
        self.mock_pod.configure_mock(spec={})

    def test_pod_clear_keys(self):
        compare = list(DEFAULT_RESOURCE.keys())[2:]
        self.assertEqual(compare, list(self.pod.manifest.keys()))
        self.assertNotIn("name", self.pod.manifest["metadata"])

    def test_handle_pod_keys(self):
        info = Mock(properties={"stop_grace_period": "123"})
        cont = Container(info)

        cont._remove_pod_keys()
        self.pod._update_pod_spec(cont)
        self.assertIn("terminationGracePeriodSeconds", self.pod.spec)

    @patch.object(Pod, "_add_affinity_to_spec")
    def test_add_host_affinity(self, mocked):
        Pod.add_affinity(Pod, {"micado.eu/node_type": ["host-1"]})
        self.assertEqual(mocked.call_count, 1)
        Pod.add_affinity(Pod, {"compute": ["host-2"], "name": []})
        self.assertEqual(mocked.call_count, 3)

    def test_add_affinity_to_spec(self):
        Pod._add_affinity_to_spec(self.mock_pod, "mykey", [])
        self.assertNotIn("affinity", self.mock_pod.spec)
        Pod._add_affinity_to_spec(self.mock_pod, "mykey", ["c-one", "c-two"])
        self.assertIn("affinity", self.mock_pod.spec)
        Pod._add_affinity_to_spec(self.mock_pod, "otherkey", ["e-one"])
        self.assertEqual(
            len(
                self.mock_pod.spec["affinity"]["nodeAffinity"][
                    "requiredDuringSchedulingIgnoredDuringExecution"
                ]["nodeSelectorTerms"]
            ),
            2,
        )

    def test_add_container(self):
        info = Mock(properties={"image": "test"}, mounts={})
        cont = Container(info)
        cont.build()
        self.pod.add_containers([cont])

    # Handle port tests

    def test_handle_very_short_docker_port(self):
        port = "8080"
        kube_port = pod._handle_docker_port(port)
        self.assertEqual(kube_port["port"], "8080")

    def test_handle_slightly_longer_docker_port(self):
        port = "8080:80"
        kube_port = pod._handle_docker_port(port)
        self.assertEqual(kube_port["targetPort"], "8080")
        self.assertEqual(kube_port["port"], "80")

    def test_handle_container_port(self):
        port = {"containerPort": 8080}
        info = namedtuple("Data", ["name", "properties"])(
            NODE, {"ports": [port]}
        )

        cont = Container(info)
        cont._remove_pod_keys()
        self.pod._extract_ports(cont)
        self.assertIn(port, cont.spec["ports"])

    def test_handle_int_port(self):
        port = {"port": "8080"}
        info = namedtuple("Data", ["name", "properties"])(
            NODE, {"ports": [8080]}
        )
        cont = Container(info)

        cont._remove_pod_keys()
        self.pod._extract_ports(cont)
        self.assertIn(port, self.pod.ports)

    # Handle volume mounting tests

    @patch.object(pod, "_get_volume_spec")
    def test_add_mounts_name_resolution(self, mock):
        metadata = {"metadata": {"name": "claim"}}
        mount = Mock(properties={}, inputs=metadata)
        mount.name = "node"
        container = Mock()
        container.info = Mock(requirements={})
        Pod._add_mounts(self.mock_pod, "configs", [mount], container)
        call_args = mock.call_args[0]
        self.assertEqual(call_args, ("configs", "node", metadata, "claim"))

        mount = Mock(name="claim", properties={"name": "node"}, inputs={})
        mount.name = "claim"
        Pod._add_mounts(self.mock_pod, "configs", [mount], container)
        call_args = mock.call_args[0]
        self.assertEqual(call_args, ("configs", "node", {}, "claim"))

    @patch.object(Pod, "_add_mounts")
    def test_handle_mount_types(self, mocked):
        container = Mock()
        container.info = Mock(mounts={"volumes": [], "configs": []})
        Pod._handle_mounts(Pod, container)
        self.assertEqual(mocked.call_count, 2)

    def test_add_volume_to_pod_spec(self):
        volume_spec = {"name": "volume-1"}
        volume_spec_2 = {"name": "volume-2"}
        Pod._add_volume_to_pod_spec(self.mock_pod, volume_spec)
        self.assertIn(volume_spec, self.mock_pod.spec["volumes"])
        Pod._add_volume_to_pod_spec(self.mock_pod, volume_spec)
        self.assertEqual(len(self.mock_pod.spec["volumes"]), 1)
        Pod._add_volume_to_pod_spec(self.mock_pod, volume_spec_2)
        self.assertEqual(len(self.mock_pod.spec["volumes"]), 2)

    def test_get_path_on_disk(self):
        path = pod._get_path_on_disk({"map": {"path": "y"}}, {"path": "x"})
        self.assertEqual(path, "y")
        path = pod._get_path_on_disk({}, {"path": "x"})
        self.assertEqual(path, "x")
        path = pod._get_path_on_disk({}, {})
        self.assertEqual(path, "")

    def test_get_volume_property(self):
        properties = {"location": "x", "read_only": True}
        node = {"node": "name", "relationship": {"properties": properties}}

        path = pod._get_volume_property("location", "name", [{"volume": node}])
        read_only = pod._get_volume_property(
            "read_only", "name", [{"volume": node}]
        )
        self.assertEqual(path, "x")
        self.assertEqual(read_only, True)

        # Missing key
        node["relationship"]["properties"].pop("location")
        path = pod._get_volume_property("location", "name", [{"volume": node}])
        self.assertEqual(path, False)

        # Non-matching name
        node["node"] = "notname"
        path = pod._get_volume_property("location", "name", [{"volume": node}])
        read_only = pod._get_volume_property(
            "read_only", "name", [{"volume": node}]
        )
        self.assertEqual(path, False)
        self.assertEqual(read_only, False)

    def test_get_volume_spec_with_volumes(self):
        mount_type = "volumes"
        with patch(
            "adaptors.k8s_adaptor.resources.pod._inline_volume_check"
        ) as mock:
            pod._get_volume_spec(mount_type, "", {}, "")
            self.assertEqual(mock.call_count, 1)

    def test_get_volume_spec_with_configs(self):
        mount_type = "configs"
        spec = pod._get_volume_spec(mount_type, "", {}, "")
        self.assertIn("configMap", spec)

    def test_get_volume_spec_with_secrets(self):
        mount_type = "secrets"
        spec = pod._get_volume_spec(mount_type, "", {}, "")
        self.assertIn("secret", spec)

    def test_get_volume_spec_with_unknown(self):
        mount_type = "wrong"
        with self.assertRaises(TypeError):
            pod._get_volume_spec(mount_type, "", {}, "")

    def test_inline_volume_check_empty_dir(self):
        inputs = {"spec": {"emptyDir": {}}}
        spec = pod._inline_volume_check(inputs, "name")
        self.assertEqual(spec, inputs)

    def test_inline_volume_check_pvc(self):
        spec = pod._inline_volume_check({}, "name")
        self.assertIn({"claimName": "name"}, spec.values())

    def test_add_volumes_to_container_spec(self):
        spec = {}
        name, path = "node", "path/to"
        pod._add_volume_to_container_spec(name, spec, path, True)
        self.assertIn(
            {"name": name, "mountPath": path, "readOnly": "true"},
            spec["volumeMounts"],
        )
        pod._add_volume_to_container_spec(name, spec, path, False)
        self.assertEqual(len(spec["volumeMounts"]), 2)
        self.assertIn({"name": name, "mountPath": path}, spec["volumeMounts"])


class TestWorkload(unittest.TestCase):
    """ UnitTests for Workload Class """

    def setUp(self):
        self.mock_work = Mock(version="", manifest={}, labels={})
        self.mock_work.spec = {}
        self.mock_pod = Mock(manifest={}, labels={"keep_this_label": "x"})
        self.mock_pod.spec = {}

    def test_workload_default_kind_set(self):
        work = Workload("app", "name", {})
        self.assertEqual(work.manifest["kind"], "Deployment")
        work = Workload("app", "name", {"kind": "StatefulSet"})
        self.assertEqual(work.manifest["kind"], "StatefulSet")

    def test_workload_add_pod_to_manifest(self):
        self.mock_pod.manifest = {"overwrite": "original", "pod-key": "as-is"}
        self.mock_work.pod = self.mock_pod
        self.mock_work.spec = {"overwrite": "replaced"}
        Workload._add_pod_to_manifest(self.mock_work, "Pod")
        self.assertNotIn("template", self.mock_work.spec)
        self.assertIn("replaced", self.mock_work.manifest.values())
        self.assertIn("pod-key", self.mock_work.manifest)

    def test_workload_add_workload_to_manifest(self):
        self.mock_pod.manifest = {
            "spec": {"still": "here", "present": "original"}
        }
        self.mock_pod.spec = self.mock_pod.manifest["spec"]
        self.mock_work.pod = self.mock_pod
        self.mock_work.spec = {"template": {"spec": {"present": "replaced"}}}
        Workload._add_pod_to_manifest(self.mock_work, "StatefulSet")
        self.assertIn(
            "replaced", self.mock_work.spec["template"]["spec"].values()
        )
        self.assertIn("here", self.mock_work.spec["template"]["spec"].values())

    def test_workload_add_selector_to_manifest(self):
        self.mock_work.pod = self.mock_pod
        Workload._add_pod_to_manifest(self.mock_work, "Deployment")
        self.assertIn(
            "keep_this_label", self.mock_work.spec["selector"]["matchLabels"]
        )

    def test_workload_add_job_to_manifest(self):
        self.mock_work.pod = self.mock_pod
        Workload._add_pod_to_manifest(self.mock_work, "Job")
        self.assertNotIn("selector", self.mock_work.spec)

    def test_workload_set_version_label(self):
        self.mock_pod.version = "v123"
        self.mock_work.pod = self.mock_pod
        Workload._set_version_label(self.mock_work)
        self.assertEqual(self.mock_work.labels[VER_LABEL], "v123")


class TestConfigMap(unittest.TestCase):
    """ UnitTests for ConfigMap Class """

    def setUp(self):
        self.inputs = {"data": {"get_property": ["SELF", "data"]}}

    def test_config_map_init(self):
        config = ConfigMap("app", "name", {}, {})
        self.assertFalse(config.spec)
        self.assertNotIn(VER_LABEL, config.manifest["metadata"]["labels"])

    def test_config_map_data_no_properties(self):
        config = ConfigMap("app", "name", self.inputs, {})
        self.assertFalse(config.manifest.get("data"))
        self.assertFalse(config.manifest.get("binaryData"))

    def test_config_map_data_with_properties(self):
        config = ConfigMap(
            "app", "name", self.inputs, {"data": {"some": "data"}}
        )
        self.assertFalse(config.manifest.get("binaryData"))
        self.assertEqual({"some": "data"}, config.manifest.get("data"))


class TestService(unittest.TestCase):
    """ UnitTests for Service Class """

    def setUp(self):
        self.svc = Service("app", "name", "mylabel", "NodePort")

    def test_service_init(self):
        self.assertNotIn(
            VER_LABEL, self.svc.manifest["metadata"]["labels"],
        )
        self.assertTrue(self.svc.spec["type"] == "NodePort" == self.svc.type)
        self.assertEqual(self.svc.manifest["kind"], "Service")

    def test_service_update_namespace(self):
        self.svc.update_namespace("nondefault")
        self.assertTrue(
            self.svc.namespace
            == self.svc.manifest["metadata"]["namespace"]
            == "nondefault"
        )

    def test_service_update_spec(self):
        self.assertNotIn("ports", self.svc.spec)
        port_mock = Mock(cluster_ip=None)
        self.svc.update_spec(port_mock)
        self.assertIn("ports", self.svc.spec)
        self.assertIn("protocol", self.svc.spec["ports"][0])
        self.assertNotIn("clusterIP", self.svc.spec)
        port_mock = Mock(cluster_ip="123.456", protocol=None)
        self.svc.update_spec(port_mock)
        self.assertIn("clusterIP", self.svc.spec)
        self.assertIn("port", self.svc.spec["ports"][1])
        self.assertNotIn("protocol", self.svc.spec["ports"][1])

    def test_get_port_without_name(self):
        port_dict = {"port": "888"}
        self.assertEqual("888-tcp", service.get_port_spec(port_dict).name)

    def test_get_port_without_port_without_name_with_udp(self):
        port_dict = {"targetPort": "888", "protocol": "UDP"}
        self.assertEqual("888-udp", service.get_port_spec(port_dict).name)

    def test_get_port_without_port_with_target(self):
        port_dict = {"targetPort": "888"}
        self.assertEqual("888", service.get_port_spec(port_dict).port)

    def test_get_port_without_port(self):
        with self.assertRaises(KeyError):
            service.get_port_spec({})

    def test_validate_port_cluster_ip(self):
        mock_port = Mock(cluster_ip="192.168.1.1")
        with self.assertRaises(ValueError):
            service._validate_port_spec(mock_port)

    def test_validate_port_node_port(self):
        mock_port = Mock(cluster_ip="10.96.1.1", node_port="29000")
        with self.assertRaises(ValueError):
            service._validate_port_spec(mock_port)


class TestVolume(unittest.TestCase):
    """ UnitTests for PV Class """

    def setUp(self):
        self.vol = PersistentVolume("app", "name", {"dataSource": "x"}, {})

    def test_clear_non_pv_keys(self):
        self.assertFalse(self.vol.namespace)
        self.assertNotIn(VER_LABEL, self.vol.labels)
        self.assertNotIn("namespace", self.vol.manifest["metadata"])

    def test_resolve_get_property(self):
        inputs = {
            "spec": {"hostPath": {"path": {"get_property": ["SELF", "path"]}}}
        }
        vol = PersistentVolume("app", "name", inputs, {"path": "y"})
        self.assertEqual(vol.spec["hostPath"]["path"], "y")

    def test_pv_defaults(self):
        self.assertTrue(self.vol.size)
        self.assertTrue(self.vol.spec.get("accessModes"))
        self.assertTrue(self.vol.spec.get("capacity"))

    def test_popped_pvc_spec(self):
        self.assertFalse(self.vol.manifest.get("dataSource"))
        self.assertTrue(self.vol.pvc_spec["spec"].get("dataSource"))

    def test_borrowed_accessmodes_pvc_spec(self):
        inputs = {"spec": {"accessModes": ["read", "write"]}}
        vol = PersistentVolume("app", "name", inputs, {})
        self.assertIn("read", vol.pvc_spec["spec"]["accessModes"])
        self.assertIn("write", vol.pvc_spec["spec"]["accessModes"])

    def test_overwrite_accessmodes_pvc_spec(self):
        inputs = {
            "accessModes": ["none"],
            "spec": {"accessModes": ["read", "write"]},
        }
        vol = PersistentVolume("app", "name", inputs, {})
        self.assertNotIn("read", vol.pvc_spec["spec"]["accessModes"])
        self.assertNotIn("write", vol.pvc_spec["spec"]["accessModes"])
        self.assertIn("none", vol.pvc_spec["spec"]["accessModes"])

    def test_pvc_get_spec(self):
        pvc = PersistentVolumeClaim("app", "name", self.vol.pvc_spec, "1Gi")
        self.assertIn(("dataSource", "x"), pvc.spec.items())

    def test_pvc_defaults(self):
        pvc = PersistentVolumeClaim("app", "name", self.vol.pvc_spec, "1Gi")
        self.assertTrue(pvc.spec.get("resources"))
        self.assertTrue(pvc.spec.get("accessModes"))
        self.assertTrue(pvc.spec.get("selector"))


class TestLocalADT(unittest.TestCase):
    """ Tests for local ADTs """

    def test_local(self):
        tpl = ToscaTemplate("tests/templates/tosca.yaml")
        self.adaptor = KubernetesAdaptor(
            "local_K8sAdaptor",
            {"volume": "tests/output/"},
            dryrun=False,
            validate=False,
            template=tpl,
        )
        self.adaptor.translate(write_files=True)


class TestMasterDemos(unittest.TestCase):
    """ Tests for Demos on Master branch """

    BRANCH = "master"
    WRITE = False

    def test_cqueue_demo(self):
        tpl = ToscaTemplate(
            f"https://raw.githubusercontent.com/micado-scale/ansible-micado/{self.BRANCH}/demos/cqueue/cqueue_ec2.yaml",
            a_file=False,
        )
        self.adaptor = KubernetesAdaptor(
            f"cqueue-{self.BRANCH}_K8sAdaptor",
            {"volume": "tests/output/"},
            dryrun=False,
            validate=False,
            template=tpl,
        )
        self.adaptor.translate(write_files=self.WRITE)

    def test_nginx_demo(self):
        tpl = ToscaTemplate(
            f"https://raw.githubusercontent.com/micado-scale/ansible-micado/{self.BRANCH}/demos/nginx/nginx_ec2.yaml",
            a_file=False,
        )
        self.adaptor = KubernetesAdaptor(
            f"nginx-{self.BRANCH}_K8sAdaptor",
            {"volume": "tests/output/"},
            dryrun=False,
            validate=False,
            template=tpl,
        )
        self.adaptor.translate(write_files=self.WRITE)

    def test_wordpress_demo(self):
        tpl = ToscaTemplate(
            f"https://raw.githubusercontent.com/micado-scale/ansible-micado/{self.BRANCH}/demos/wordpress/wordpress_ec2.yaml",
            a_file=False,
        )
        self.adaptor = KubernetesAdaptor(
            f"wordpress-{self.BRANCH}_K8sAdaptor",
            {"volume": "tests/output/"},
            dryrun=False,
            validate=False,
            template=tpl,
        )
        self.adaptor.translate(write_files=self.WRITE)


class TestDevDemos(TestMasterDemos):
    """ Tests for Demos on Dev branch"""

    BRANCH = "develop"
