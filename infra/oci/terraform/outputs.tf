output "instance_id" {
  value = oci_core_instance.app.id
}

output "reserved_public_ip" {
  value = oci_core_public_ip.app.ip_address
}

output "ssh_command" {
  value = "ssh ubuntu@${oci_core_public_ip.app.ip_address}"
}

output "dns_record" {
  value = "Create an A record for the API hostname pointing to ${oci_core_public_ip.app.ip_address}"
}
