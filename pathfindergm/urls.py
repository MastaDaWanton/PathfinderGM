from django.conf import settings
from django.contrib.staticfiles.views import serve as static_serve
from django.urls import path, re_path

from play import class_views, race_views, spell_views, craft_views, home_views, views

urlpatterns = [
    path("", home_views.home, name="home"),
    path("play/", views.table, name="table"),
    path("api/state", views.state, name="state"),
    # The heartbeat every page sends so the process can tell an open window from a
    # closed one. See `pathfindergm/liveness.py` for the four hours of orphaned server
    # that made it necessary.
    path("api/alive", views.alive, name="alive"),
    path("api/sheet", views.sheet, name="sheet"),
    path("api/slots", views.slots, name="slots"),
    path("api/spells/prepare", views.prepare_spells, name="prepare_spells"),
    path("api/level-up", views.level_up, name="level_up"),
    path("api/feats", views.feat_search, name="feat_search"),
    path("licence", views.licence, name="licence"),
    path("api/characters", views.characters, name="characters"),
    path("api/character/new", views.new_character, name="new_character"),
    path("api/character/switch", views.switch_character, name="switch_character"),
    path("api/resurrect", views.resurrect, name="resurrect"),
    path("api/say", views.say, name="say"),
    path("api/roll", views.roll, name="roll"),
    path("api/combat/act", views.combat_act, name="combat_act"),
    path("api/use", views.use_item, name="use_item"),
    path("api/character/gender", views.set_gender, name="set_gender"),
    path("api/trade", views.trade, name="trade"),
    path("api/trade/do", views.trade_do, name="trade_do"),
    path("craft/", craft_views.craft_page, name="craft"),
    path("api/world/<str:world_id>", home_views.world_detail, name="world_detail"),
    path("api/bench/<str:bench_id>", home_views.bench, name="bench"),
    path("api/worlds", home_views.worlds, name="worlds"),
    path("api/worlds/import", home_views.import_world, name="import_world"),
    path("api/start", home_views.start_in_world, name="start_in_world"),
    path("api/resume", home_views.resume, name="resume"),
    path("api/create/options", home_views.creation_options, name="creation_options"),
    path("api/character/create", home_views.create_character, name="create_character"),
    path("api/character/delete", home_views.delete_character,
         name="delete_character"),
    path("api/settings/models", home_views.model_settings,
         name="model_settings"),
    path("api/homebrew/rules", home_views.house_rules, name="house_rules"),
    path("api/homebrew/races/import", home_views.import_races, name="import_races"),
    path("api/effects/catalogue", home_views.effect_catalogue, name="effect_catalogue"),
    path("api/kinds", home_views.kind_catalogue, name="kind_catalogue"),
    path("api/effects/preview", home_views.effect_preview, name="effect_preview"),
    path("api/consumables", home_views.save_consumable, name="save_consumable"),
    path("api/bench/<str:bench_id>/open/<str:thing_id>", home_views.open_thing,
         name="open_thing"),
    path("api/bench/<str:bench_id>/save", home_views.save_thing, name="save_thing"),
    # These three sit above `api/spells/<spell_id>` deliberately: Django takes the first
    # match, and that pattern happily reads "list" and "save" as the name of a spell.
    path("api/spells/list", spell_views.spell_list, name="spell_list"),
    path("api/spells/start/<str:spell_id>", spell_views.spell_start, name="spell_start"),
    path("api/spells/save", spell_views.spell_save, name="spell_save"),
    path("api/spells", home_views.spell_search, name="spell_search"),
    path("api/spells/<str:spell_id>", home_views.spell_detail, name="spell_detail"),
    path("api/craft/ingredients", craft_views.craft_ingredients, name="craft_ingredients"),
    path("api/craft/preview", craft_views.craft_preview, name="craft_preview"),
    path("api/craft/do", craft_views.craft_do, name="craft_do"),
    path("api/craft/recipes", craft_views.craft_recipes, name="craft_recipes"),
    path("api/forage/table", craft_views.forage_table, name="forage_table"),
    path("api/forage", craft_views.forage_do, name="forage_do"),
    path("api/wear", views.wear_item, name="wear_item"),
    path("api/craftaction", craft_views.craft_action, name="craft_action"),
    # The acquisition hub: what can be gone out and got, here, and the doing of it.
    path("api/craft/actions", craft_views.craft_actions, name="craft_actions"),
    path("api/craft/excursion", craft_views.craft_excursion, name="craft_excursion"),
    path("api/travel", craft_views.travel_to, name="travel_to"),
    # The class builder. A page rather than a bench tab because a class is not a flat
    # form: its level table and its paths are repeating structures, and the effect
    # builder's one-card-per-thing shape cannot hold either.
    path("homebrew/classes/", class_views.class_builder, name="class_builder"),
    path("homebrew/spells/", spell_views.spell_builder, name="spell_builder"),
    path("homebrew/races/", race_views.race_builder, name="race_builder"),
    path("api/races/open/<str:race_id>", race_views.race_open, name="race_open"),
    path("api/classes/catalogue", class_views.class_catalogue, name="class_catalogue"),
    path("api/classes/scaffold/<str:kind>", class_views.class_scaffold,
         name="class_scaffold"),
    path("api/classes/open/<str:class_id>", class_views.class_open, name="class_open"),
    path("api/classes/validate", class_views.class_validate, name="class_validate"),
    path("api/classes/save", class_views.class_save, name="class_save"),

    # Static files, routed explicitly rather than left to the runserver handler.
    #
    # `runserver` inserts this route itself and the frozen exe does not run `runserver`,
    # so without this line every page in the packaged build loads with no CSS backgrounds,
    # no fonts and no dice — and does so *silently*, because a missing background image is
    # not an error anywhere. "Anything available in a browser must also work in the
    # packaged desktop app" is the standing constraint this satisfies.
    #
    # `insecure=True` because the view refuses to serve when DEBUG is off, and this app is
    # a single-user process bound to 127.0.0.1 with no deployment and no untrusted client.
    # The alternative — a `collectstatic` step into a directory the installer has to
    # create — puts derived files outside the install root, which is the exact shape
    # CLAUDE.md's stale-cache rule was written about.
    re_path(r"^%s(?P<path>.*)$" % settings.STATIC_URL.lstrip("/"), static_serve,
            {"insecure": True}, name="static"),
]
