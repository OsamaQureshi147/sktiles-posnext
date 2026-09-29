# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

"""Create Quotations from the POS cart."""

import json

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, nowdate

# Cart item fields that exist on Quotation Item
QUOTATION_ITEM_FIELDS = (
	"item_code",
	"item_name",
	"qty",
	"uom",
	"conversion_factor",
	"rate",
	"price_list_rate",
	"discount_percentage",
	"discount_amount",
	"warehouse",
	"is_free_item",
)


def _get_valid_till(pos_profile_doc, transaction_date):
	"""Validity from the POS Profile, else CRM Settings, else one month (as the Quotation form does)."""
	days = cint(pos_profile_doc.get("posa_quotation_validity_days"))
	if days <= 0:
		days = cint(frappe.db.get_single_value("CRM Settings", "default_valid_till"))
	return add_days(transaction_date, days) if days > 0 else add_months(transaction_date, 1)


@frappe.whitelist()
def create_quotation(data):
	"""
	Create and submit a Quotation from the POS cart.

	Args:
		data: dict / JSON with pos_profile, customer, items (as formatted for
			invoice submission) and optional discount_amount.

	Returns:
		dict: name, grand_total, valid_till of the submitted Quotation
	"""
	data = json.loads(data) if isinstance(data, str) else data

	pos_profile = data.get("pos_profile")
	customer = data.get("customer")
	items = data.get("items") or []

	if not pos_profile:
		frappe.throw(_("POS Profile is required"))
	if not customer:
		frappe.throw(_("Customer is required"))
	if not items:
		frappe.throw(_("Cart is empty"))

	has_access = frappe.db.exists("POS Profile User", {"parent": pos_profile, "user": frappe.session.user})
	if not has_access and not frappe.has_permission("Quotation", "create"):
		frappe.throw(_("You don't have access to this POS Profile"))

	pos_profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
	if not cint(pos_profile_doc.get("posa_allow_quotation")):
		frappe.throw(_("Quotations are not enabled for POS Profile {0}").format(pos_profile))

	transaction_date = nowdate()
	quotation = frappe.get_doc(
		{
			"doctype": "Quotation",
			"quotation_to": "Customer",
			"party_name": customer,
			"order_type": "Sales",
			"company": pos_profile_doc.company,
			"currency": pos_profile_doc.currency,
			"selling_price_list": pos_profile_doc.selling_price_list,
			"transaction_date": transaction_date,
			"valid_till": _get_valid_till(pos_profile_doc, transaction_date),
			"taxes_and_charges": pos_profile_doc.taxes_and_charges,
			"tax_category": pos_profile_doc.get("tax_category"),
			"discount_amount": flt(data.get("discount_amount")),
			# Rates and discounts are computed by the POS (offers already applied)
			"ignore_pricing_rule": 1,
			"items": [
				{field: item.get(field) for field in QUOTATION_ITEM_FIELDS if item.get(field) is not None}
				for item in items
			],
		}
	)

	if pos_profile_doc.get("branch") and quotation.meta.has_field("branch"):
		quotation.branch = pos_profile_doc.branch

	quotation.flags.ignore_permissions = True
	quotation.set_missing_values(for_validate=True)
	if not quotation.get("taxes"):
		quotation.append_taxes_from_master()
	quotation.calculate_taxes_and_totals()
	quotation.insert()
	quotation.submit()

	return {
		"name": quotation.name,
		"grand_total": quotation.grand_total,
		"valid_till": quotation.valid_till,
	}
