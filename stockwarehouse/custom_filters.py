from django import template

register = template.Library()

@register.filter(name='format_currency_0')
def format_currency_0(value):
    # Định dạng giá trị số với dấu phẩy và cách hiển thị 3 số 0
    return "{:,.0f}".format(value)


@register.filter(name='format_currency_2')
def format_currency_2(value):
    # Định dạng giá trị số với dấu phẩy và cách hiển thị 3 số 0
    return "{:,.2f}".format(value)