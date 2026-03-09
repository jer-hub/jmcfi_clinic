from django.contrib import admin
from .models import (
    Medicine, MedicineCategory, Batch, Supplier,
    PurchaseOrder, PurchaseOrderItem, Dispensing,
    StockAdjustment, AuditLog,
)


@admin.register(MedicineCategory)
class MedicineCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name']
    ordering = ['name']


class BatchInline(admin.TabularInline):
    model = Batch
    extra = 0
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ['name', 'generic_name', 'brand_name', 'category', 'unit', 'strength',
                    'requires_prescription', 'reorder_level', 'is_active']
    list_filter = ['category', 'unit', 'requires_prescription', 'is_active']
    search_fields = ['name', 'generic_name', 'brand_name']
    ordering = ['name']
    inlines = [BatchInline]


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['medicine', 'batch_number', 'quantity', 'unit_cost',
                    'expiry_date', 'received_date']
    list_filter = ['medicine__category', 'expiry_date']
    search_fields = ['batch_number', 'medicine__name']
    ordering = ['expiry_date']
    date_hierarchy = 'expiry_date'


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'email', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'contact_person', 'email']
    ordering = ['name']


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'supplier', 'status', 'ordered_by',
                    'order_date', 'expected_delivery', 'received_date']
    list_filter = ['status', 'supplier']
    search_fields = ['order_number', 'supplier__name']
    ordering = ['-order_date']
    date_hierarchy = 'order_date'
    inlines = [PurchaseOrderItemInline]


@admin.register(Dispensing)
class DispensingAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'batch', 'quantity', 'dispensed_by',
                    'prescribing_doctor', 'dispensed_at']
    list_filter = ['dispensed_at']
    search_fields = ['patient__first_name', 'patient__last_name',
                     'batch__medicine__name', 'prescription_reference']
    ordering = ['-dispensed_at']
    date_hierarchy = 'dispensed_at'


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['batch', 'quantity_change', 'reason', 'adjusted_by', 'created_at']
    list_filter = ['reason']
    search_fields = ['batch__medicine__name', 'notes']
    ordering = ['-created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'performed_by', 'medicine', 'quantity', 'created_at']
    list_filter = ['action']
    search_fields = ['details', 'medicine__name']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    readonly_fields = ['action', 'performed_by', 'medicine', 'batch',
                       'quantity', 'details', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
