from django.urls import path

from play import views

urlpatterns = [
    path("", views.table, name="table"),
    path("api/state", views.state, name="state"),
    path("api/sheet", views.sheet, name="sheet"),
    path("api/slots", views.slots, name="slots"),
    path("api/characters", views.characters, name="characters"),
    path("api/character/new", views.new_character, name="new_character"),
    path("api/character/switch", views.switch_character, name="switch_character"),
    path("api/say", views.say, name="say"),
    path("api/roll", views.roll, name="roll"),
]
