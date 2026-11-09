"""The single source of truth for categorical values.

Everything that is allowed to reach GA4 is a small fixed list defined here:
actions, modules, surfaces, channels. Because they are closed lists (Enums),
free text, such as a company name, cannot sneak into those fields.
"""
from enum import Enum


class Action(str, Enum):
    CREATE = "create"
    SIGN = "sign"
    UPLOAD = "upload"
    RECEIVE = "receive"
    PAY = "pay"
    APPROVE = "approve"


class Module(str, Enum):
    INVOICES = "invoices"
    CONTRACTS = "contracts"
    LIEN_WAIVERS = "lien_waivers"
    BILLS = "bills"
    CHANGE_ORDERS = "change_orders"


class Surface(str, Enum):
    WEB = "web"
    MOBILE = "mobile"
    API = "api"


class Channel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    INTEGRATION = "integration"


# Tracking plan: internal event name -> (action, module).
# An event that is not listed here can never be exported ("fail closed").
EVENT_MAP: dict[str, tuple[Action, Module]] = {
    "invoice_created":       (Action.CREATE,  Module.INVOICES),
    "contract_signed":       (Action.SIGN,    Module.CONTRACTS),
    "lien_waiver_uploaded":  (Action.UPLOAD,  Module.LIEN_WAIVERS),
    "bill_received":         (Action.RECEIVE, Module.BILLS),
    "bill_paid":             (Action.PAY,     Module.BILLS),
    "change_order_approved": (Action.APPROVE, Module.CHANGE_ORDERS),
}
