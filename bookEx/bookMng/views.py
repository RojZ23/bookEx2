from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import MainMenu, Rate
from .forms import BookForm
from django.http import HttpResponseRedirect
from django.http import HttpResponseForbidden
from .models import Book, Comment
from django.views.generic.edit import CreateView
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from .models import ShoppingCart
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.db.models import Sum
from django.contrib import messages
from .models import BookReturn

def index(request):
   return render(request, 'bookMng/index.html', { 'item_list': MainMenu.objects.all() })

def postbook(request):
   submitted = False
   if request.method == 'POST':
       form = BookForm(request.POST, request.FILES)
       if form.is_valid():
           book = form.save(commit=False)
           try:
               book.username = request.user
           except Exception:
               pass
           book.save()
           return HttpResponseRedirect('/postbook?submitted=True')
   else:
       form = BookForm()
       if 'submitted' in request.GET:
           submitted = True
   return render(request, 'bookMng/postbook.html', { 'form': form, 'item_list': MainMenu.objects.all(), 'submitted': submitted })

def displaybooks(request):
    books = Book.objects.all()
    for b in books:
        b.pic_path = b.picture.url.split('/static/')[-1]
    return render(request, 'bookMng/displaybooks.html', {'item_list': MainMenu.objects.all(), 'books': books})


def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    book.pic_path = book.picture.url.split('/static/')[-1]

    ratings = Rate.objects.filter(book=book)
    avg_rating = ratings.aggregate(Avg('rating'))['rating__avg']

    return render(request, 'bookMng/book_detail.html', {
        'item_list': MainMenu.objects.all(),
        'book': book,
        'ratings': ratings,
        'avg_rating': avg_rating
    })


def mybooks(request):
    if not request.user.is_authenticated:
        return render(request, 'bookMng/login_required.html', {
            'message': 'You need to login to view your books.',
            'item_list': MainMenu.objects.all(),
        })

    posted_books = Book.objects.filter(username=request.user)
    purchased_items = ShoppingCart.objects.filter(user=request.user, checked_out=True)
    purchased_books_quantities = purchased_items.values('book').annotate(total_quantity=Sum('quantity'))

    # Calculate returned quantities for user
    returned_books_quantities = BookReturn.objects.filter(user=request.user).values('book').annotate(total_quantity=Sum('quantity'))
    returned_quantities = {rq['book']: rq['total_quantity'] for rq in returned_books_quantities}

    # Compute net purchased quantities = purchased - returned
    purchased_quantities = {}
    for pq in purchased_books_quantities:
        book_id = pq['book']
        net_qty = pq['total_quantity'] - returned_quantities.get(book_id, 0)
        if net_qty > 0:
            purchased_quantities[book_id] = net_qty

    # Filter purchased_books to include only books with positive net quantity
    purchased_books = Book.objects.filter(id__in=purchased_quantities.keys())

    favorite_books = request.user.favorite_books.all()

    for book in posted_books:
        book.pic_path = book.picture.url.split('/static/')[-1]
    for book in purchased_books:
        book.pic_path = book.picture.url.split('/static/')[-1]
    for book in favorite_books:
        book.pic_path = book.picture.url.split('/static/')[-1]

    return render(request, 'bookMng/mybooks.html', {
        'item_list': MainMenu.objects.all(),
        'posted_books': posted_books,
        'purchased_books': purchased_books,
        'purchased_quantities': purchased_quantities,
        'favorite_books': favorite_books
    })

def book_delete(request, book_id):
   book = Book.objects.get(id=book_id)
   book.delete()
   return render(request, 'bookMng/book_delete.html', { 'item_list': MainMenu.objects.all() })

class Register(CreateView):
    template_name = 'registration/register.html'
    form_class = UserCreationForm
    success_url = reverse_lazy('register-success')

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        # Re-render the form with errors
        return self.render_to_response(self.get_context_data(form=form))



def aboutus(request):
   return render(request, 'aboutus.html', { 'item_list': MainMenu.objects.all() })

def searchbooks(request):
    query = request.GET.get('q')
    books = Book.objects.filter(name__icontains=query) if query else []
    return render(request, 'searchbooks.html', { 'books': books, 'item_list': MainMenu.objects.all(), 'query': query })

@login_required
def add_to_cart(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    cart_item, created = ShoppingCart.objects.get_or_create(user=request.user, book=book, checked_out=False)
    if not created:
        cart_item.quantity += 1
    cart_item.save()
    return redirect('checkout')

@login_required
def view_cart(request):
    cart_items = ShoppingCart.objects.filter(user=request.user, checked_out=False).select_related('book')
    for item in cart_items:
        item.book.pic_path = item.book.picture.url.split('/static/')[-1]
    return render(request, 'bookMng/cart.html', {'item_list': MainMenu.objects.all(), 'cart_items': cart_items})

@login_required
def checkout(request):
    if request.method == 'POST':
        ShoppingCart.objects.filter(user=request.user, checked_out=False).update(checked_out=True)
        return redirect('mybooks')
    else:
        cart_items = ShoppingCart.objects.filter(user=request.user, checked_out=False).select_related('book')
        total_price = sum(item.quantity * item.book.price for item in cart_items)
        for item in cart_items:
            item.book.pic_path = item.book.picture.url.split('/static/')[-1]
        return render(request, 'bookMng/checkout.html', {
            'item_list': MainMenu.objects.all(),
            'cart_items': cart_items,
            'total_price': total_price
        })


@login_required
def rate_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if request.method == 'POST':
        rating = int(request.POST.get('rating'))
        Rate.objects.update_or_create(
            user=request.user,
            book=book,
            defaults={'rating': rating}
        )
        return redirect('book_detail', book_id=book_id)

    return render(request, 'bookMng/rate.html', { 'book': book })

@login_required
def toggle_favorite(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    user = request.user
    if user in book.favorites.all():
        book.favorites.remove(user)
    else:
        book.favorites.add(user)
    return redirect('book_detail', book_id=book_id)

@login_required
def favorite_list(request):
    user = request.user
    favorites = user.favorite_books.all()
    for book in favorites:
        book.pic_path = book.picture.url[14:]
    return render(request, 'bookMng/favorites.html', {
        'item_list': MainMenu.objects.all(),
        'favorites': favorites
    })

@login_required
def add_comment(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Comment.objects.create(book=book, user=request.user, content=content)
    return redirect('book_detail', book_id=book_id)

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if comment.user != request.user:
        return HttpResponseForbidden("You are not allowed to delete this comment.")
    book_id = comment.book.id
    comment.delete()
    return redirect('book_detail', book_id=book_id)

@login_required
def update_cart_quantity(request, book_id):
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        cart_item = ShoppingCart.objects.filter(user=request.user, book=book, checked_out=False).first()
        if cart_item:
            try:
                qty = int(request.POST.get('quantity', 1))
                if qty > 0:
                    cart_item.quantity = qty
                    cart_item.save()
            except ValueError:
                pass
        return redirect('checkout')

@login_required
def return_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    # Get user's total purchased (exclude already returned)
    purchased = ShoppingCart.objects.filter(
        user=request.user, book=book, checked_out=True
    ).aggregate(total=Sum('quantity'))['total'] or 0
    returned = BookReturn.objects.filter(
        user=request.user, book=book
    ).aggregate(total=Sum('quantity'))['total'] or 0
    available_to_return = purchased - returned

    if request.method == "POST":
        qty = int(request.POST.get("quantity", 0))
        if 0 < qty <= available_to_return:
            # Update inventory
            book.quantity += qty     # Assumes Book has a quantity (inventory) field
            book.save()
            # Log the return
            BookReturn.objects.create(user=request.user, book=book, quantity=qty)
            messages.success(request, f"Successfully returned {qty} copy/copies of {book.name}.")
        else:
            messages.error(request, f"Invalid quantity: {qty}. You can return up to {available_to_return}.")
        return redirect('mybooks')

    return render(request, 'bookMng/return_book_form.html', {
        'book': book,
        'available_to_return': available_to_return,
    })