from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


# ─── Medicine / Product Catalog ──────────────────────────────────────────────

class MedicineCategory(models.Model):
    """Categories for organizing medicines (e.g., Analgesic, Antibiotic, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Medicine categories'

    def __str__(self):
        return self.name


class Medicine(models.Model):
    """Master record for a medicine or supply item."""
    UNIT_CHOICES = [
        ('tablet', 'Tablet'),
        ('capsule', 'Capsule'),
        ('bottle', 'Bottle'),
        ('vial', 'Vial'),
        ('tube', 'Tube'),
        ('sachet', 'Sachet'),
        ('piece', 'Piece'),
        ('box', 'Box'),
        ('pack', 'Pack'),
        ('ml', 'Milliliter (mL)'),
        ('mg', 'Milligram (mg)'),
        ('roll', 'Roll'),
        ('pair', 'Pair'),
        ('set', 'Set'),
    ]

    name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True, default='')
    brand_name = models.CharField(max_length=200, blank=True, default='')
    category = models.ForeignKey(
        MedicineCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='medicines'
    )
    description = models.TextField(blank=True, default='')
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='tablet')
    strength = models.CharField(
        max_length=50, blank=True, default='',
        help_text='e.g., 500mg, 250mg/5ml'
    )
    requires_prescription = models.BooleanField(default=False)
    reorder_level = models.PositiveIntegerField(
        default=10,
        help_text='Alert when stock falls below this quantity'
    )
    max_stock_level = models.PositiveIntegerField(
        default=500,
        help_text='Alert when stock exceeds this quantity'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        label = self.name
        if self.strength:
            label += f' ({self.strength})'
        return label

    @property
    def current_stock(self):
        """Sum of all non-expired batch quantities."""
        return sum(
            b.quantity for b in self.batches.filter(
                quantity__gt=0, expiry_date__gt=timezone.now().date()
            )
        )

    @property
    def total_stock(self):
        """Sum of all batch quantities (including near-expiry)."""
        return sum(b.quantity for b in self.batches.filter(quantity__gt=0))

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level

    @property
    def is_overstocked(self):
        return self.current_stock > self.max_stock_level


# ─── Batch & Expiry Management ───────────────────────────────────────────────

class Batch(models.Model):
    """A specific batch of a medicine with expiry tracking."""
    medicine = models.ForeignKey(
        Medicine, on_delete=models.CASCADE, related_name='batches'
    )
    batch_number = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Cost per unit in PHP'
    )
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    received_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expiry_date']
        verbose_name_plural = 'Batches'
        unique_together = ['medicine', 'batch_number']

    def __str__(self):
        return f"{self.medicine.name} – Batch {self.batch_number}"

    @property
    def is_expired(self):
        return self.expiry_date <= timezone.now().date()

    @property
    def is_near_expiry(self):
        """Within 90 days of expiry."""
        return (
            not self.is_expired
            and self.expiry_date <= timezone.now().date() + timezone.timedelta(days=90)
        )

    @property
    def total_value(self):
        return self.quantity * self.unit_cost

    @property
    def days_until_expiry(self):
        delta = self.expiry_date - timezone.now().date()
        return delta.days


# ─── Supplier / Procurement ──────────────────────────────────────────────────

class Supplier(models.Model):
    """Supplier / vendor record."""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    address = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    """A purchase order sent to a supplier."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]

    order_number = models.CharField(max_length=50, unique=True, blank=True)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='purchase_orders'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    ordered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='pharmacy_orders_placed'
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pharmacy_orders_approved'
    )
    order_date = models.DateField(default=timezone.now)
    expected_delivery = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"PO-{self.order_number} ({self.supplier.name})"

    @property
    def total_cost(self):
        return sum(item.line_total for item in self.items.all())

    def save(self, *args, **kwargs):
        if not self.order_number:
            last = PurchaseOrder.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            self.order_number = f"{timezone.now().strftime('%Y%m')}-{next_id:04d}"
        super().save(*args, **kwargs)


class PurchaseOrderItem(models.Model):
    """Line item on a purchase order."""
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='items'
    )
    medicine = models.ForeignKey(
        Medicine, on_delete=models.CASCADE, related_name='order_items'
    )
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Cost per unit in PHP'
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.medicine.name} x{self.quantity_ordered}"

    @property
    def line_total(self):
        return self.quantity_ordered * self.unit_cost


# ─── Dispensing & Prescription Integration ───────────────────────────────────

class Dispensing(models.Model):
    """Record of medicine dispensed to a patient / student."""
    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='pharmacy_dispensings'
    )
    dispensed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='pharmacy_dispensed_by'
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name='dispensings'
    )
    quantity = models.PositiveIntegerField()
    prescription_reference = models.CharField(
        max_length=200, blank=True, default='',
        help_text='Doctor prescription or medical record reference'
    )
    prescribing_doctor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pharmacy_prescriptions',
        limit_choices_to={'role__in': ['staff', 'doctor']}
    )
    reason = models.TextField(blank=True, default='')
    dispensed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dispensed_at']

    def __str__(self):
        return (
            f"{self.batch.medicine.name} x{self.quantity} → "
            f"{self.patient.first_name} {self.patient.last_name}"
        )


# ─── Stock Adjustment / Audit Log ────────────────────────────────────────────

class StockAdjustment(models.Model):
    """Manual stock adjustments and explanations for auditing."""
    REASON_CHOICES = [
        ('expired', 'Expired – Disposed'),
        ('damaged', 'Damaged / Broken'),
        ('correction', 'Inventory Correction'),
        ('returned', 'Returned to Supplier'),
        ('donated', 'Donated'),
        ('other', 'Other'),
    ]

    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name='adjustments'
    )
    adjusted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='pharmacy_adjustments'
    )
    quantity_change = models.IntegerField(
        help_text='Positive to add, negative to deduct'
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        direction = '+' if self.quantity_change > 0 else ''
        return (
            f"{self.batch.medicine.name} "
            f"{direction}{self.quantity_change} ({self.get_reason_display()})"
        )


# ─── Audit Trail ─────────────────────────────────────────────────────────────

class AuditLog(models.Model):
    """Immutable audit trail for every pharmacy transaction."""
    ACTION_CHOICES = [
        ('stock_in', 'Stock In (PO Received)'),
        ('dispensed', 'Dispensed'),
        ('adjustment', 'Stock Adjustment'),
        ('expired_disposed', 'Expired / Disposed'),
        ('medicine_added', 'Medicine Added'),
        ('order_created', 'Purchase Order Created'),
        ('order_approved', 'Purchase Order Approved'),
        ('order_received', 'Purchase Order Received'),
    ]

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='pharmacy_audit_logs'
    )
    medicine = models.ForeignKey(
        Medicine, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs'
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs'
    )
    quantity = models.IntegerField(default=0)
    details = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_action_display()}] {self.details[:80]}"
