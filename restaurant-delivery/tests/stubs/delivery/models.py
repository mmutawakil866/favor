from django.db import models
class Delivery(models.Model):
    order = models.OneToOneField("orders.Order", on_delete=models.RESTRICT)
    status = models.CharField(max_length=20, default="ASSIGNED")
    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)