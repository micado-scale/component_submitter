import unittest

from toscaparser.tosca_template import ToscaTemplate

import utils
import adaptors.k8s_adaptor as kutil

from abstracts.exceptions import AdaptorCritical

from adaptors.k8s_adaptor import KubernetesAdaptor
from adaptors.k8s_adaptor import Container
from adaptors.k8s_adaptor import Manifest
from adaptors.k8s_adaptor import WorkloadManifest
from adaptors.k8s_adaptor import ServiceManifest
from adaptors.k8s_adaptor import VolumeManifest
from adaptors.k8s_adaptor import ConfigMapManifest


class TestK8sTranslation(unittest.TestCase):
    """ UnitTests for micado_validator """

    def setUp(self):
        """ Setup Validator object and prep a bad TOSCA template """
        self.tpl = ToscaTemplate("tests/templates/tosca_074.yaml")
        self.docker = self.getContainerbyName("docker-container")

    def getContainerbyName(self, name):
        """ query me """
        [container] = [x for x in self.tpl.nodetemplates if x.name == name]
        return container

    """ Test Container class """

    def test_drop_swarm_option(self):
        test = Container(self.docker, self.tpl.repositories)
        self.assertTrue(self.docker.get_property_value("stop_signal"))
        self.assertFalse(test.spec.get("stop_signal"))

    def test_drop_pod_option(self):
        test = Container(self.docker, self.tpl.repositories)
        self.assertTrue(self.docker.get_property_value("pid"))
        self.assertFalse(test.spec.get("pid"))
        self.assertIsNotNone(test.ports)

    def test_convert_environment(self):
        test = Container(self.docker, self.tpl.repositories)
        self.assertTrue(test.spec.get("env"))
        self.assertIsInstance(test.spec.get("env"), list)
        [env] = [x for x in test.spec.get("env") if x.get("name") == "VARTWO"]
        self.assertTrue(env)
        self.assertEqual(env.get("value"), 456)

    def test_convert_entrypoint(self):
        test = Container(self.docker, self.tpl.repositories)
        self.assertTrue(test.spec.get("command"))
        self.assertIsInstance(test.spec.get("command"), list)
        self.assertEqual(test.spec.get("command")[0], "stress")
        self.assertEqual(test.spec.get("command")[2], "50")

    def test_get_image_property(self):
        test = Container(self.docker, self.tpl.repositories)
        self.assertEqual(test.spec.get("image"), "myimage:v123")
        self.assertEqual(test.labels.get("app.kubernetes.io/version"), "v123")

    def test_get_image_artifact(self):
        cont = self.getContainerbyName("docker-container-with-artifact_bad_name")
        test = Container(cont, self.tpl.repositories)
        self.assertEqual(test.spec.get("image"), "myimage:v5000")
        self.assertEqual(test.labels.get("app.kubernetes.io/version"), "v5000")

    def test_get_image_artifact_with_custom_repo(self):
        cont = self.getContainerbyName("docker-container-with-custom-repo-artifact")
        test = Container(cont, self.tpl.repositories)
        self.assertEqual(test.spec.get("image"), "https://test.hub.com/myimage:v123")
        self.assertEqual(test.labels.get("app.kubernetes.io/version"), "v123")

    """ Test Manifest class """

    def test_manual_labels(self):
        spec = {"metadata": {"labels": {"test": "stay"}}}
        test = Manifest("xx", "xx", spec)
        self.assertTrue("test" in test.resource["metadata"]["labels"])

    def test_automatic_labels_no_overwrite(self):
        spec = {"metadata": {"labels": {"app.kubernetes.io/name": "zz"}}}
        test = Manifest("xx", "xx", spec)
        self.assertTrue(
            "xx" in test.resource["metadata"]["labels"]["app.kubernetes.io/name"]
        )

    def test_manual_kind(self):
        spec = {"kind": "notreal"}
        test = Manifest("xx", "xx", spec)
        self.assertTrue("notreal" in test.resource["kind"])

    def test_manual_spec(self):
        spec = {"spec": {"subdomain": "mysubdomain"}}
        test = Manifest("xx", "xx", spec)
        self.assertTrue(test.resource.get("spec"))

    def test_automatic_spec(self):
        spec = {"kind": "doesnt-matter", "subdomain": "mysubdomain"}
        test = Manifest("xx", "xx", spec)
        self.assertTrue(test.resource.get("spec").get("subdomain"))

    """ Test WorkloadManifest Class """

    def test_workload_super(self):
        spec = {"create": {"kind": "doesnt-matter", "strategy": "Recreate"}}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertTrue(test.resource.get("spec").get("strategy"))

    def test_workload_namespace(self):
        spec = {"create": {"metadata": {"namespace": "my-ns"}}}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(test.resource.get("metadata").get("namespace"), "my-ns")
        self.assertEqual(test.namespace, "my-ns")

    def test_workload_spec_to_pod(self):
        spec = {"create": {"kind": "doesnt-matter", "subdomain": "mysubdomain"}}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertTrue(
            test.resource.get("spec").get("template").get("spec").get("subdomain")
        )

    def test_manual_pod_spec_in_create(self):
        spec = {
            "create": {"spec": {"template": {"spec": {"subdomain": "mysubdomain"}}}}
        }
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertTrue(test.pod.get("spec").get("subdomain"))

    def test_manual_pod_spec_in_configure(self):
        spec = {"configure": {"spec": {"subdomain": "mysubdomain"}}}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertTrue(test.pod.get("spec").get("subdomain"))

    def test_auto_pod_spec_in_configure(self):
        spec = {"configure": {"metadata": {}, "subdomain": "mysubdomain"}}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertTrue(test.pod.get("spec").get("subdomain"))

    def test_custom_pod_label(self):
        spec = {"configure": {"metadata": {"labels": {"custom": "label"}}}}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertTrue(test.pod.get("metadata").get("labels").get("custom"))

    def test_custom_pod_label_no_overwrite(self):
        spec = {
            "configure": {"metadata": {"labels": {"app.kubernetes.io/name": "newname"}}}
        }
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertNotEqual(
            test.pod.get("metadata").get("labels").get("app.kubernetes.io/name"),
            "newname",
        )

    def test_pod_property_from_container(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertTrue(test.pod.get("spec").get("hostPID"))

    def test_no_selector_for_jobs(self):
        spec = {"create": {"kind": "Job"}}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertFalse(test.resource.get("spec").get("selector"))

    def test_no_template_for_pod(self):
        spec = {"create": {"kind": "Pod"}}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertFalse(test.resource.get("spec").get("template"))

    def test_template_selector_container_for_workloads(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertTrue(test.resource.get("spec").get("template"))
        self.assertTrue(test.resource.get("spec").get("selector"))
        self.assertEqual(len(test.pod.get("spec").get("containers")), 1)

    def test_multiple_containers_to_workload(self):
        cont = self.getContainerbyName("add-container-to-workload")
        spec = {}
        test = WorkloadManifest("myapp", cont, spec, self.tpl.repositories)
        self.assertEqual(len(test.pod.get("spec").get("containers")), 2)

    def test_container_to_workload_label_no_overwrite(self):
        cont = self.getContainerbyName("add-container-to-workload")
        spec = {}
        test = WorkloadManifest("myapp", cont, spec, self.tpl.repositories)
        self.assertEqual(
            test.resource.get("metadata")
            .get("labels")
            .get("app.kubernetes.io/version"),
            "v1000",
        )

    def test_multiple_containers_to_bare_pod(self):
        cont = self.getContainerbyName("add-containers-to-bare-pod")
        spec = {}
        test = WorkloadManifest("myapp", cont, spec, self.tpl.repositories)
        self.assertEqual(len(test.pod.get("spec").get("containers")), 2)

    def test_containers_to_pod_label_first_wins(self):
        cont = self.getContainerbyName("add-containers-to-bare-pod")
        spec = {}
        test = WorkloadManifest("myapp", cont, spec, self.tpl.repositories)
        self.assertEqual(
            test.resource.get("metadata")
            .get("labels")
            .get("app.kubernetes.io/version"),
            "v123",
        )

    """ Test services, ServiceManifest """

    def test_create_container_port(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(
            test.pod["spec"]["containers"][0].get("ports")[0].get("containerPort"), 1234
        )

    def test_create_host_port(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(
            test.pod["spec"]["containers"][0].get("ports")[1].get("containerPort"), 5000
        )
        self.assertEqual(
            test.pod["spec"]["containers"][0].get("ports")[1].get("hostPort"), 5050
        )

    def test_create_service_with_docker_long_syntax(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(
            len(
                test.services.get("docker-container").resource.get("spec").get("ports")
            ),
            1,
        )
        self.assertEqual(
            test.services.get("docker-container")
            .resource.get("spec")
            .get("ports")[0]
            .get("port"),
            4000,
        )
        self.assertEqual(
            test.services.get("docker-container")
            .resource.get("spec")
            .get("ports")[0]
            .get("protocol"),
            "UDP",
        )

    def test_create_service_with_multiple_ports(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(
            len(
                test.services.get("docker-container-nodeport")
                .resource.get("spec")
                .get("ports")
            ),
            2,
        )

    def test_create_service_with_auto_node_port(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(
            test.services.get("docker-container-nodeport").type, "NodePort"
        )
        self.assertEqual(
            test.services.get("docker-container-nodeport")
            .resource.get("spec")
            .get("type"),
            "NodePort",
        )
        self.assertEqual(
            test.services.get("docker-container-nodeport")
            .resource.get("spec")
            .get("ports")[0]
            .get("targetPort"),
            "3000",
        )
        self.assertEqual(
            test.services.get("docker-container-nodeport")
            .resource.get("spec")
            .get("ports")[0]
            .get("port"),
            3030,
        )
        self.assertEqual(
            test.services.get("docker-container-nodeport")
            .resource.get("spec")
            .get("ports")[0]
            .get("nodePort"),
            30000,
        )

    def test_create_service_with_custom_name(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(
            len(test.services.get("my-custom-name").resource.get("spec").get("ports")),
            1,
        )
        self.assertEqual(
            test.services.get("my-custom-name")
            .resource.get("spec")
            .get("ports")[0]
            .get("port"),
            1000,
        )
        self.assertEqual(
            test.services.get("my-custom-name")
            .resource.get("spec")
            .get("ports")[0]
            .get("nodePort"),
            30006,
        )

    def test_create_service_overwrite_type(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(
            len(
                test.services.get("docker-container-loadbalancer")
                .resource.get("spec")
                .get("ports")
            ),
            1,
        )
        self.assertEqual(
            test.services.get("docker-container-loadbalancer").type, "LoadBalancer"
        )
        self.assertEqual(
            test.services.get("docker-container-loadbalancer")
            .resource.get("spec")
            .get("type"),
            "LoadBalancer",
        )
        self.assertEqual(
            test.services.get("docker-container-loadbalancer")
            .resource.get("spec")
            .get("ports")[0]
            .get("port"),
            1000,
        )
        self.assertEqual(
            test.services.get("docker-container-loadbalancer")
            .resource.get("spec")
            .get("ports")[0]
            .get("nodePort"),
            30009,
        )

    def test_create_service_use_parent_namespace(self):
        cont = self.getContainerbyName("docker-by-kube")
        spec = {"create": {"metadata": {"namespace": "custom-ns"}}}
        test = WorkloadManifest("myapp", cont, spec, self.tpl.repositories)
        self.assertEqual(test.services.get("docker-by-kube").namespace, "custom-ns")
        self.assertEqual(
            test.services.get("docker-by-kube")
            .resource.get("metadata")
            .get("namespace"),
            "custom-ns",
        )

    def test_create_service_use_service_namespace(self):
        cont = self.getContainerbyName("docker-by-kube-service")
        spec = {"create": {"metadata": {"namespace": "custom-ns"}}}
        test = WorkloadManifest("myapp", cont, spec, self.tpl.repositories)
        self.assertEqual(test.services.get("docker-by-kube-service").namespace, "service-ns")
        self.assertEqual(
            test.services.get("docker-by-kube-service")
            .resource.get("metadata")
            .get("namespace"),
            "service-ns",
        )

    """ Test volumes, requirements, VolumeManifest """

    def test_get_hosted_on(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertIn("nodeAffinity", test.pod.get("spec").get("affinity"))

    def test_attach_volume_to_pod(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        [mount] = [
            x
            for x in test.pod.get("spec").get("volumes")
            if x.get("name") == "fake-vol"
        ]
        [mount_abst] = [
            x
            for x in test.pod.get("spec").get("volumes")
            if x.get("name") == "fake-vol-abst"
        ]
        self.assertTrue(mount)
        self.assertTrue(mount_abst)

    def test_attach_volumes_configs_to_pods(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        self.assertEqual(
            len(test.pod.get("spec").get("containers")[0].get("volumeMounts")), 6
        )

    def test_attach_volume_default_path(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        [mount] = [
            x
            for x in test.pod.get("spec").get("containers")[0].get("volumeMounts")
            if x.get("name") == "fake-vol"
        ]
        self.assertEqual(mount.get("mountPath"), "/etc/micado/volumes")

    def test_attach_volume_path_in_volume_interface(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        [mount] = [
            x
            for x in test.pod.get("spec").get("containers")[0].get("volumeMounts")
            if x.get("name") == "fake-vol-interface"
        ]
        self.assertEqual(mount.get("mountPath"), "getthispath")

    def test_attach_volume_path_in_req(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        [mount] = [
            x
            for x in test.pod.get("spec").get("containers")[0].get("volumeMounts")
            if x.get("name") == "fake-vol-abst"
        ]
        self.assertEqual(mount.get("mountPath"), "usethisone")

    def test_attach_volume_path_in_volume_properties(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        [mount] = [
            x
            for x in test.pod.get("spec").get("containers")[0].get("volumeMounts")
            if x.get("name") == "fake-vol-abst-no-rel"
        ]
        self.assertEqual(mount.get("mountPath"), "volinprop")

    def test_attach_configs_to_pods(self):
        spec = {}
        test = WorkloadManifest("myapp", self.docker, spec, self.tpl.repositories)
        [mount] = [
            x
            for x in test.pod.get("spec").get("containers")[0].get("volumeMounts")
            if x.get("name") == "fake-config-volume"
        ]
        [mount_abst] = [
            x
            for x in test.pod.get("spec").get("containers")[0].get("volumeMounts")
            if x.get("name") == "fake-config-abst-volume"
        ]
        self.assertTrue(mount)
        self.assertTrue(mount_abst)
        [mount] = [
            x
            for x in test.pod.get("spec").get("volumes")
            if x.get("name") == "fake-config-volume"
        ]
        [mount_abst] = [
            x
            for x in test.pod.get("spec").get("volumes")
            if x.get("name") == "fake-config-abst-volume"
        ]
        self.assertTrue(mount.get("configMap"))
        self.assertTrue(mount_abst.get("configMap"))

    def test_volume_manifest_PVC_only_from_interface(self):
        cont = self.getContainerbyName("fake-vol-abst")
        spec = {"configure": {"metadata": {"labels": {"custom": "label"}}}}
        test = VolumeManifest("myapp", cont, spec)
        self.assertTrue(test.resource.get("metadata").get("labels").get("custom"))

    def test_volume_manifest_PVC_and_PV_from_interface(self):
        cont = self.getContainerbyName("fake-vol-abst")
        spec = {"create": {"hostPath": "mypath"}, "configure": {"storageClassName": "rook"}}
        test = VolumeManifest("myapp", cont, spec)
        self.assertTrue(test.resource.get("spec").get("hostPath"))
        self.assertTrue(test.claim.get("spec").get("storageClassName"))

    def test_volume_manifest_spec_from_interface(self):
        cont = self.getContainerbyName("fake-vol-interface")
        spec = utils.get_lifecycle(cont, "Kubernetes")
        test = VolumeManifest("myapp", cont, spec)
        self.assertEqual(
            test.resource.get("spec").get("hostPath").get("path"), "getthispath"
        )

    def test_volume_manifest_spec_overwrite_from_interface(self):
        cont = self.getContainerbyName("fake-vol-interface")
        spec = utils.get_lifecycle(cont, "Kubernetes")
        test = VolumeManifest("myapp", cont, spec)
        self.assertEqual(len(test.resource.get("spec").get("accessModes")), 1)

    def test_volume_manifest_spec_from_property(self):
        cont = self.getContainerbyName("fake-vol-abst")
        spec = utils.get_lifecycle(cont, "Kubernetes")
        test = VolumeManifest("myapp", cont, spec)
        self.assertEqual(test.resource.get("spec").get("nfs").get("path"), "volinprop")

    def test_config_manifest_spec_overwrite_from_interface(self):
        cont = self.getContainerbyName("fake-config")
        spec = utils.get_lifecycle(cont, "Kubernetes")
        test = ConfigMapManifest("myapp", cont, spec)
        self.assertEqual(test.resource.get("binaryData"), {"bingoes": "here"})

    def test_config_manifest_spec_from_property(self):
        cont = self.getContainerbyName("fake-config-abst")
        spec = utils.get_lifecycle(cont, "Kubernetes")
        test = ConfigMapManifest("myapp", cont, spec)
        self.assertEqual(test.resource.get("data"), {"datagoes": "here"})

    """ Test module methods """

    def test_get_node_checks(self):
        cont = self.getContainerbyName("docker-container-with-artifact_bad_name")
        with self.assertRaises(AdaptorCritical):
            kutil._get_node(cont)

    def test_get_parent_interfaces(self):
        cont = self.getContainerbyName("daemonset-by-auto")
        test = utils.get_lifecycle(cont, "Kubernetes")
        self.assertEqual(test.get("create").get("kind"), "DaemonSet")

    def test_overwrite_parent_interfaces(self):
        cont = self.getContainerbyName("overwrite-with-auto")
        test = utils.get_lifecycle(cont, "Kubernetes")
        self.assertEqual(test.get("create").get("kind"), "Deployment")

