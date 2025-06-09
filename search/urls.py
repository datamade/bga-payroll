from django.urls import path
from . import api, views

urlpatterns = [
    path('', views.SearchView.as_view(), name='search'),
    path('suggest/', views.EntityLookup.as_view(), name='suggest'), 
    path('employer/', api.EmployerSearchView.as_view(), name='search-employer'),
    path('person/', api.PersonSearchView.as_view(), name='search-person'),
]