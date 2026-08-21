from django.urls import path

from play import craft_views, views

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
    path("craft/", craft_views.craft_page, name="craft"),
    path("api/craft/ingredients", craft_views.craft_ingredients, name="craft_ingredients"),
    path("api/craft/preview", craft_views.craft_preview, name="craft_preview"),
    path("api/craft/do", craft_views.craft_do, name="craft_do"),
    path("api/craft/recipes", craft_views.craft_recipes, name="craft_recipes"),
]
