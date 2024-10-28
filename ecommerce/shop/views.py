from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from .models import Cart, CartItem, Order, OrderItem, Product
from .serializers import ProductSerializer, OrderSerializer, CartSerializer
from .forms import UserRegisterForm
from rest_framework.permissions import AllowAny
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
import paypalrestsdk
from django.conf import settings
from django.http import JsonResponse


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    if request.method == 'POST':
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email')
        logger.info(f'Received data: username={username}, email={email}')  # Logowanie danych
        if not username or not password or not email:
            return Response({'error': 'Please provide username, password, and email'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.create_user(username=username, password=password, email=email)
            user.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response({'token': token.key}, status=status.HTTP_201_CREATED)
        except IntegrityError:
            logger.error(f'Username {username} already exists.')  # Logowanie błędu
            return Response({'error': 'Username already exists. Please choose a different username.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Error during registration: {e}')  # Logowanie błędu
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({'error': 'Please provide both username and password'}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)

    if user is not None:
        token, created = Token.objects.get_or_create(user=user)
        logger.info(f'User {user.username} logged in with ID {user.id}')  # Log the user ID
        return Response({'token': token.key, 'user_id': user.id}, status=status.HTTP_200_OK)
    else:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def logout_user(request):
    token = request.auth
    if token is not None:
        token.delete()
    return Response(status=204)

# Widoki dla rejestracji, logowania i wylogowywania użytkowników za pomocą szablonów HTML
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('home')
    else:
        form = UserRegisterForm()
    return render(request, 'shop/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'shop/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

def home(request):
    return render(request, 'shop/home.html')

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# Kontroler dla produktów
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

import logging

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_cart(request):
    user = request.user
    cart, created = Cart.objects.get_or_create(user=user)

    if request.method == 'POST':
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)
        logger.debug(f"Received product_id: {product_id}, quantity: {quantity}")

        if not product_id:
            return Response({'error': 'Product ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = get_object_or_404(Product, pk=product_id)
            cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
            if not created:
                cart_item.quantity += quantity
            else:
                cart_item.quantity = quantity
            cart_item.save()
            return Response({'status': 'item added'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error adding product to cart: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'DELETE':
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'Product ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = get_object_or_404(Product, pk=product_id)
            cart_item = get_object_or_404(CartItem, cart=cart, product=product)
            cart_item.delete()
            return Response({'status': 'item removed'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error removing product from cart: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'GET':
        serializer = CartSerializer(cart)
        return Response(serializer.data)


paypalrestsdk.configure({
    "mode": "sandbox",  # sandbox or live
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET
})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def paypal_webhook(request):
    payload = request.body
    headers = request.headers

    signature_verification = paypalrestsdk.WebhookEvent.verify(
        transmission_id=headers['PayPal-Transmission-Id'],
        timestamp=headers['PayPal-Transmission-Time'],
        webhook_id=settings.PAYPAL_WEBHOOK_ID,
        event_body=payload,
        cert_url=headers['PayPal-Cert-Url'],
        actual_sig=headers['PayPal-Transmission-Sig'],
        auth_algo=headers['PayPal-Auth-Algo']
    )

    if signature_verification:
        event = paypalrestsdk.WebhookEvent.deserialize(payload)
        # Handle the event here
        if event.event_type == "PAYMENT.SALE.COMPLETED":
            sale = event.resource
            # Process the sale
            print('Payment completed successfully!')
            return JsonResponse({'status': 'success'}, status=200)
        else:
            return JsonResponse({'status': 'ignored'}, status=200)
    else:
        return JsonResponse({'status': 'verification failed'}, status=400)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_cart_item(request, item_id):
    try:
        cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
        cart_item.delete()
        return Response({'success': 'Item removed from cart'}, status=status.HTTP_204_NO_CONTENT)
    except CartItem.DoesNotExist:
        return Response({'error': 'Item not found in cart'}, status=status.HTTP_404_NOT_FOUND)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import CartItem

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_cart_item_quantity(request, item_id):
    try:
        cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
    except CartItem.DoesNotExist:
        return Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)

    quantity = request.data.get('quantity')
    if quantity is not None and int(quantity) > 0:
        cart_item.quantity = int(quantity)
        cart_item.save()
        return Response({'success': 'Quantity updated'}, status=status.HTTP_200_OK)
    else:
        return Response({'error': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    user = request.user
    cart = get_object_or_404(Cart, user=user)
    cart_items = CartItem.objects.filter(cart=cart)

    if not cart_items.exists():
        return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

    order_data = {
        'total_amount': sum(item.product.price * item.quantity for item in cart_items),
        'transaction_details': request.data,
        'items': [{'product_id': item.product.product_id, 'quantity': item.quantity} for item in cart_items]
    }

    serializer = OrderSerializer(data=order_data, context={'user': user})
    if serializer.is_valid():
        order = serializer.save()
        cart_items.delete()
        cart.delete()
        return Response({'message': 'Order created successfully'}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)