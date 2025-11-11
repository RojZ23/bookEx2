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
from decimal import Decimal
from .models import ExclusiveBookMeta, SUBSCRIPTION_PRICING
from .forms import ExclusiveBookForm
from datetime import date

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
    books = Book.objects.filter(is_exclusive=False)
    for b in books:
        b.pic_path = b.picture.url.split('/static/')[-1]
    return render(request, 'bookMng/displaybooks.html', {
        'item_list': MainMenu.objects.all(),
        'books': books
    })

@login_required
def exclusive_book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id, is_exclusive=True)
    profile = getattr(request.user, 'userprofile', None)

    if not profile:
        return render(request, 'user_profile_not_found.html', {
            'message': 'Access denied. User profile not found.'
        })

    # Writers can always see the exclusive book detail page
    if profile.role == 'Writer':
        has_access = True
    else:
        required_tier = None
        if hasattr(book, 'exclusive_meta'):
            required_tier = book.exclusive_meta.allowed_tiers

        # Check if user has the required subscription tier
        if profile.tier != required_tier:
            return render(request, 'subscription_tier_denied.html', {
                'message': 'Access denied. You do not have the required subscription tier for this book.'
            })

        # For regular users, check if they have enough funds
        if profile.role == 'Regular':
            required_fee = SUBSCRIPTION_PRICING.get(required_tier, Decimal('0'))
            if profile.balance < required_fee:
                return render(request, 'insufficient_funds.html', {
                    'message': 'Insufficient funds. Please top up your account to access this exclusive book.'
                })

    ratings = Rate.objects.filter(book=book)
    avg_rating = ratings.aggregate(Avg('rating'))['rating__avg']

    return render(request, 'bookMng/exclusive_book_detail.html', {
        'item_list': MainMenu.objects.all(),
        'book': book,
        'ratings': ratings,
        'avg_rating': avg_rating
    })



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
            'message': 'You need to log in to view your books.',
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

    total_purchased_qty = sum(purchased_quantities.values())
    purchased_books = Book.objects.filter(id__in=purchased_quantities.keys())
    favorite_books = request.user.favorite_books.all()

    for book in posted_books:
        book.pic_path = book.picture.url
    for book in purchased_books:
        book.pic_path = book.picture.url
    for book in favorite_books:
        book.pic_path = book.picture.url

    context = {
        'item_list': MainMenu.objects.all(),
        'posted_books': posted_books,
        'purchased_books': purchased_books,
        'purchased_quantities': purchased_quantities,
        'favorite_books': favorite_books,
        'total_purchased_qty': total_purchased_qty,
    }
    return render(request, 'bookMng/mybooks.html', context)

@login_required
def book_delete(request, book_id):
    book = get_object_or_404(Book, id=book_id, username=request.user)  # Optional ownership check
    if request.method == 'POST':
        book.delete()
        messages.success(request, f'Book "{book.name}" deleted successfully.')
        return redirect('mybooks')
    return render(request, 'bookMng/book_delete.html', {'book': book, 'item_list': MainMenu.objects.all()})
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
    purchased_agg = ShoppingCart.objects.filter(user=request.user, checked_out=True).aggregate(total_purchased=Sum('quantity'))
    total_purchased = purchased_agg['total_purchased'] or 0
    returned_agg = BookReturn.objects.filter(user=request.user).aggregate(total_returned=Sum('quantity'))
    total_returned = returned_agg['total_returned'] or 0

    if request.method == 'POST':
        new_role = request.POST.get('role')
        new_tier = request.POST.get('tier')
        old_tier = profile.tier
        old_role = profile.role

        if new_role in ['Regular', 'Publisher', 'Writer']:
            profile.role = new_role

        if profile.role == 'Regular' and new_tier in ['Free', 'Bronze', 'Silver', 'Gold']:
            if old_tier != new_tier:
                # Calculate tier difference and deduct from balance
                old_fee = SUBSCRIPTION_PRICING.get(old_tier, Decimal('0'))
                new_fee = SUBSCRIPTION_PRICING.get(new_tier, Decimal('0'))
                diff = new_fee - old_fee
                if diff > 0:
                    if profile.balance < diff:
                        messages.error(request, 'Insufficient funds to change to this subscription tier.')
                        return redirect('user_settings')
                    else:
                        profile.balance -= diff
                profile.tier = new_tier
        # Downgrade to Free if left Regular
        if profile.role != 'Regular':
            profile.tier = 'Free'

        profile.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('user_settings')

    context = {
        'profile': profile,
        'total_purchased': total_purchased,
        'total_returned': total_returned,
    }
    return render(request, 'user_settings.html', context)


def aboutus(request):
   return render(request, 'aboutus.html', { 'item_list': MainMenu.objects.all() })


def searchbooks(request):
    query = request.GET.get('q')
    min_rating = request.GET.get('min_rating')
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')

    user_profile = getattr(request.user, 'userprofile', None)
    books = Book.objects.all()

    if user_profile:
        if user_profile.role == 'Writer':
            # Writers can see all books
            pass
        elif user_profile.role == 'Regular':
            # For Regular users, show non-exclusive plus exclusive allowed by user's tier
            allowed_tier = user_profile.tier
            if allowed_tier in ['Bronze', 'Silver', 'Gold', 'Silver+', 'GoldOnly']:
                books = books.filter(
                    Q(is_exclusive=False) |
                    Q(is_exclusive=True, exclusive_meta__allowed_tiers=allowed_tier)
                )
            else:
                # Free tier or others see only non-exclusive
                books = books.filter(is_exclusive=False)
        else:
            # Publishers or other roles see only non-exclusive
            books = books.filter(is_exclusive=False)
    else:
        # Anonymous users see only non-exclusive
        books = books.filter(is_exclusive=False)

    if query:
        books = books.filter(name__icontains=query)

    books = books.annotate(avg_rating_value=Avg('rate__rating'))

    # Further filters (rating, price) unchanged
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

    for book in books:
        if book.picture:
            book.pic_path = book.picture.url.split('/static/')[-1]
        else:
            book.pic_path = 'default.jpg'  # fallback image path
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


@login_required
@group_required('Writer')
def edit_book(request, book_id):
    book = get_object_or_404(Book, id=book_id, username=request.user)
    old_picture = book.picture

    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            book = form.save(commit=False)

            # Update or create ExclusiveBookMeta if the book is exclusive
            if book.is_exclusive:
                allowed_tiers = request.POST.get('allowed_tiers')
                # Create or update ExclusiveBookMeta record
                ExclusiveBookMeta.objects.update_or_create(
                    book=book,
                    defaults={'allowed_tiers': allowed_tiers}
                )
            book.save()  # Save book and exclusive meta changes
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

from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def exclusive_books(request):
    profile = request.user.userprofile
    is_writer = profile.role == "Writer"

    if profile.role == "Publisher":
        return render(request, 'permission_denied.html', {'message': 'Access denied.'})

    if profile.role == "Regular":
        # Pause access if balance insufficient for current subscription monthly fee
        required_fee = SUBSCRIPTION_PRICING.get(profile.tier, Decimal('0'))
        if profile.tier == "Free" or profile.balance < required_fee:
            return render(request, 'permission_denied.html', {
                'message': 'Exclusive content is paused. Please deposit funds to continue access.'
            })

    # Define tiers allowed for display based on current tier
    visible_tiers = []
    if profile.tier == "Gold":
        visible_tiers = ["Bronze", "Silver", "Gold", "Silver+", "GoldOnly"]
    elif profile.tier == "Silver":
        visible_tiers = ["Bronze", "Silver", "Silver+"]
    elif profile.tier == "Bronze":
        visible_tiers = ["Bronze"]

    filter_tier = request.GET.get("tier")
    search_term = request.GET.get("q")
    books_qs = Book.objects.filter(is_exclusive=True)

    if not is_writer:
        books_qs = books_qs.filter(exclusive_meta__allowed_tiers__in=visible_tiers)
    if filter_tier:
        books_qs = books_qs.filter(exclusive_meta__allowed_tiers=filter_tier)
    if search_term:
        books_qs = books_qs.filter(name__icontains=search_term)

    for book in books_qs:
        book.pic_path = book.picture.url
        # NEW tag if published within last 3 days
        book.is_new = (date.today() - book.publishdate).days <= 3

    context = {
        'books': books_qs,
        'is_writer': is_writer,
        'visible_tiers': visible_tiers,
        'user_tier': profile.tier,
    }
    return render(request, "bookMng/exclusive_books.html", context)

@login_required
def post_exclusive_book(request):
    profile = request.user.userprofile
    if profile.role != "Writer":
        return render(request, 'permission_denied.html', {'message': 'Only writers may post exclusive books.'})

    if request.method == "POST":
        form = ExclusiveBookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.is_exclusive = True
            book.username = request.user
            book.save()

            # create exclusive metadata
            allowed_tier = form.cleaned_data['allowed_tiers']
            ExclusiveBookMeta.objects.create(book=book, allowed_tiers=allowed_tier)
            messages.success(request, "Exclusive book posted successfully.")
            return redirect('exclusive_books')
    else:
        form = ExclusiveBookForm()

    return render(request, 'bookMng/post_exclusive_book.html', {'form': form})



@login_required
def deposit_money(request):
    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get('amount', '0'))
            if amount > 0:
                profile = request.user.userprofile
                profile.balance += amount
                profile.save()
                messages.success(request, "Deposit successful.")
            else:
                messages.error(request, "Please enter a positive amount.")
        except Exception:
            messages.error(request, "Invalid input.")
        return redirect('user_settings')
    return render(request, "bookMng/deposit_money.html")