from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

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
import json
from django.conf import settings
import requests

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

    today = date.today()

    # Monthly deduction (occurs separately)
    if profile.role == 'Regular' and profile.tier in ['Bronze', 'Silver', 'Gold']:
        deduct_amount = SUBSCRIPTION_PRICING.get(profile.tier, Decimal('0'))
        if profile.last_deduction_date is None or (today - profile.last_deduction_date).days >= 30:
            if profile.balance >= deduct_amount:
                profile.balance -= deduct_amount
                profile.last_deduction_date = today
                profile.save()
                messages.info(request, f'Monthly subscription fee of ${deduct_amount} deducted.')
            else:
                profile.tier = 'Free'
                profile.subscription_start = None
                profile.last_deduction_date = None
                profile.save()
                messages.warning(request, 'Insufficient funds for monthly fee. Downgraded to Free.')

    if request.method == 'POST':
        new_role = request.POST.get('role')
        new_tier = request.POST.get('tier')
        old_tier = profile.tier

        if new_role in ['Regular', 'Publisher', 'Writer']:
            profile.role = new_role

        if profile.role == 'Regular' and new_tier in ['Free', 'Bronze', 'Silver', 'Gold']:
            if old_tier != new_tier:
                new_fee = SUBSCRIPTION_PRICING.get(new_tier, Decimal('0'))

                # Deduct full new subscription price immediately (no refunds)
                if profile.balance < new_fee:
                    messages.error(request, 'Insufficient funds to change to this subscription tier.')
                    return redirect('user_settings')
                else:
                    # Charge full new tier amount
                    profile.balance -= new_fee

                    # Update tier info and subscription dates
                    profile.tier = new_tier
                    profile.subscription_start = today
                    profile.last_deduction_date = today
                    profile.save()

                    messages.success(request, f'You have been charged ${new_fee} for the {new_tier} subscription tier.')

        elif profile.role != 'Regular':
            # Reset tier and subscription for non-regular users
            profile.tier = 'Free'
            profile.subscription_start = None
            profile.last_deduction_date = None
            profile.save()

        else:
            # If tier unchanged, just save role change
            profile.save()

        messages.success(request, 'Profile updated successfully.')
        return redirect('user_settings')

    context = {
        'profile': profile,
        'total_purchased': total_purchased,
        'total_returned': total_returned,
        'subscription_start': profile.subscription_start,
        'last_deduction_date': profile.last_deduction_date,
    }
    return render(request, 'user_settings.html', context)

def aboutus(request):
   return render(request, 'aboutus.html', { 'item_list': MainMenu.objects.all() })


from django.db.models import Count, Q, Avg


TIER_RANK = {
    'Free': 0,
    'Bronze': 1,
    'Silver': 2,
    'Gold': 3,
    'Silver+': 2,
    'GoldOnly': 3,
}


def _apply_exclusive_filter(queryset, user_profile):
    """
    Apply your existing exclusive-visibility rules to a queryset.
    Writers see all; Regular users limited by tier; others see non-exclusive only.
    """
    if not user_profile:
        # Anonymous: only non-exclusive
        return queryset.filter(is_exclusive=False)

    user_tier = user_profile.tier
    user_tier_rank = TIER_RANK.get(user_tier, -1)

    if user_profile.role == 'Writer':
        # Writers see everything
        return queryset

    if user_profile.role == 'Regular':
        if user_tier_rank > 0:
            allowed_tier_books_q = []
            for tier_key, rank in TIER_RANK.items():
                if rank <= user_tier_rank and tier_key not in ['Free']:
                    allowed_tier_books_q.append(
                        Q(is_exclusive=True, exclusive_meta__allowed_tiers=tier_key)
                    )
            if allowed_tier_books_q:
                query_filter = Q(is_exclusive=False)
                for q_filter in allowed_tier_books_q:
                    query_filter |= q_filter
                return queryset.filter(query_filter)
            else:
                return queryset.filter(is_exclusive=False)
        else:
            return queryset.filter(is_exclusive=False)

    # Publishers or other roles: only non-exclusive
    return queryset.filter(is_exclusive=False)


def _build_ai_recommendations(filtered_qs, user_profile, query):
    """
    Use OpenRouter gpt-4o-mini to pick a subset and ranking of books
    from filtered_qs (already includes search + filters + tier rules).
    Only uses local DB data (no external books).
    """
    # Start from the same filtered queryset, then narrow to "good" candidates
    candidates = list(
        filtered_qs.annotate(
            avg_rating=Avg('rate__rating'),
            comments_count=Count('comments')
        ).filter(
            Q(avg_rating__gte=3) | Q(comments_count__gte=3)
        )
    )

    if not candidates:
        return []

    books_payload = []
    for b in candidates:
        books_payload.append({
            "id": b.id,
            "name": b.name,
            "price": float(b.price),
            "avg_rating": float(b.avg_rating) if b.avg_rating is not None else 0.0,
            "comments_count": int(b.comments_count or 0),
        })

    user_tier = getattr(user_profile, "tier", "Anonymous") if user_profile else "Anonymous"
    prompt = (
        "You are a book recommendation engine for a private site. "
        "You must ONLY recommend book IDs that are provided in the JSON list. "
        "Each book has fields: id, name, price, avg_rating, comments_count. "
        "Prefer books with higher avg_rating and more comments. "
        "If the user search query is non-empty, prefer books whose name semantically matches the query. "
        "User tier: " + str(user_tier) + ". "
        "Return a JSON list of at most 10 book IDs in descending recommendation order, "
        "no explanations, no extra keys.\n\n"
        "User search query: " + (query or "") + "\n\n"
        "Books JSON:\n" + json.dumps(books_payload, ensure_ascii=False)
    )

    api_key = getattr(settings, "OPENROUTER_API_KEY", None)

    # Fallback ranking if API key missing or request fails
    def fallback_order():
        return [
            b.id for b in sorted(
                candidates,
                key=lambda x: (
                    -(x.avg_rating or 0.0),
                    -(x.comments_count or 0),
                )
            )
        ]

    if not api_key:
        recommended_ids = fallback_order()
    else:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a strict JSON API."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                },
                timeout=15,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            recommended_ids = json.loads(content)
            if not isinstance(recommended_ids, list):
                recommended_ids = []
            recommended_ids = [int(i) for i in recommended_ids if isinstance(i, (int, str))]
        except Exception:
            recommended_ids = fallback_order()

    if not recommended_ids:
        return []

    # Keep only ids that are in candidates
    candidate_ids = {b.id for b in candidates}
    recommended_ids = [bid for bid in recommended_ids if bid in candidate_ids]

    preserved_order = {bid: idx for idx, bid in enumerate(recommended_ids)}
    # Pull from filtered_qs so all filters/tier rules stay applied
    qs = filtered_qs.filter(id__in=recommended_ids).annotate(
        avg_rating=Avg('rate__rating'),
        comments_count=Count('comments')
    )
    books_list = sorted(qs, key=lambda b: preserved_order.get(b.id, 10**9))
    return books_list


def searchbooks(request):
    query = request.GET.get('q')
    min_rating = request.GET.get('min_rating')
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')

    user_profile = getattr(request.user, 'userprofile', None)

    # 1) Base queryset with exclusive rules
    books = _apply_exclusive_filter(Book.objects.all(), user_profile)

    # 2) Apply text search
    if query:
        books = books.filter(name__icontains=query)

    # 3) Annotate for rating
    books = books.annotate(avg_rating_value=Avg('rate__rating'))

    # 4) Apply rating filter
    if min_rating and min_rating != 'none':
        try:
            min_rating_float = float(min_rating)
            books = books.filter(avg_rating_value__gte=min_rating_float)
        except ValueError:
            pass

    # 5) Apply price filters
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

    # 6) Prefetch comments for display
    books = books.prefetch_related('comments')

    # 7) Picture path + avg_rating_value cleanup for search list
    for book in books:
        if book.picture:
            book.pic_path = book.picture.url.split('/static/')[-1]
        else:
            book.pic_path = 'default.jpg'
        if book.avg_rating_value is None:
            book.avg_rating_value = None

    # 8) Recommended books use THE SAME filtered queryset (`books`)
    #    so search query + min_rating + price range all affect recommendations.
    recommended_books = _build_ai_recommendations(books, user_profile, query)

    # 9) Picture path for recommended list
    for book in recommended_books:
        if book.picture:
            book.pic_path = book.picture.url.split('/static/')[-1]
        else:
            book.pic_path = 'default.jpg'

    context = {
        'books': books,
        'query': query or '',
        'min_rating': min_rating or 'none',
        'price_min': price_min or '',
        'price_max': price_max or '',
        'recommended_books': recommended_books,
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
        if book.is_exclusive:
            return redirect('exclusive_book_detail', book_id=book_id)
        return redirect('book_detail', book_id=book_id)

    return render(request, 'bookMng/rate.html', {'book': book})


@login_required
def toggle_favorite(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    user = request.user
    if user in book.favorites.all():
        book.favorites.remove(user)
    else:
        book.favorites.add(user)

    if book.is_exclusive:
        return redirect('exclusive_book_detail', book_id=book_id)
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

    if book.is_exclusive:
        return redirect('exclusive_book_detail', book_id=book_id)
    return redirect('book_detail', book_id=book_id)


@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if comment.user != request.user:
        return HttpResponseForbidden("You are not allowed to delete this comment.")
    book = comment.book
    book_id = book.id
    comment.delete()

    if book.is_exclusive:
        return redirect('exclusive_book_detail', book_id=book_id)
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

def subscription_plans(request):
    return render(request, 'subscription_plans.html')


def edit_book(request, book_id):
    if not request.user.is_authenticated:
        return render(request, 'bookMng/login_required.html', {
            'message': 'You need to log in to edit books.',
            'item_list': MainMenu.objects.all(),
        })

    profile = getattr(request.user, 'userprofile', None)
    if not profile or profile.role != 'Writer':
        return render(request, 'permission_denied.html', status=403)

    book = get_object_or_404(Book, id=book_id, username=request.user)

    # Preload allowed_tiers into the book instance for form display if exclusive
    if book.is_exclusive:
        try:
            book.allowed_tiers = book.exclusive_meta.allowed_tiers
        except ExclusiveBookMeta.DoesNotExist:
            book.allowed_tiers = None

    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            book = form.save(commit=False)
            if book.is_exclusive:
                allowed_tiers = request.POST.get('allowed_tiers')
                ExclusiveBookMeta.objects.update_or_create(
                    book=book,
                    defaults={'allowed_tiers': allowed_tiers}
                )
            book.save()
            return redirect('book_detail', book_id=book.id)
    else:
        form = BookForm(instance=book)

    context = {
        'form': form,
        'item_list': MainMenu.objects.all(),
    }
    return render(request, 'bookMng/editbook.html', context)


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
        book = rating.book
        book_id = book.id
        rating.delete()
        if book.is_exclusive:
            return redirect('exclusive_book_detail', book_id=book_id)
        return redirect('book_detail', book_id=book_id)
    # If not owner, just send back to the right detail page
    book = rating.book
    if book.is_exclusive:
        return redirect('exclusive_book_detail', book_id=book.id)
    return redirect('book_detail', book_id=book.id)

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
        return render(request, 'subscription_required.html', {'message': 'Access denied.'})

    if profile.role == "Regular":
        # Pause access if balance insufficient for current subscription monthly fee
        required_fee = SUBSCRIPTION_PRICING.get(profile.tier, Decimal('0'))
        if profile.tier == "Free" or profile.balance < required_fee:
            return render(request, 'insufficient_funds.html', {
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

@csrf_exempt
def chatbot_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        user_msg = data.get('message', '').strip()
        if not user_msg:
            return JsonResponse({'reply': "Please ask a question."})

        # Fetch books info to create context for AI
        books = Book.objects.all().values('name', 'price')

        books_info = "; ".join([f"{b['name']} priced at ${b['price']} /n" for b in books[:50]])  # limit length

        prompt = f"""
You are a helpful assistant for a book exchange website. You know about the books available and site features like searching, posting, and user tiers.
Books currently available: {books_info}
User question: {user_msg}
Answer clearly based on books, subscription tiers of this website, and website features only. Do not mention anything outside this site.
"""

        # Call OpenRouter.ai GPT-4o-mini model with this prompt
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a concise helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=10,
        )
        response.raise_for_status()
        ai_reply = response.json()['choices'][0]['message']['content'].strip()

    except Exception as e:
        ai_reply = "Sorry, I am unable to answer right now."

    return JsonResponse({'reply': ai_reply})