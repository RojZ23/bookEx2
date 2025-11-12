from django.contrib.auth.models import User
from django.db import models
from django.utils.timezone import now
from django.db.models import Avg
from decimal import Decimal

class MainMenu(models.Model):
   item = models.CharField(max_length=300, unique=True)
   link = models.CharField(max_length=300, unique=True)


   def __str__(self):
       return self.item

class Book(models.Model):
    is_exclusive = models.BooleanField(default=False)
    name = models.CharField(max_length=200)
    web = models.URLField(max_length=300)
    price = models.DecimalField(decimal_places=2, max_digits=8)
    publishdate = models.DateField(auto_now=True)
    picture = models.FileField(upload_to='uploads/')
    pic_path = models.CharField(max_length=300, editable=False, blank=True)
    username = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    favorites = models.ManyToManyField(User, related_name='favorite_books', blank=True)
    quantity = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.picture:
            self.pic_path = self.picture.name  # relative path like 'uploads/filename.jpg'
            super().save(update_fields=['pic_path'])
            
    def __str__(self):
        return self.name

    @property
    def average_rating(self):
        avg = self.rate_set.aggregate(models.Avg('rating'))['rating__avg']
        return avg or 0


class ShoppingCart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    checked_out = models.BooleanField(default=False)  # marks if purchased

    def __str__(self):
        return f"{self.quantity} x {self.book.name} for {self.user.username}"


class Rate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(default=1)

class Comment(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return f'Comment by {self.user.username} on {self.book.name}'

class BookReturn(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    returned_at = models.DateTimeField(auto_now_add=True)

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('Regular', 'Regular User'),
        ('Publisher', 'Publisher'),
        ('Writer', 'Writer'),
    ]
    TIER_CHOICES = [
        ('Free', 'Free'),
        ('Bronze', 'Bronze Supporter'),
        ('Silver', 'Silver Supporter'),
        ('Gold', 'Gold Supporter'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Regular')
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='Free')
    subscription_start = models.DateField(null=True, blank=True)
    last_deduction_date = models.DateField(null=True, blank=True)
    balance = models.DecimalField(default=Decimal('0.00'), max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.username} - {self.role} ({self.tier})"

SUBSCRIPTION_PRICING = {
    'Bronze': Decimal('20.00'),
    'Silver': Decimal('45.00'),
    'Gold': Decimal('80.00'),
}

class ExclusiveBookMeta(models.Model):
    ALLOWED_TIERS_CHOICES = [
        ('Bronze', 'Bronze'),
        ('Silver', 'Silver'),
        ('Gold', 'Gold'),
        ('Silver+', 'Silver+'),
        ('GoldOnly', 'Gold only'),
    ]

    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name='exclusive_meta')
    allowed_tiers = models.CharField(max_length=10, choices=ALLOWED_TIERS_CHOICES)
    views_bronze = models.PositiveIntegerField(default=0)
    views_silver = models.PositiveIntegerField(default=0)
    views_gold = models.PositiveIntegerField(default=0)
    favorited_bronze = models.PositiveIntegerField(default=0)
    favorited_silver = models.PositiveIntegerField(default=0)
    favorited_gold = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.book.name} exclusive metadata"