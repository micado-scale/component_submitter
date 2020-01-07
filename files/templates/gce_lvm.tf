variable "x" {
    default = "1"
}

variable "vm_name" {}
variable "project" {}
variable "region" {}
variable "machine_type" {}
variable "zone" {}
variable "image" {}
variable "network" {}
variable "ssh-keys" {}

provider "google" {
 credentials = "${file("accounts.json")}"
 project     = "${var.project}"
 region      = "${var.region}"
}

resource "google_compute_instance" "database" {
  name         = "${var.vm_name}"
  machine_type = "${var.machine_type}"
  zone         = "${var.zone}"

  boot_disk {
    initialize_params {
      image = "${var.image}"
    }
  }

  network_interface {
    network = "${var.network}"
    access_config {
    
    }
  }

  metadata = {
    ssh-keys = "ubuntu:${var.ssh-keys}"
    user-data = "${file("terrainit.yaml")}"
  }
 
  count = "${var.x}"
}