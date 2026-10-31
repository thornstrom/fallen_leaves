variable "subscription_id" {
  type = string
}

variable "location" {
  type    = string
  default = "swedencentral"
}

variable "allowed_rdp_cidrs" {
  description = "Adresser som får ansluta med RDP, t.ex. [\"<din publika IP>/32\"] (curl -s ifconfig.me)."
  type        = list(string)

  validation {
    condition     = length(var.allowed_rdp_cidrs) > 0 && !contains(var.allowed_rdp_cidrs, "0.0.0.0/0")
    error_message = "Ange minst en adress, och öppna inte RDP för hela internet."
  }
}

variable "admin_username" {
  type    = string
  default = "fladmin"
}

variable "vm_size" {
  description = "Power BI Desktop behöver minst 8 GB minne."
  type        = string
  default     = "Standard_B2ms"
}

variable "shutdown_time" {
  description = "Tid (HHMM, svensk tid) då VM:en stängs av varje dag."
  type        = string
  default     = "2200"
}
