from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ProductViewSet, manage_cart, delete_cart_item, OrderViewSet,
                    register_user, create_order, login_user, update_cart_item_quantity,
                    logout_user, paypal_webhook)

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('register/', register_user, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('cart/', manage_cart, name='manage_cart'),
    path('paypal-webhook/', paypal_webhook, name='paypal-webhook'),
    path('cart/<int:item_id>/', delete_cart_item, name='delete_cart_item'),
    path('cart/<int:item_id>/update/', update_cart_item_quantity, name='update_cart_item_quantity'),
    path('create-order/', create_order, name='create_order'),
]