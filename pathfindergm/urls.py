from django.urls import path

from play import views

urlpatterns = [
    path("", views.table, name="table"),
    path("api/state", views.state, name="state"),
    path("api/sheet", views.sheet, name="sheet"),
    path("api/say", views.say, name="say"),
    path("api/roll", views.roll, name="roll"),
]
