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
from django.db.models import Avg, Q
from django.db.models import Sum
from django.contrib import messages
from .models import BookReturn
from .decorators import group_required
from .forms import CustomUserCreationForm
from .models import UserProfile
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404, redirect


def index(request):
   return render(request, 'bookMng/index.html', { 'item_list': MainMenu.objects.all() })

def postbook(request):
    if not request.user.is_authenticated:
        return render(request, 'bookMng/login_required.html', {
            'message': 'You need to log in to post a book.',
            'item_list': MainMenu.objects.all(),
        })

    # Assuming you still want to check user role here (Publisher or Writer)
    profile = getattr(request.user, 'userprofile', None)
    if not profile or profile.role not in ['Publisher', 'Writer']:
        return render(request, 'permission_denied.html', status=403)

    submitted = False
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.username = request.user
            book.save()
            submitted = True
    else:
        form = BookForm()
        if 'submitted' in request.GET:
            submitted = True

    return render(request, 'bookMng/postbook.html', {
        'form': form,
        'submitted': submitted,
        'item_list': MainMenu.objects.all(),
    })

def displaybooks(request):
    books = Book.objects.all()
    # Remove pic_path splitting; use picture.url directly in templates
    return render(request, 'bookMng/displaybooks.html', {'item_list': MainMenu.objects.all(), 'books': books})


def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    # Remove pic_path splitting static, use the direct url in template
    ratings = Rate.objects.filter(book=book)
    avg_rating = ratings.aggregate(Avg('rating'))['rating__avg']

    return render(request, 'bookMng/book_detail.html', {
        'item_list': MainMenu.objects.all(),
        'book': book,
        'ratings': ratings,
        'avg_rating': avg_rating,
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
    returned_books_quantities = BookReturn.objects.filter(user=request.user).values('book').annotate(total_quantity=Sum('quantity'))
    returned_quantities = {rq['book']: rq['total_quantity'] for rq in returned_books_quantities}

    purchased_quantities = {}
    for pq in purchased_books_quantities:
        book_id = pq['book']
        net_qty = pq['total_quantity'] - returned_quantities.get(book_id, 0)
        if net_qty > 0:
            purchased_quantities[book_id] = net_qty

    purchased_books = Book.objects.filter(id__in=purchased_quantities.keys())
    favorite_books = request.user.favorite_books.all()

    return render(request, 'bookMng/mybooks.html', {
        'item_list': MainMenu.objects.all(),
        'posted_books': posted_books,
        'purchased_books': purchased_books,
        'purchased_quantities': purchased_quantities,
        'favorite_books': favorite_books,
    })


def book_delete(request, book_id):
   book = Book.objects.get(id=book_id)
   book.delete()
   return render(request, 'bookMng/book_delete.html', { 'item_list': MainMenu.objects.all() })

class Register(CreateView):
    template_name = 'registration/register.html'
    form_class = UserCreationForm
    success_url = reverse_lazy('register-success')


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            is_publisher = form.cleaned_data.get('is_publisher')
            is_writer = form.cleaned_data.get('is_writer')

            # Assign groups based on checkboxes
            if is_publisher:
                publisher_group, _ = Group.objects.get_or_create(name='Publisher')
                user.groups.add(publisher_group)
            if is_writer:
                writer_group, _ = Group.objects.get_or_create(name='Writer')
                user.groups.add(writer_group)

            # Determine role string for profile
            if is_publisher and is_writer:
                role = 'Publisher/Writer'
            elif is_publisher:
                role = 'Publisher'
            elif is_writer:
                role = 'Writer'
            else:
                role = 'Regular'

            UserProfile.objects.create(user=user, role=role)

            return redirect('register-success')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def register_success(request):
    return render(request, 'registration/register_success.html')

@login_required
def user_settings(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in ['Regular', 'Publisher', 'Writer']:
            profile.role = new_role
            profile.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('user_settings')
        else:
            messages.error(request, 'Invalid role selected.')
    return render(request, 'user_settings.html', {'profile': profile})


def aboutus(request):
   return render(request, 'aboutus.html', { 'item_list': MainMenu.objects.all() })


def searchbooks(request):
    query = request.GET.get('q')
    min_rating = request.GET.get('min_rating')
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')

    books = Book.objects.all()
    if query:
        books = books.filter(name__icontains=query)

    books = books.annotate(avg_rating_value=Avg('rate__rating'))

    # Filter by rating only if min_rating is set and not 'none'
    if min_rating and min_rating != 'none':
        try:
            min_rating_float = float(min_rating)
            books = books.filter(avg_rating_value__gte=min_rating_float)
        except ValueError:
            pass

    if price_min:
        try:
            price_min_val = float(price_min)
            books = books.filter(price__gte=price_min_val)
        except ValueError:
            pass

    if price_max:
        try:
            price_max_val = float(price_max)
            books = books.filter(price__lte=price_max_val)
        except ValueError:
            pass

    books = books.prefetch_related('comments')

    # For static pic_path extraction and rating None handling
    for book in books:
        if book.picture:
            book.pic_path = book.picture.url.split('/static/')[-1]
        else:
            book.pic_path = 'default.jpg'  # fallback image path if needed
        if book.avg_rating_value is None:
            book.avg_rating_value = None

    context = {
        'books': books,
        'query': query or '',
        'min_rating': min_rating or 'none',
        'price_min': price_min or '',
        'price_max': price_max or '',
    }
    return render(request, 'bookMng/searchbooks.html', context)

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

def checkout(request):
    if not request.user.is_authenticated:
        return render(request, 'bookMng/login_required.html', {
            'message': 'You need to log in to access the checkout.',
            'item_list': MainMenu.objects.all(),
        })

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


@group_required('Publisher', 'Writer')
def edit_book(request, book_id):
    # Only allow editing by the user who posted the book
    book = get_object_or_404(Book, id=book_id, username=request.user)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            return redirect('book_detail', book_id=book.id)
    else:
        form = BookForm(instance=book)
    return render(request, 'editbook.html', {'form': form})

@group_required('Publisher', 'Writer')
def delete_book(request, book_id):
    book = get_object_or_404(Book, id=book_id, author=request.user)
    if request.method == 'POST':
        book.delete()
        return redirect('mybooks')
    return render(request, 'delete_confirm.html', {'book': book})

@login_required
def cancel_checkout(request):
    if request.method == 'POST':
        # Remove all shopping cart items for the current user that are not checked out
        ShoppingCart.objects.filter(user=request.user, checked_out=False).delete()
    return redirect('cart')  # Ensure 'cart' URL name exists

@login_required
def delete_rating(request, rate_id):
    rating = get_object_or_404(Rate, id=rate_id)
    if rating.user == request.user:
        rating.delete()
    return redirect('book_detail', book_id=rating.book.id)

@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if comment.user != request.user:
        return HttpResponseForbidden("You cannot edit this comment.")

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment.content = content
            comment.save()
        return redirect('book_detail', book_id=comment.book.id)

    # Optionally handle GET if you want a separate edit page
    return redirect('book_detail', book_id=comment.book.id)