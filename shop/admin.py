from django.contrib import admin
from django.utils import timezone  # 👈 ЭТА СТРОКА ВАЖНА!
from .models import Category, Product, Order, OrderItem, Material, UserProfile, ProductImage
import csv
from django.http import HttpResponse
from openpyxl import Workbook
from django.utils.html import format_html


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['name', 'material_type', 'color', 'price_per_gram', 'is_active']
    list_filter = ['material_type', 'is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['price_per_gram', 'is_active']

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'material_type', 'color', 'is_active', 'order')
        }),
        ('Цены', {
            'fields': ('price_per_gram', 'density')
        }),
        ('Технические характеристики', {
            'fields': ('print_temperature', 'bed_temperature', 'strength', 'flexibility'),
            'classes': ('collapse',)
        }),
        ('Визуальное отображение', {
            'fields': ('icon', 'image'),
            'classes': ('collapse',)
        }),
    )


class LowStockFilter(admin.SimpleListFilter):
    title = 'Наличие на складе'
    parameter_name = 'stock_status'

    def lookups(self, request, model_admin):
        return (
            ('low', 'Мало (< 10 шт)'),
            ('out', 'Нет в наличии (0)'),
            ('in', 'В наличии (> 10)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(stock__lt=10, stock__gt=0)
        if self.value() == 'out':
            return queryset.filter(stock=0)
        if self.value() == 'in':
            return queryset.filter(stock__gte=10)


class ProductImageInline(admin.TabularInline):
    """Inline для добавления фотографий прямо в карточку товара"""
    model = ProductImage
    extra = 3  # Показывать 3 пустых поля для загрузки
    fields = ['image', 'title', 'is_main', 'order', 'preview']
    readonly_fields = ['preview']

    def preview(self, obj):
        """Превью фотографии в админке"""
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: cover;" />', obj.image.url)
        return '-'

    preview.short_description = 'Превью'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'material', 'product_type', 'price', 'is_available', 'is_featured',
                    'hide_from_catalog']
    list_filter = ['category', 'material', 'product_type', 'is_available', 'is_featured', 'hide_from_catalog']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['price', 'is_available', 'is_featured']
    list_per_page = 20

    inlines = [ProductImageInline]

    fieldsets = (
        ('Классификация', {
            'fields': ('name', 'slug', 'category', 'material', 'product_type')
        }),
        ('Цены', {
            'fields': ('price', 'price_per_unit')
        }),
        ('Описание', {
            'fields': ('description', 'specifications', 'image')
        }),
        ('Наличие и видимость', {
            'fields': ('stock', 'is_available', 'is_featured', 'hide_from_catalog')
        }),
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ['get_total']
    fields = [
        'product', 'quantity', 'price', 'color_choice',
        'infill_percent', 'layer_height', 'need_support',
        'need_polishing', 'need_painting', 'get_total'
    ]

    def get_total(self, obj):
        return obj.get_total()

    get_total.short_description = 'Сумма'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer_name', 'status', 'payment_status', 'total', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'customer_name', 'customer_email', 'customer_phone']
    readonly_fields = ['order_number', 'subtotal', 'total', 'created_at']
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'
    list_per_page = 25

    fieldsets = (
        ('Информация о заказе', {
            'fields': ('order_number', 'user', 'status', 'payment_status')
        }),
        ('3D модель', {
            'fields': ('model_file', 'model_notes'),
            'classes': ('collapse',)
        }),
        ('Клиент', {
            'fields': ('customer_name', 'customer_email', 'customer_phone',
                       'delivery_address', 'delivery_notes', 'customer_comment')
        }),
        ('Финансы', {
            'fields': ('subtotal', 'delivery_cost', 'total')
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_processing', 'mark_as_printed', 'mark_as_completed', 'export_to_csv']

    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='modeling')
        self.message_user(request, f'{updated} заказов переведено в статус "Моделирование"')

    mark_as_processing.short_description = 'Отметить как "В обработке"'

    def mark_as_printed(self, request, queryset):
        updated = queryset.update(status='printing')
        self.message_user(request, f'{updated} заказов переведено в статус "Печать"')

    mark_as_printed.short_description = 'Отметить как "В печати"'

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} заказов отмечено как выполненные')

    mark_as_completed.short_description = 'Отметить как "Выполнено"'

    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Номер заказа', 'Клиент', 'Email', 'Телефон',
            'Статус', 'Статус оплаты', 'Сумма', 'Дата создания'
        ])

        for order in queryset:
            writer.writerow([
                order.order_number,
                order.customer_name,
                order.customer_email,
                order.customer_phone,
                order.get_status_display(),
                order.get_payment_status_display(),
                float(order.total),
                order.created_at.strftime('%Y-%m-%d %H:%M')
            ])

        self.message_user(request, f'Экспортировано {queryset.count()} заказов')
        return response

    export_to_csv.short_description = 'Экспорт в CSV'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['order', 'is_active']
    search_fields = ['name']