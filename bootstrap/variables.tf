variable "subscription_id" {
  description = "Azure-subscription där projektet deployas."
  type        = string
}

variable "location" {
  description = "Azure-region."
  type        = string
  default     = "swedencentral"
}

variable "project" {
  description = "Kort projektnamn som används i resursnamn (endast gemener och siffror)."
  type        = string
  default     = "fallenleaves"

  validation {
    condition     = can(regex("^[a-z0-9]{3,12}$", var.project))
    error_message = "project får bara innehålla gemener och siffror, 3–12 tecken."
  }
}

variable "github_owner" {
  description = "GitHub-användare eller organisation som äger repot."
  type        = string
}

variable "github_repo" {
  description = "Namnet på GitHub-repot (utan ägare)."
  type        = string
  default     = "fallen_leaves"
}

variable "prod_reviewers" {
  description = "GitHub-användarnamn som måste godkänna deploy till prod."
  type        = list(string)
}
