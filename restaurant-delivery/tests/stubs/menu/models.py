from django.db import models
class FoodItem(models.Model):
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)