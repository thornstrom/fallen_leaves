variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "default_filesystem_id" {
  description = "https://<konto>.dfs.core.windows.net/<container>"
  type        = string
}

variable "default_container_id" {
  description = "Resource manager-ID för default-containern."
  type        = string
}

variable "gold_container_id" {
  description = "Resource manager-ID för gold-containern."
  type        = string
}

variable "allowed_ip_ranges" {
  description = "Brandväggsregler för Synapse-endpointen. GitHub-hostade runners har inga fasta IP-adresser, så standard är öppet; begränsa i prod om möjligt."
  type = map(object({
    start = string
    end   = string
  }))
  default = {
    AllowAll = { start = "0.0.0.0", end = "255.255.255.255" }
  }
}

variable "admin_object_ids" {
  description = "Object ID för användare som ska bli Synapse Administrator."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
