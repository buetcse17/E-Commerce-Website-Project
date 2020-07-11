from django.shortcuts import render
from django.db import connections
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import reverse
from django.contrib.auth.decorators import login_required

# Create your views here.
def item_page(request, product_id, seller_id):
    return render(request, 'item.html')

def add_item_page(request):
    pass

def add_advert_page(request):
    pass

def add_offer_page(request):
    pass

def search_result(request, search_string):
    returnToHome = True
    for i in search_string:
        if i!='_':
            returnToHome = False
    if returnToHome:
        return HttpResponseRedirect(reverse('home_page'))

    return render(request, 'search_result.html')
