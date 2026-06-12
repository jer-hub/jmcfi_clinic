"""Pharmacy views — re-exported for urls.py compatibility."""

from pharmacy.views.api import api_batches_for_medicine, api_medicine_detail
from pharmacy.views.dashboard import pharmacy_dashboard
from pharmacy.views.inventory import (
    batch_create,
    batch_edit,
    batch_list,
    category_create,
    category_delete,
    category_edit,
    category_list,
    medicine_create,
    medicine_detail,
    medicine_edit,
    medicine_list,
)
from pharmacy.views.operations import (
    audit_log_list,
    dispensing_create,
    dispensing_list,
    stock_adjustment_create,
    stock_adjustment_list,
)
from pharmacy.views.procurement import (
    purchase_order_approve,
    purchase_order_create,
    purchase_order_detail,
    purchase_order_edit,
    purchase_order_list,
    purchase_order_receive,
    purchase_order_submit,
    supplier_create,
    supplier_detail,
    supplier_edit,
    supplier_list,
)
from pharmacy.views.reports import compliance_report, cost_analysis

__all__ = [
    'api_batches_for_medicine',
    'api_medicine_detail',
    'audit_log_list',
    'batch_create',
    'batch_edit',
    'batch_list',
    'category_create',
    'category_delete',
    'category_edit',
    'category_list',
    'compliance_report',
    'cost_analysis',
    'dispensing_create',
    'dispensing_list',
    'medicine_create',
    'medicine_detail',
    'medicine_edit',
    'medicine_list',
    'pharmacy_dashboard',
    'purchase_order_approve',
    'purchase_order_create',
    'purchase_order_detail',
    'purchase_order_edit',
    'purchase_order_list',
    'purchase_order_receive',
    'purchase_order_submit',
    'stock_adjustment_create',
    'stock_adjustment_list',
    'supplier_create',
    'supplier_detail',
    'supplier_edit',
    'supplier_list',
]
