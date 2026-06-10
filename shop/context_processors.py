def cart_count(request):
    """Контекстный процессор для отображения количества товаров в корзине"""
    cart = request.session.get('cart', {})
    total_items = 0

    for item in cart.values():
        # Проверяем, является ли элемент словарем (новая структура) или числом (старая)
        if isinstance(item, dict):
            total_items += item.get('quantity', 0)
        else:
            total_items += item

    return {'cart_count': total_items}