variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "storage_account_id" {
  description = "Data lake som access connectorn ska få skriva till."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
