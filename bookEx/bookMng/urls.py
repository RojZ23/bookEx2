from django.urls import path, include
from . import views

urlpatterns = [
   path('', views.index, name='index'),
   path('postbook', views.postbook, name='postbook'),
   path('displaybooks', views.displaybooks, name='displaybooks'),
   path('book_detail/<int:book_id>', views.book_detail, name='book_detail'),
   path('mybooks', views.mybooks, name='mybooks'),
   path('book_delete/<int:book_id>', views.book_delete, name='book_delete'),
   path('aboutus', views.aboutus, name='aboutus'),
   path('searchbooks', views.searchbooks, name='searchbooks'),
   path('cart', views.view_cart, name='cart'),
   path('add_to_cart/<int:book_id>', views.add_to_cart, name='add_to_cart'),
   path('update_cart_quantity/<int:book_id>/', views.update_cart_quantity, name='update_cart_quantity'),
   path('checkout', views.checkout, name='checkout'),
   path('return_book/<int:book_id>/', views.return_book, name='return_book'),
   path('rate/<int:book_id>', views.rate_book, name='rate_book'),
   path('toggle_favorite/<int:book_id>/', views.toggle_favorite, name='toggle_favorite'),
   path('favorites/', views.favorite_list, name='favorite_list'),
   path('add_comment/<int:book_id>/', views.add_comment, name='add_comment'),
   path('delete_comment/<int:comment_id>/', views.delete_comment, name='delete_comment'),
]