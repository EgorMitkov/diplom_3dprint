from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver


# Create your models here.

class Category(models.Model):
    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('URL', unique=True, max_length=100)
    description = models.TextField('Описание', blank=True)
    image = models.ImageField('Изображение', upload_to='categories/', blank=True, null=True)
    order = models.IntegerField('Порядок сортировки', default=0)
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Material(models.Model):
    """Модель материала для 3D печати (вид пластика)"""

    MATERIAL_TYPES = [
        ('fdm', 'FDM пластик (нить)'),
        ('sla', 'SLA смола'),
        ('sls', 'SLS порошок'),
    ]

    name = models.CharField('Название материала', max_length=100)
    slug = models.SlugField('URL', unique=True, max_length=100)
    material_type = models.CharField('Тип материала', max_length=10, choices=MATERIAL_TYPES)

    # Характеристики
    color = models.CharField('Цвет', max_length=50, blank=True)
    density = models.DecimalField('Плотность (г/см³)', max_digits=5, decimal_places=2, default=1.24)
    price_per_gram = models.DecimalField('Цена за грамм (руб)', max_digits=8, decimal_places=2)

    # Технические характеристики
    print_temperature = models.CharField('Температура печати', max_length=50, blank=True)
    bed_temperature = models.CharField('Температура стола', max_length=50, blank=True)
    strength = models.CharField('Прочность', max_length=100, blank=True)
    flexibility = models.CharField('Гибкость', max_length=100, blank=True)

    # Визуальное отображение
    icon = models.CharField('Иконка', max_length=50, blank=True, help_text='Font Awesome иконка')
    image = models.ImageField('Изображение', upload_to='materials/', blank=True, null=True)

    is_active = models.BooleanField('Активен', default=True)
    order = models.IntegerField('Порядок сортировки', default=0)

    class Meta:
        verbose_name = 'Type of plastic'
        verbose_name_plural = 'Types of plastic'
        ordering = ['material_type', 'order', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_material_type_display()})"


class Product(models.Model):
    """Товар/услуга"""
    PRODUCT_TYPES = [
        ('ready_product', 'Готовое изделие'),
        ('printing_service', 'Услуга печати'),
        ('modeling_service', 'Услуга моделирования'),
        ('postprocessing_service', 'Услуга постобработки'),
    ]

    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('URL', unique=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, null=True, blank=True)
    material = models.ForeignKey('Material', on_delete=models.SET_NULL, null=True, blank=True)
    product_type = models.CharField('Тип', max_length=30, choices=PRODUCT_TYPES, default='ready_product')
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, default=0)
    price_per_unit = models.CharField('Единица цены', max_length=50, blank=True)
    description = models.TextField('Описание', blank=True)
    specifications = models.TextField('Характеристики', blank=True)
    image = models.ImageField('Изображение', upload_to='products/', blank=True, null=True)
    stock = models.IntegerField('Остаток', default=0)
    is_available = models.BooleanField('Доступен', default=True)
    is_featured = models.BooleanField('Рекомендуемый', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    hide_from_catalog = models.BooleanField(
        'Скрыть из каталога',
        default=False,
        help_text='Отметьте, чтобы скрыть товар из общего каталога')

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.stock > 0 if self.product_type == 'ready_product' else True

        # Характеристики для готовых изделий

    weight = models.DecimalField('Вес (г)', max_digits=10, decimal_places=2, null=True, blank=True)
    dimensions = models.CharField('Размеры (мм)', max_length=100, blank=True)

    # Время изготовления для услуг
    min_time = models.DecimalField('Мин. время (часы)', max_digits=5, decimal_places=2, null=True, blank=True)
    max_time = models.DecimalField('Макс. время (часы)', max_digits=5, decimal_places=2, null=True, blank=True)


class OrderItem(models.Model):
    """Позиция заказа"""
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Параметры для 3D печати
    color_choice = models.CharField(max_length=50, blank=True)
    infill_percent = models.IntegerField(default=20, validators=[MinValueValidator(0), MaxValueValidator(100)])
    layer_height = models.DecimalField(max_digits=4, decimal_places=2, default=0.2, null=True, blank=True)
    need_support = models.BooleanField(default=True)
    need_polishing = models.BooleanField(default=False)
    need_painting = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def get_total(self):
        total = self.price * self.quantity
        if self.need_polishing:
            total += 500
        if self.need_painting:
            total += 1000
        return total


class Order(models.Model):
    """Заказ"""
    STATUS_CHOICES = [
        ('pending', 'Ожидает обработки'),
        ('modeling', 'Моделирование'),
        ('printing', 'Печать'),
        ('postprocessing', 'Постобработка'),
        ('ready', 'Готов к выдаче'),
        ('completed', 'Выполнен'),
        ('cancelled', 'Отменён'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Не оплачен'),
        ('paid', 'Оплачен'),
        ('refunded', 'Возвращен'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')  # Добавлено

    model_file = models.FileField(upload_to='orders/%Y/%m/%d/', blank=True, null=True)
    model_notes = models.TextField(blank=True)

    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    delivery_address = models.TextField()
    delivery_notes = models.TextField(blank=True)
    customer_comment = models.TextField(blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Добавлено

    def save(self, *args, **kwargs):
        if not self.order_number:
            import random
            self.order_number = f'ORD{timezone.now().strftime("%Y%m%d")}{random.randint(1000, 9999)}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Заказ #{self.order_number}'

        # Добавьте эти поля, если они нужны
        estimated_weight = models.DecimalField('Предполагаемый вес (г)', max_digits=10, decimal_places=2, null=True,
                                               blank=True)
        estimated_print_time = models.DecimalField('Предполагаемое время печати (часы)', max_digits=8, decimal_places=2,
                                                   null=True, blank=True)
        model_description = models.TextField('Описание модели', blank=True)
        paid_at = models.DateTimeField('Дата оплаты', null=True, blank=True)
        completed_at = models.DateTimeField('Дата выполнения', null=True, blank=True)


class OrderItem(models.Model):
    """
    Модель позиции в заказе
    """
    INFILL_CHOICES = [
        (0, '0% - Пустой'),
        (10, '10%'),
        (20, '20% - Экономичный'),
        (50, '50% - Стандартный'),
        (75, '75% - Прочный'),
        (100, '100% - Максимальная прочность'),
    ]

    LAYER_HEIGHT_CHOICES = [
        (0.10, '0.10 мм - Высокое качество'),
        (0.15, '0.15 мм'),
        (0.20, '0.20 мм - Стандарт'),
        (0.25, '0.25 мм'),
        (0.30, '0.30 мм - Быстрая печать'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Заказ'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='order_items',
        verbose_name='Товар'
    )
    quantity = models.IntegerField('Количество', default=1, validators=[MinValueValidator(1)])
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)

    # Специфические параметры для 3D печати
    color_choice = models.CharField('Выбранный цвет', max_length=50, blank=True)
    infill_percent = models.IntegerField('Процент заполнения', default=20,
                                         choices=INFILL_CHOICES,
                                         validators=[MinValueValidator(0), MaxValueValidator(100)])
    layer_height = models.DecimalField('Высота слоя (мм)', max_digits=4, decimal_places=2,
                                       default=0.20, choices=LAYER_HEIGHT_CHOICES,
                                       blank=True, null=True)

    # Параметры для SLA печати (смолы)
    resin_type = models.CharField('Тип смолы', max_length=50, blank=True)
    exposure_time = models.IntegerField('Время экспозиции (сек)', blank=True, null=True)

    # Дополнительные услуги
    need_support = models.BooleanField('Требуются поддержки', default=True)
    need_polishing = models.BooleanField('Шлифовка', default=False)
    need_painting = models.BooleanField('Покраска', default=False)

    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказов'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def get_total(self):
        """Возвращает стоимость позиции"""
        # Проверяем, что price и quantity не None
        price = self.price or 0
        quantity = self.quantity or 0

        total = price * quantity

        # Добавляем стоимость дополнительных услуг
        if self.need_polishing:
            total += 500  # Стоимость шлифовки
        if self.need_painting:
            total += 1000  # Стоимость покраски

        return total

    def get_infill_display(self):
        """Возвращает отображаемое имя процента заполнения"""
        return f'{self.infill_percent}%'

    def calculate_material_weight(self, model_volume_cm3):
        """Рассчитать вес материала на основе объема модели и заполнения"""
        # Плотность PLA ~ 1.24 г/см³
        density = 1.24
        # Объем с учетом заполнения
        effective_volume = model_volume_cm3 * (self.infill_percent / 100)
        return effective_volume * density


class CalculationHistory(models.Model):
    """История расчетов калькулятора"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Пользователь')

    # Параметры расчета
    material_type = models.CharField('Тип материала', max_length=50)
    volume = models.FloatField('Объем модели (см³)')
    infill = models.IntegerField('Процент заполнения (%)', default=20)
    layer_height = models.FloatField('Высота слоя (мм)', default=0.2)

    # Результаты расчета
    weight = models.FloatField('Вес модели (г)')
    material_cost = models.DecimalField('Стоимость материала', max_digits=10, decimal_places=2)
    print_cost = models.DecimalField('Стоимость печати', max_digits=10, decimal_places=2)
    total_cost = models.DecimalField('Итоговая стоимость', max_digits=10, decimal_places=2)

    created_at = models.DateTimeField('Дата расчета', auto_now_add=True)

    class Meta:
        verbose_name = 'История расчета'
        verbose_name_plural = 'История расчетов'
        ordering = ['-created_at']

    def __str__(self):
        return f'Расчет от {self.created_at.strftime("%d.%m.%Y %H:%M")} - {self.total_cost} руб.'


class UserProfile(models.Model):
    """Расширенный профиль пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name='Пользователь')

    # Контактная информация
    phone = models.CharField('Телефон', max_length=20, blank=True)
    avatar = models.ImageField('Аватар', upload_to='avatars/', blank=True, null=True)

    # Адрес по умолчанию
    default_address = models.TextField('Адрес по умолчанию', blank=True)

    # Предпочтения
    preferred_material = models.CharField('Предпочитаемый материал', max_length=50, blank=True)
    notifications_enabled = models.BooleanField('Уведомления по email', default=True)

    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f'Профиль: {self.user.username}'


class ProductImage(models.Model):
    """Модель для дополнительных фотографий товара"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Товар'
    )
    image = models.ImageField(
        'Фотография',
        upload_to='products/%Y/%m/%d/'
    )
    title = models.CharField(
        'Название',
        max_length=100,
        blank=True,
        help_text='Например: "Вид спереди", "В упаковке"'
    )
    is_main = models.BooleanField(
        'Основное фото',
        default=False,
        help_text='Отметьте, если это главное фото товара'
    )
    order = models.IntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Дата добавления', auto_now_add=True)

    class Meta:
        verbose_name = 'Фотография товара'
        verbose_name_plural = 'Фотографии товаров'
        ordering = ['order', '-is_main', 'created_at']

    def __str__(self):
        return f'Фото для {self.product.name} - {self.order}'

    def save(self, *args, **kwargs):
        # Если это основное фото, убираем отметку у других фото этого товара
        if self.is_main:
            ProductImage.objects.filter(product=self.product, is_main=True).update(is_main=False)
        super().save(*args, **kwargs)


# Сигнал для автоматического создания профиля при регистрации
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()