from django.contrib.admin import AdminSite
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from .models import Order, Product


class ShopAdminSite(AdminSite):
    site_header = 'Управление 3D печатью'
    site_title = 'Админ-панель'
    index_title = 'Дашборд управления'

    def index(self, request, extra_context=None):
        # Статистика
        total_orders = Order.objects.count()
        pending_orders = Order.objects.filter(status='pending').count()
        printing_orders = Order.objects.filter(status='printing').count()
        completed_orders = Order.objects.filter(status='completed').count()

        # Выручка за месяц
        month_ago = timezone.now() - timedelta(days=30)
        monthly_revenue = Order.objects.filter(
            completed_at__gte=month_ago,
            status='completed'
        ).aggregate(total=Sum('total'))['total'] or 0

        # Товары на складе
        low_stock_products = Product.objects.filter(
            product_type='material',
            stock__lt=10,
            is_available=True
        ).count()

        extra_context = extra_context or {}
        extra_context.update({
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'printing_orders': printing_orders,
            'completed_orders': completed_orders,
            'monthly_revenue': monthly_revenue,
            'low_stock_products': low_stock_products,
        })

        return super().index(request, extra_context)


# Замените стандартную админку
admin_site = ShopAdminSite(name='shop_admin')