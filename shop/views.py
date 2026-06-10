from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import Q, Sum
from .models import Product, Category, Material, Order, OrderItem, CalculationHistory, UserProfile
from .forms import UserRegistrationForm, OrderForm, OrderItemForm, CustomOrderForm
from django.conf import settings
import json, os


def home(request):
    """Главная страница"""
    featured_products = Product.objects.filter(is_featured=True, is_available=True)[:4]
    return render(request, 'shop/home.html', {
        'featured_products': featured_products
    })


def calculator(request):
    """Калькулятор стоимости 3D печати"""
    result = None

    if request.method == 'POST':
        try:
            # Получаем данные из формы
            material_type = request.POST.get('material_type', 'pla')
            volume = float(request.POST.get('volume', 0))
            infill = int(request.POST.get('infill', 20))
            layer_height = float(request.POST.get('layer_height', 0.2))

            # Цены материалов (руб/г)
            material_prices = {
                'pla': 5,
                'abs': 6,
                'petg': 7,
                'resin': 8
            }

            # Плотность материалов (г/см³)
            densities = {
                'pla': 1.24,
                'abs': 1.04,
                'petg': 1.27,
                'resin': 1.1
            }

            # Получаем цену и плотность
            price_per_gram = material_prices.get(material_type, 5)
            density = densities.get(material_type, 1.24)

            # Расчет веса с учетом заполнения
            # Вес = объем * плотность * (заполнение/100)
            weight = volume * density * (infill / 100)

            # Стоимость материала
            material_cost = weight * price_per_gram

            # Стоимость печати (включает амортизацию, электроэнергию, время)
            # Коэффициент сложности в зависимости от высоты слоя
            layer_factor = {
                0.1: 1.5,  # высокое качество - дольше
                0.15: 1.2,
                0.2: 1.0,  # стандарт
                0.25: 0.8,
                0.3: 0.6  # быстрая печать
            }
            complexity = layer_factor.get(layer_height, 1.0)

            # Стоимость печати = вес * базовая_стоимость * коэффициент_сложности
            base_print_cost = 3  # руб/г базовая стоимость печати
            print_cost = weight * base_print_cost * complexity

            # Итоговая стоимость
            total_cost = material_cost + print_cost

            # Округляем до 2 знаков
            result = {
                'weight': round(weight, 2),
                'material_cost': round(material_cost, 2),
                'print_cost': round(print_cost, 2),
                'total': round(total_cost, 2)
            }

            # Сохраняем расчет в историю (если пользователь авторизован)
            if request.user.is_authenticated:
                try:
                    CalculationHistory.objects.create(
                        user=request.user,
                        material_type=material_type,
                        volume=volume,
                        infill=infill,
                        layer_height=layer_height,
                        weight=weight,
                        material_cost=material_cost,
                        print_cost=print_cost,
                        total_cost=total_cost
                    )
                except Exception as e:
                    # Если модель не создана, просто игнорируем
                    pass

            messages.success(request, 'Расчет выполнен успешно!')

        except Exception as e:
            messages.error(request, f'Ошибка при расчете: {str(e)}')
            result = None

    return render(request, 'shop/calculator.html', {'result': result})


def product_list(request):
    """Список товаров с фильтрацией"""
    products = Product.objects.filter(is_available=True)

    # Исключаем товары, скрытые из каталога
    products = Product.objects.filter(is_available=True, hide_from_catalog=False)

    # Поиск
    search_query = request.GET.get('search')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Фильтрация по категории изделия
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    # Фильтрация по виду пластика
    material_slug = request.GET.get('material')
    if material_slug:
        material = get_object_or_404(Material, slug=material_slug)
        products = products.filter(material=material)

    # Фильтрация по типу услуги
    product_type = request.GET.get('product_type')
    if product_type:
        products = products.filter(product_type=product_type)

    # Фильтрация по цене
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Сортировка
    sort = request.GET.get('sort')
    if sort == 'name':
        products = products.order_by('name')
    elif sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    else:
        products = products.order_by('-created_at')

    # Пагинация
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    # Данные для фильтров
    categories = Category.objects.filter(is_active=True)
    materials = Material.objects.filter(is_active=True)

    return render(request, 'shop/product_list.html', {
        'products': products_page,
        'categories': categories,
        'materials': materials,
        'selected_category': category_slug,
        'selected_material': material_slug,
        'selected_type': product_type,
        'min_price': min_price,
        'max_price': max_price,
        'search_query': search_query,
    })


def product_detail(request, slug):
    """Детальная страница товара"""
    product = get_object_or_404(Product, slug=slug, is_available=True)

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))

        if product.product_type == 'ready_product' and quantity > product.stock:
            messages.error(request, f'Недостаточно товара в наличии. Доступно: {product.stock} шт.')
            return redirect('product_detail', slug=product.slug)

        cart = request.session.get('cart', {})
        product_id = str(product.id)

        if product_id in cart:
            cart[product_id] += quantity
        else:
            cart[product_id] = quantity

        request.session['cart'] = cart
        messages.success(request, f'Товар "{product.name}" в количестве {quantity} шт. добавлен в корзину!')
        return redirect('cart')

    # Получаем все фотографии товара
    product_images = product.images.all()

    # Рекомендуемые товары
    related_products = Product.objects.filter(
        category=product.category,
        is_available=True
    ).exclude(id=product.id)[:4]

    return render(request, 'shop/product_detail.html', {
        'product': product,
        'product_images': product_images,
        'related_products': related_products
    })


def cart(request):
    """Корзина"""
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0
    total_quantity = 0

    for pid, data in cart.items():
        product = get_object_or_404(Product, id=int(pid))

        if isinstance(data, dict):
            quantity = data.get('quantity', 0)
            params = data.get('params', {})

            # Если это услуга печати по чертежам и есть расчетная цена
            if product.slug == 'pechat-po-chertezham' and params.get('calculated_price'):
                price_per_item = params['calculated_price']
            else:
                price_per_item = float(product.price)
        else:
            quantity = data
            params = {}
            price_per_item = float(product.price)

        subtotal = price_per_item * quantity
        total += subtotal
        total_quantity += quantity
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'price': price_per_item,
            'subtotal': subtotal,
            'params': params
        })

    return render(request, 'shop/cart.html', {
        'cart_items': cart_items,
        'total': total,
        'total_quantity': total_quantity
    })


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    cart = request.session.get('cart', {})
    pid = str(product_id)
    if pid in cart:
        cart[pid]['quantity'] += quantity
    else:
        cart[pid] = {'quantity': quantity, 'params': {}}
    request.session['cart'] = cart
    return redirect('cart')


def remove_from_cart(request, product_id):
    """Удаление из корзины"""
    cart = request.session.get('cart', {})
    pid = str(product_id)
    if pid in cart:
        del cart[pid]
        request.session['cart'] = cart
    return redirect('cart')


def update_cart(request, product_id):
    """Обновление количества в корзине"""
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 0))
        cart = request.session.get('cart', {})
        pid = str(product_id)

        if pid in cart:
            if isinstance(cart[pid], dict):
                if quantity > 0:
                    cart[pid]['quantity'] = quantity
                else:
                    del cart[pid]
            else:
                # Старая структура
                if quantity > 0:
                    cart[pid] = quantity
                else:
                    del cart[pid]

        request.session['cart'] = cart
    return redirect('cart')


def checkout(request):
    """Оформление заказа"""
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'Корзина пуста')
        return redirect('cart')

    if request.method == 'POST':
        form = OrderForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            order.save()

            total = 0
            for pid, data in cart.items():
                product = get_object_or_404(Product, id=int(pid))

                if isinstance(data, dict):
                    quantity = data.get('quantity', 0)
                    params = data.get('params', {})

                    # Получаем цену из параметров или из продукта
                    if product.slug == 'pechat-po-chertezham' and params.get('calculated_price'):
                        price = params['calculated_price']
                    else:
                        price = float(product.price)
                else:
                    quantity = data
                    params = {}
                    price = float(product.price)

                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=price,  # Используем расчетную цену
                    color_choice=params.get('color', ''),
                    infill_percent=params.get('infill', 20),
                    layer_height=params.get('layer_height', 0.2),
                    need_support=params.get('need_support', True),
                    need_polishing=params.get('need_polishing', False),
                    need_painting=params.get('need_painting', False)
                )

                # Если есть файл модели — привязываем к заказу
                if params and 'model_file' in params:
                    temp_path = params['model_file']
                    full_temp_path = os.path.join(settings.MEDIA_ROOT, temp_path)
                    if os.path.exists(full_temp_path):
                        new_name = f"orders/{order.id}/{os.path.basename(temp_path)}"
                        with open(full_temp_path, 'rb') as f:
                            new_path = default_storage.save(new_name, ContentFile(f.read()))
                        order.model_file = new_path
                        order.model_notes = f"Материал: {params.get('material')}\nЦвет: {params.get('color')}\nЗаполнение: {params.get('infill')}%\nВысота слоя: {params.get('layer_height')} мм"
                        order.save()
                        os.remove(full_temp_path)

                total += order_item.get_total()

            order.subtotal = total
            order.total = total + order.delivery_cost
            order.save()

            request.session['cart'] = {}
            messages.success(request, f'Заказ #{order.order_number} успешно оформлен!')
            return redirect('order_confirmation', order_id=order.id)
        else:
            messages.error(request, f'Ошибка формы: {form.errors}')
    else:
        form = OrderForm(user=request.user)

    total = 0
    cart_items = []
    for pid, data in cart.items():
        product = get_object_or_404(Product, id=int(pid))

        if isinstance(data, dict):
            quantity = data.get('quantity', 0)
            params = data.get('params', {})
            if product.slug == 'pechat-po-chertezham' and params.get('calculated_price'):
                price = params['calculated_price']
            else:
                price = float(product.price)
        else:
            quantity = data
            params = {}
            price = float(product.price)

        subtotal = price * quantity
        total += subtotal
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'price': price,
            'subtotal': subtotal,
            'params': params
        })

    return render(request, 'shop/checkout.html', {
        'form': form,
        'cart_items': cart_items,
        'total': total,
    })


def upload_model(request):
    """Страница загрузки чертежа"""
    if request.method == 'POST':
        form = CustomOrderForm(request.POST, request.FILES)
        if form.is_valid():
            # Сохраняем файл во временную папку
            uploaded_file = form.cleaned_data['model_file']
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            file_path = default_storage.save(
                os.path.join('temp', uploaded_file.name),
                ContentFile(uploaded_file.read())
            )

            # Получаем параметры для расчета цены
            material = form.cleaned_data['material_type']
            infill = form.cleaned_data['infill_percent']
            layer_height = float(form.cleaned_data['layer_height'])
            need_polishing = form.cleaned_data['need_polishing']
            need_painting = form.cleaned_data['need_painting']

            # Рассчитываем примерную стоимость
            # Для расчета нужен объем, но его пользователь вводит вручную
            # Будем использовать примерный вес 50г или тот, что ввел пользователь
            # Пока используем стандартный расчет
            material_prices = {'pla': 5, 'abs': 6, 'petg': 7, 'resin': 8}
            layer_factors = {0.1: 1.5, 0.15: 1.2, 0.2: 1.0, 0.25: 0.8, 0.3: 0.6}

            # Временный вес (пользователь введет объем позже)
            estimated_weight = 50  # примерный вес 50г
            price_per_gram = material_prices.get(material, 5)
            layer_factor = layer_factors.get(layer_height, 1.0)

            material_cost = estimated_weight * price_per_gram
            print_cost = estimated_weight * 3 * layer_factor

            extra_cost = 0
            if need_polishing:
                extra_cost += 500
            if need_painting:
                extra_cost += 1000

            calculated_price = material_cost + print_cost + extra_cost

            # Параметры с ценой
            params = {
                'model_file': file_path,
                'material': material,
                'color': form.cleaned_data['color'],
                'infill': infill,
                'layer_height': layer_height,
                'need_support': form.cleaned_data['need_support'],
                'need_polishing': need_polishing,
                'need_painting': need_painting,
                'calculated_price': calculated_price,  # Добавляем рассчитанную цену
                'estimated_weight': estimated_weight
            }
            quantity = form.cleaned_data['quantity']

            # Ищем услугу "Печать по чертежам"
            try:
                service = Product.objects.get(slug='pechat-po-chertezham')
            except Product.DoesNotExist:
                messages.error(request, 'Услуга печати по чертежам не найдена.')
                return redirect('upload_model')

            # Добавляем в корзину
            cart = request.session.get('cart', {})
            pid = str(service.id)
            if pid in cart:
                cart[pid]['quantity'] += quantity
                cart[pid]['params'] = params
            else:
                cart[pid] = {'quantity': quantity, 'params': params}
            request.session['cart'] = cart

            messages.success(request,
                             f'Модель добавлена в корзину! Примерная стоимость: {calculated_price * quantity:.2f} ₽')
            return redirect('cart')
        else:
            messages.error(request, f'Ошибка: {form.errors}')
    else:
        form = CustomOrderForm()

    return render(request, 'shop/upload_model.html', {'form': form})


@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    # Разрешаем просмотр только владельцу или сотруднику (можно для всех, кто знает ссылку)
    if order.user != request.user and not request.user.is_staff:
        messages.error(request, 'У вас нет доступа к этому заказу')
        return redirect('home')
    return render(request, 'shop/order_confirmation.html', {'order': order})


def register(request):
    """Регистрация пользователя"""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('home')
    else:
        form = UserRegistrationForm()

    return render(request, 'shop/register.html', {'form': form})


def user_login(request):
    """Вход пользователя"""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('home')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')

    return render(request, 'shop/login.html')


def user_logout(request):
    """Выход пользователя"""
    logout(request)
    messages.success(request, 'Вы вышли из системы')
    return redirect('home')


def admin_login_page(request):
    """Страница входа в админ-панель"""
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect('admin:index')
    return render(request, 'shop/admin_login.html')


def is_admin(user):
    """Проверка, является ли пользователь администратором"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@user_passes_test(is_admin, login_url='login')
def admin_dashboard(request):
    """Перенаправление в админ-панель"""
    return redirect('admin:index')


@login_required
def profile(request):
    """Личный кабинет пользователя"""
    return render(request, 'shop/profile.html')


@login_required
def my_orders(request):
    """Страница со списком заказов пользователя"""
    orders = Order.objects.filter(user=request.user)

    # Фильтрация по статусу
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    # Поиск по номеру заказа
    search_query = request.GET.get('search')
    if search_query:
        orders = orders.filter(order_number__icontains=search_query)

    # Сортировка
    sort = request.GET.get('sort', '-created_at')
    if sort == 'created_at':
        orders = orders.order_by('created_at')
    elif sort == '-total':
        orders = orders.order_by('-total')
    elif sort == 'total':
        orders = orders.order_by('total')
    else:
        orders = orders.order_by('-created_at')

    # Пагинация
    paginator = Paginator(orders, 10)  # 10 заказов на страницу
    page_number = request.GET.get('page')
    orders_page = paginator.get_page(page_number)

    return render(request, 'shop/my_orders.html', {
        'orders': orders_page,
        'selected_status': status_filter,
        'sort': sort,
        'search_query': search_query,
    })


@login_required
def cancel_order(request, order_id):
    """Отмена заказа"""
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Проверяем, можно ли отменить заказ
    if order.can_cancel():
        order.status = 'cancelled'
        order.save()
        messages.success(request, f'Заказ #{order.order_number} успешно отменен')
    else:
        messages.error(request, 'Этот заказ нельзя отменить')

    return redirect('my_orders')


@login_required
def order_detail(request, order_id):
    """Детали конкретного заказа"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order_detail.html', {'order': order})


@login_required
def calculation_history(request):
    """История расчетов пользователя"""
    calculations = CalculationHistory.objects.filter(user=request.user)[:50]
    return render(request, 'shop/calculation_history.html', {'calculations': calculations})


@login_required
def profile(request):
    """Личный кабинет пользователя"""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')

    # Статистика
    orders_count = orders.count()
    active_orders_count = orders.exclude(status__in=['completed', 'cancelled']).count()
    completed_orders_count = orders.filter(status='completed').count()
    total_spent = orders.filter(status='completed').aggregate(Sum('total'))['total__sum'] or 0

    return render(request, 'shop/profile.html', {
        'orders': orders,
        'orders_count': orders_count,
        'active_orders_count': active_orders_count,
        'completed_orders_count': completed_orders_count,
        'total_spent': total_spent,
    })


@login_required
def update_profile(request):
    """Обновление профиля пользователя"""
    if request.method == 'POST':
        user = request.user
        profile = user.profile

        # Обновляем данные пользователя
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()

        # Обновляем профиль
        profile.phone = request.POST.get('phone', '')
        profile.default_address = request.POST.get('default_address', '')
        profile.preferred_material = request.POST.get('preferred_material', '')
        profile.notifications_enabled = request.POST.get('notifications_enabled') == 'on'

        # Обновляем аватар
        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']

        profile.save()

        messages.success(request, 'Профиль успешно обновлен!')

    return redirect('profile')


@login_required
def order_detail(request, order_id):
    """Детальная страница заказа"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order_detail.html', {'order': order})


def calculator(request):
    """Калькулятор стоимости 3D печати"""
    if request.method == 'POST':
        # Получаем параметры из формы
        volume = float(request.POST.get('volume', 0))
        material_type = request.POST.get('material_type')
        infill = int(request.POST.get('infill', 20))
        layer_height = float(request.POST.get('layer_height', 0.2))

        # Примерная стоимость за грамм
        price_per_gram = 5  # рублей

        # Расчет веса (плотность PLA ~ 1.24 г/см³)
        weight = volume * 1.24 * (infill / 100)

        # Стоимость материалов
        material_cost = weight * price_per_gram

        # Стоимость печати (условная)
        print_cost = material_cost * 1.5

        total_cost = material_cost + print_cost

        return render(request, 'shop/calculator.html', {
            'result': {
                'weight': round(weight, 2),
                'material_cost': round(material_cost, 2),
                'print_cost': round(print_cost, 2),
                'total': round(total_cost, 2)
            }
        })

    return render(request, 'shop/calculator.html')