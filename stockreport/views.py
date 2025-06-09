from django.http import HttpResponse
from django.shortcuts import render    


def home(request):

    return HttpResponse("Welcome to the Stock Report Application!") 