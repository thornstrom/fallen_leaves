variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "purge_protection_enabled" {
  type    = bool
  default = false
}

variable "secret_officer_object_ids" {
  description = "Object ID för personer som ska kunna sätta hemligheter (t.ex. Trafikverket-nyckeln)."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
