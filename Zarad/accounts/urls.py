from django.conf.urls import url
from . import views

app_name = 'accounts'

urlpatterns = [
    url(r"login/$", views.login_page, name='login'),
    url(r"logout/$", views.logout_page, name='logout'),
    url(r"signup/$", views.signup_page, name='signup'),
    url(r"myaccount/(?P<firstPage>\w+)/$", views.myaccount, name='myaccount'),
]
