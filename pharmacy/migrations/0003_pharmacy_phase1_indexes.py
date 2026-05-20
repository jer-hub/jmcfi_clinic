import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacy', '0002_alter_auditlog_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dispensing',
            name='dispensed_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
        migrations.AddIndex(
            model_name='batch',
            index=models.Index(fields=['expiry_date', 'quantity'], name='pharm_batch_exp_qty_idx'),
        ),
        migrations.AddIndex(
            model_name='purchaseorder',
            index=models.Index(fields=['status', 'order_date'], name='pharm_po_status_ord_idx'),
        ),
        migrations.AddIndex(
            model_name='purchaseorder',
            index=models.Index(fields=['status', 'received_date'], name='pharm_po_status_rcv_idx'),
        ),
    ]
