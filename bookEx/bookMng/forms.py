from django import forms
from django.forms import ModelForm
from .models import Book, ExclusiveBookMeta
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class BookForm(ModelForm):
   class Meta:
       model = Book
       fields = [
           'name',
           'web',
           'price',
           'picture',
       ]

class CustomUserCreationForm(UserCreationForm):
    is_publisher = forms.BooleanField(required=False, label='Register as Publisher')
    is_writer = forms.BooleanField(required=False, label='Register as Writer')

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'is_publisher', 'is_writer')


class ExclusiveBookForm(ModelForm):
    allowed_tiers = forms.ChoiceField(choices=ExclusiveBookMeta.ALLOWED_TIERS_CHOICES)

    class Meta:
        model = Book
        fields = ['name', 'web', 'price', 'picture']