variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "replication_type" {
  type    = string
  default = "LRS"
}

variable "gold_reader_object_ids" {
  description = "Entra ID object ID som får läsa gold-containern direkt, t.ex. Power BI-användare."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
