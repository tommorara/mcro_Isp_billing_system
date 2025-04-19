from django.db import models

class Customer(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    data_usage = models.FloatField(default=0)  # MB
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name

class BillingRecord(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    billed_at = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.customer} - {self.amount}"