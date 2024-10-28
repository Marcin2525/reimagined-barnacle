from django.contrib import admin
from .models import Product, Order, OrderItem, Cart, CartItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1

class CartAdmin(admin.ModelAdmin):
    inlines = [CartItemInline]

admin.site.register(Product)
admin.site.register(Order, OrderAdmin)
admin.site.register(Cart, CartAdmin)
