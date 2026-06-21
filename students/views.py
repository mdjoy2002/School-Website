from django.shortcuts import render
# Create your views here.
from django.http import HttpResponse
# Create your views here.

def student_home(request):
    return HttpResponse("students app এর হোম পেজে স্বাগতম!")