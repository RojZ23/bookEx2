from django.contrib.auth.models import User
from django.db import models
from django.utils.timezone import now

class MainMenu(models.Model):
   item = models.CharField(max_length=300, unique=True)
   link = models.CharField(max_length=300, unique=True)

   def __str__(self):
       return self.item

class Book(models.Model):
   name = models.CharField(max_length=200)
   web = models.URLField(max_length=300)
   price = models.DecimalField(decimal_places=2, max_digits=8)
   publishdate = models.DateField(auto_now=True)
   picture = models.FileField(upload_to='bookEx/static/uploads')
   pic_path = models.CharField(max_length=300, editable=False, blank=True)
   username = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
   favorites = models.ManyToManyField(User, related_name='favorite_books', blank=True)

class ShoppingCart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    checked_out = models.BooleanField(default=False)  # New field to mark purchase status

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