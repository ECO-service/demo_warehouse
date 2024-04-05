# forms.py
from django import forms
from datetime import date


class SellingForm(forms.Form):
    selling_price = forms.FloatField(label='Giá bán', widget=forms.TextInput(attrs={'placeholder': 'Nhập giá đủ phần nghìn'}))
    selling_date = forms.DateField(label='Ngày bán')
