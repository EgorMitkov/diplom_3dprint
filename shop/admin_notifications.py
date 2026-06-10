from django.contrib.admin import AdminSite
from django.contrib import messages


class NotificationAdminSite(AdminSite):
    def get_app_list(self, request):
        app_list = super().get_app_list(request)

        # Проверяем новые заказы
        from .models import Order
        new_orders = Order.objects.filter(status='pending').count()

        if new_orders > 0:
            messages.info(
                request,
                f'У вас {new_orders} новых заказов, ожидающих обработки!'
            )

        return app_list