from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Order, OrderItem


class UserRegistrationForm(UserCreationForm):
    """Форма регистрации пользователя"""
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Email'
    }))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if field_name == 'username':
                field.widget.attrs['placeholder'] = 'Имя пользователя'
            elif field_name == 'password1':
                field.widget.attrs['placeholder'] = 'Пароль'
            elif field_name == 'password2':
                field.widget.attrs['placeholder'] = 'Подтверждение пароля'


class OrderForm(forms.ModelForm):
    # Для авторизованных: сохранить данные в профиль
    save_to_profile = forms.BooleanField(
        label='Сохранить эти данные в профиль',
        required=False,
        initial=True,
        help_text='Будут сохранены ваше имя, телефон и адрес'
    )
    # Для неавторизованных: создать аккаунт
    create_account = forms.BooleanField(
        label='Зарегистрироваться и сохранить данные',
        required=False,
        help_text='Создать аккаунт и сохранить данные для следующих заказов'
    )
    password = forms.CharField(
        label='Пароль',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Введите пароль для регистрации'
    )

    class Meta:
        model = Order
        fields = [
            'customer_name', 'customer_email', 'customer_phone',
            'delivery_address', 'delivery_notes', 'customer_comment'
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ваше полное имя'}),
            'customer_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email для связи'}),
            'customer_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 123-45-67'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Город, улица, дом, квартира'}),
            'delivery_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Особенности доставки'}),
            'customer_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Дополнительные пожелания к заказу'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            # Заполняем поля из профиля
            profile = user.profile
            self.fields['customer_name'].initial = user.get_full_name() or user.username
            self.fields['customer_email'].initial = user.email
            self.fields['customer_phone'].initial = profile.phone
            self.fields['delivery_address'].initial = profile.default_address
            self.fields['save_to_profile'].initial = True   # по умолчанию сохранять
            # Скрываем поля регистрации
            self.fields['create_account'].widget = forms.HiddenInput()
            self.fields['password'].widget = forms.HiddenInput()
        else:
            # Для неавторизованных скрываем поле сохранения в профиль
            self.fields['save_to_profile'].widget = forms.HiddenInput()
            self.fields['create_account'].initial = False
            self.fields['password'].required = False


class OrderItemForm(forms.ModelForm):
    """Форма для добавления товара в корзину"""

    class Meta:
        model = OrderItem
        fields = ['quantity', 'color_choice', 'infill_percent', 'layer_height',
                  'need_support', 'need_polishing', 'need_painting']
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'color_choice': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Выберите цвет'}),
            'infill_percent': forms.Select(attrs={'class': 'form-select'}),
            'layer_height': forms.Select(attrs={'class': 'form-select'}),
            'need_support': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'need_polishing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'need_painting': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CustomOrderForm(forms.Form):
    """Форма заказа по чертежам"""
    model_file = forms.FileField(
        label='3D модель',
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.stl,.obj,.3mf,.step'})
    )
    quantity = forms.IntegerField(
        label='Количество',
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    material_type = forms.ChoiceField(
        label='Материал',
        choices=[('pla', 'PLA'), ('abs', 'ABS'), ('petg', 'PETG'), ('resin', 'Resin')],
        initial='pla',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    color = forms.CharField(
        label='Цвет',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Белый, черный...'})
    )
    infill_percent = forms.IntegerField(
        label='Заполнение (%)',
        min_value=0,
        max_value=100,
        initial=20,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    layer_height = forms.ChoiceField(
        label='Высота слоя',
        choices=[
            (0.1, '0.1 мм - Высокое качество'),
            (0.15, '0.15 мм'),
            (0.2, '0.2 мм - Стандарт'),
            (0.25, '0.25 мм'),
            (0.3, '0.3 мм - Быстрая печать'),
        ],
        initial=0.2,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    need_support = forms.BooleanField(
        label='Поддержки',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    need_polishing = forms.BooleanField(
        label='Шлифовка (+500 руб.)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    need_painting = forms.BooleanField(
        label='Покраска (+1000 руб.)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_model_file(self):
        model_file = self.cleaned_data.get('model_file')
        if model_file:
            ext = '.' + model_file.name.split('.')[-1].lower()
            allowed = ['.stl', '.obj', '.3mf', '.step']
            if ext not in allowed:
                raise forms.ValidationError(f'Разрешены только файлы: {", ".join(allowed)}')
            if model_file.size > 500 * 1024 * 1024:
                raise forms.ValidationError('Файл не должен превышать 500 МБ')
        return model_file


class OrderForm(forms.ModelForm):
    """Форма оформления заказа"""
    class Meta:
        model = Order
        fields = ['customer_name', 'customer_email', 'customer_phone', 'delivery_address', 'delivery_notes', 'customer_comment']
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'customer_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'customer_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 123-45-67'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'delivery_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'customer_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.fields['customer_name'].initial = user.get_full_name() or user.username
            self.fields['customer_email'].initial = user.email
            try:
                if hasattr(user, 'profile') and user.profile:
                    self.fields['customer_phone'].initial = user.profile.phone
                    self.fields['delivery_address'].initial = user.profile.default_address
            except:
                pass
