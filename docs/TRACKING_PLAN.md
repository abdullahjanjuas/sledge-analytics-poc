# Tracking plan (event dictionary)

One page that engineering and analytics both use. **If an event is not listed here, it is not exported to GA4.**

| Internal event | GA4 `action` | GA4 `module` | Stays internal only |
|---|---|---|---|
| `invoice_created` | create | invoices | amount, company, party name, tax ID |
| `contract_signed` | sign | contracts | amount, company, party name, tax ID |
| `lien_waiver_uploaded` | upload | lien_waivers | amount, company, party name, tax ID |
| `bill_received` | receive | bills | amount, company, party name, tax ID, `bill_id` |
| `bill_paid` | pay | bills | amount, company, party name, tax ID, `bill_id`, days to pay |
| `change_order_approved` | approve | change_orders | amount, company, party name, tax ID |

Every GA4 event also carries:

| Field | Allowed values | Source |
|---|---|---|
| `surface` | web, mobile, api | where the action happened |
| `channel` | in_app, email, integration | how the work entered the product |
| `tenant_hash` | 32 hex chars | HMAC-SHA256(tenant_id, secret key) |

## Checklist for instrumenting a new feature
1. Add the event to `EVENT_MAP` in `src/taxonomy.py` (action + module). Add new enum values to `sql/01_schema.sql` too.
2. Decide which fields are internal-only. Default answer: everything except the five above.
3. Run `make test`. The enum/SQL consistency test and the canary tests must stay green.
4. Add a row to this table.
