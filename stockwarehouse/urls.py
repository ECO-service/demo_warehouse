"""ecotrading URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
import debug_toolbar
from .views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('operation.urls')),
    path('customer/<int:pk>', customer_view, name='customer_detail'),
    path('loginuser/', LoginUser, name="loginuser"),
    path('logout/', LogoutUser, name="logout"),
    path('clicklogin', clicklogin, name="clicklogin"),
    path('',LoginUser,name=""),
    path('change_password/', change_password, name='change_password'),
    path('cal_trading_power_customer/', cal_trading_power_customer, name='cal_trading_power_customer'),
    path('<int:pk>/assumption_sell_stock/<int:port_pk>', assumption_sell_stock, name='assumption_sell_stock'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
