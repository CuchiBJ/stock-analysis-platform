variable "tenancy_ocid" {
  description = "OCI tenancy OCID."
  type        = string
}

variable "compartment_ocid" {
  description = "Compartment in which the stack will be created."
  type        = string
}

variable "region" {
  description = "OCI home region, where Always Free resources must be created."
  type        = string
}

variable "ssh_public_key" {
  description = "OpenSSH public key used to access the ubuntu account."
  type        = string
  sensitive   = true
}

variable "availability_domain_number" {
  description = "Zero-based availability-domain index. Change it if A1 capacity is unavailable."
  type        = number
  default     = 0
}

variable "ssh_allowed_cidr" {
  description = "CIDR allowed to reach SSH. Prefer your public IP with /32."
  type        = string

  validation {
    condition     = can(cidrhost(var.ssh_allowed_cidr, 0))
    error_message = "ssh_allowed_cidr must be a valid CIDR such as 203.0.113.10/32."
  }
}

variable "instance_shape" {
  description = "Always Free eligible Ampere shape."
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "ocpus" {
  description = "OCPUs assigned to the VM. The current Always Free total is 2 OCPUs."
  type        = number
  default     = 2

  validation {
    condition     = var.ocpus > 0 && var.ocpus <= 2
    error_message = "Keep ocpus between 1 and 2 to remain within the current Always Free aggregate ceiling."
  }
}

variable "memory_in_gbs" {
  description = "Memory assigned to the VM. The current Always Free total is 12 GB."
  type        = number
  default     = 12

  validation {
    condition     = var.memory_in_gbs > 0 && var.memory_in_gbs <= 12
    error_message = "Keep memory_in_gbs at or below 12 to remain within the current Always Free aggregate ceiling."
  }
}

variable "boot_volume_size_in_gbs" {
  description = "Boot volume size. Counts against the tenancy's 200 GB Always Free block-volume pool."
  type        = number
  default     = 100

  validation {
    condition     = var.boot_volume_size_in_gbs >= 50 && var.boot_volume_size_in_gbs <= 200
    error_message = "boot_volume_size_in_gbs must be between 50 and 200. Check other volumes before using the full Always Free pool."
  }
}
