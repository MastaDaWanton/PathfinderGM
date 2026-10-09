from django.conf import settings
import mimetypes

from django.contrib.staticfiles.views import serve as _serve

# Django's static view takes a file's type from `mimetypes`, which on Windows reads the
# registry — and on some machines the registry says `.js` is `text/plain`. Classic
# scripts still run then; the play table's six script files (2026-09-25) would not survive
# a move to modules. Stated here rather than left to the machine.
mimetypes.add_type("text/javascript", ".js")
# The same for stylesheets, pinned before the first one shipped (theme-v2.css,
# 2026-09-30; every page before it styled itself inline). A stylesheet answered as
# `text/plain` is not applied by a page in standards mode, and nothing on screen says why:
# the page just loses its materials on the one machine whose registry disagrees.
mimetypes.add_type("text/css", ".css")
# And the soundtrack (play/static/audio/music, 2026-10-02), pinned for the same reason as
# the two above: the type is this file's to say, not whatever one machine's registry holds.
mimetypes.add_type("audio/mpeg", ".mp3")


def static_serve(request, path, **kwargs):
    """The static view, told never to be trusted from cache without asking.

    The Electron shell keeps its disk cache in the user data directory, which outlives
    reinstalls, on an origin that never changes — World Bible served a five-day-old
    stylesheet exactly that way. The play table's scripts carry a content stamp
    (`play/templatetags/assets.py`); `no-cache` covers everything else.
    """
    response = _serve(request, path, **kwargs)
    response["Cache-Control"] = "no-cache"
    return response
from django.urls import path, re_path

from play import (class_views, outfit_views, race_views, setup_views, spell_views,
                  craft_views, home_views, views, bench_views, herb_views, forge_views,
                  works_views, enchant_views, alchemy_views, tradecraft_views,
                  report_views)

urlpatterns = [
    path("", home_views.home, name="home"),
    path("play/", views.table, name="table"),
    path("api/state", views.state, name="state"),
    # The conversation log a page at a time, for the panel's "Earlier…" (fix-interfaces
    # §2.10); `/api/state` carries only the latest entries.
    path("api/conversation", views.conversation, name="conversation"),
    path("api/history", views.history, name="history"),
    # The heartbeat every page sends so the process can tell an open window from a
    # closed one. See `pathfindergm/liveness.py` for the four hours of orphaned server
    # that made it necessary.
    path("api/alive", views.alive, name="alive"),
    # What a second device polls to learn the game moved without it. See
    # `play/concurrency.py` and `docs/lan-play.md`.
    path("api/revision", views.game_revision, name="game_revision"),
    # Playing from a phone: whether the network door is open, and the QR that opens it.
    # Loopback-only, enforced in the views — see `docs/lan-play.md`.
    path("api/lan", views.lan_status, name="lan_status"),
    path("api/lan/open", views.lan_open, name="lan_open"),
    path("api/lan/close", views.lan_close, name="lan_close"),
    path("api/sheet", views.sheet, name="sheet"),
    path("api/slots", views.slots, name="slots"),
    path("api/spells/prepare", views.prepare_spells, name="prepare_spells"),
    path("api/spells/learnable", views.learnable_spells, name="learnable_spells"),
    path("api/spells/learn", views.learn_spells, name="learn_spells"),
    path("api/spells/swap", views.swap_spell, name="swap_spell"),
    path("api/level-up", views.level_up, name="level_up"),
    path("api/level/feats", views.level_feat_menu, name="level_feat_menu"),
    path("api/level/feats/take", views.level_take_feats, name="level_take_feats"),
    path("api/level/points", views.level_take_points, name="level_take_points"),
    # Skill ranks, class choices and Blood Bending's Path B, owed by level and chosen on
    # the Class tab (docs/class-audit.md, lane 1).
    path("api/level/skills", views.level_take_skills, name="level_take_skills"),
    path("api/level/choices", views.level_choice_menu, name="level_choice_menu"),
    path("api/level/choose", views.level_take_choice, name="level_take_choice"),
    path("api/level/path", views.level_take_path, name="level_take_path"),
    path("api/feats", views.feat_search, name="feat_search"),
    path("licence", views.licence, name="licence"),
    # The manual, served from inside the app because that is where the player is: this
    # ships as one executable and a document in a repository is not a manual they have.
    path("manual", views.manual, name="manual"),
    path("api/characters", views.characters, name="characters"),
    path("api/character/new", views.new_character, name="new_character"),
    path("api/character/switch", views.switch_character, name="switch_character"),
    path("api/resurrect", views.resurrect, name="resurrect"),
    path("api/say", views.say, name="say"),
    path("api/talk", views.talk_act, name="talk_act"),
    path("api/cast", views.cast_act, name="cast_act"),
    path("api/roll", views.roll, name="roll"),
    # The face on its own, so the die can land before the narrator has finished. See
    # `views.roll_face` — it decides a number and changes nothing.
    path("api/roll/face", views.roll_face, name="roll_face"),
    path("api/combat/act", views.combat_act, name="combat_act"),
    path("api/use", views.use_item, name="use_item"),
    path("api/write", views.write, name="write"),
    path("api/character/gender", views.set_gender, name="set_gender"),
    path("api/trade", views.trade, name="trade"),
    path("api/trade/do", views.trade_do, name="trade_do"),
    # The trade uses by button (rules/tradecraft.py; options B and C, 2026-10-07).
    path("api/tradeskill", tradecraft_views.tradeskill_act, name="tradeskill_act"),
    path("api/tradeskill/offer", tradecraft_views.tradeskill_offer, name="tradeskill_offer"),
    path("craft/", craft_views.craft_page, name="craft"),
    path("api/world/<str:world_id>", home_views.world_detail, name="world_detail"),
    # The forge bench (docs/blacksmithing-contracts.md §7). Every fixed name sits above the
    # one pattern with a parameter, and the whole block above the homebrew benches'
    # `api/bench/<bench_id>`, so the herb bench's route-order bug (a fixed name read as a
    # parameter, test_bench_routes) cannot recur here (tests/test_forge_api.py pins it).
    path("api/forge/state", forge_views.forge_state, name="forge_state"),
    path("api/forge/check", forge_views.forge_check, name="forge_check"),
    path("api/forge/roll", forge_views.forge_roll, name="forge_roll"),
    path("api/forge/finish", forge_views.forge_finish, name="forge_finish"),
    path("api/forge/assay", forge_views.forge_assay, name="forge_assay"),
    path("api/forge/perks", forge_views.forge_perks, name="forge_perks"),
    path("api/forge/ledger", forge_views.forge_ledger, name="forge_ledger"),
    path("api/forge/ask", forge_views.forge_ask, name="forge_ask"),
    path("api/forge/material/<str:material_id>", forge_views.forge_material,
         name="forge_material"),
    # In progress, every craft's unfinished work (docs/enchanting-contracts.md §8.2). Lane
    # G's block; fixed names only, so no pattern below can read them as a parameter.
    path("api/works", works_views.works, name="works"),
    path("api/works/collect", works_views.works_collect, name="works_collect"),
    path("api/works/cancel", works_views.works_cancel, name="works_cancel"),
    # The enchanting bench (docs/enchanting-contracts.md §6). Lane E's block: every fixed
    # name above the one pattern with a parameter, and all of it above the homebrew
    # benches' `api/bench/<bench_id>` (the herb bench's route-order bug, test_bench_routes;
    # tests/test_enchant_api.py pins it).
    path("api/enchant/state", enchant_views.enchant_state, name="enchant_state"),
    path("api/enchant/check", enchant_views.enchant_check, name="enchant_check"),
    path("api/enchant/roll", enchant_views.enchant_roll, name="enchant_roll"),
    path("api/enchant/finish", enchant_views.enchant_finish, name="enchant_finish"),
    path("api/enchant/read", enchant_views.enchant_read, name="enchant_read"),
    path("api/enchant/identify", enchant_views.enchant_identify, name="enchant_identify"),
    path("api/enchant/wait", enchant_views.enchant_wait, name="enchant_wait"),
    path("api/enchant/perks", enchant_views.enchant_perks, name="enchant_perks"),
    path("api/enchant/ledger", enchant_views.enchant_ledger, name="enchant_ledger"),
    path("api/enchant/recipes", enchant_views.enchant_recipes, name="enchant_recipes"),
    # The magic items carried with their cards, read only (lane U1 for lane U5's ledger).
    path("api/enchant/items", enchant_views.enchant_items, name="enchant_items"),
    # Old enchanted items converted onto the layer (lane H): answer a question, mark seen.
    path("api/enchant/answer", enchant_views.enchant_answer, name="enchant_answer"),
    path("api/enchant/seen", enchant_views.enchant_seen, name="enchant_seen"),
    path("api/enchant/essence/<str:essence_id>", enchant_views.enchant_essence,
         name="enchant_essence"),
    # The alchemy bench (docs/alchemy-contracts.md §8). Lane F's block: every fixed name
    # above the one pattern with a parameter, and all of it above the homebrew benches'
    # `api/bench/<bench_id>` (the herb bench's route-order bug; tests/test_alchemy_api.py
    # pins it).
    path("api/alchemy/state", alchemy_views.alchemy_state, name="alchemy_state"),
    path("api/alchemy/check", alchemy_views.alchemy_check, name="alchemy_check"),
    path("api/alchemy/roll", alchemy_views.alchemy_roll, name="alchemy_roll"),
    path("api/alchemy/finish", alchemy_views.alchemy_finish, name="alchemy_finish"),
    path("api/alchemy/assay", alchemy_views.alchemy_assay, name="alchemy_assay"),
    path("api/alchemy/identify", alchemy_views.alchemy_identify, name="alchemy_identify"),
    path("api/alchemy/learn", alchemy_views.alchemy_learn, name="alchemy_learn"),
    path("api/alchemy/ask", alchemy_views.alchemy_ask, name="alchemy_ask"),
    path("api/alchemy/collect", alchemy_views.alchemy_collect, name="alchemy_collect"),
    path("api/alchemy/perks", alchemy_views.alchemy_perks, name="alchemy_perks"),
    path("api/alchemy/seen", alchemy_views.alchemy_seen, name="alchemy_seen"),
    path("api/alchemy/recipe", alchemy_views.alchemy_recipe, name="alchemy_recipe"),
    path("api/alchemy/formulary", alchemy_views.alchemy_formulary, name="alchemy_formulary"),
    path("api/alchemy/codex", alchemy_views.alchemy_codex, name="alchemy_codex"),
    path("api/alchemy/material/<str:material_id>", alchemy_views.alchemy_material,
         name="alchemy_material"),
    # The herbalism bench (docs/herbalism-contracts.md §3), ABOVE the homebrew benches'
    # `api/bench/<bench_id>`: Django takes the first match, and below it "state" was read
    # as a homebrew bench id and answered 404 "no bench 'state'" (Lane D, 2026-10-02).
    path("api/bench/state", bench_views.bench_state, name="bench_state"),
    path("api/bench/check", bench_views.bench_check, name="bench_check"),
    path("api/bench/roll", bench_views.bench_roll, name="bench_roll"),
    path("api/bench/finish", bench_views.bench_finish, name="bench_finish"),
    path("api/bench/perks", bench_views.bench_perks, name="bench_perks"),
    path("api/bench/recipe", bench_views.bench_recipe, name="bench_recipe"),
    path("api/bench/<str:bench_id>", home_views.bench, name="bench"),
    path("api/worlds", home_views.worlds, name="worlds"),
    path("api/worlds/import", home_views.import_world, name="import_world"),
    path("api/start", home_views.start_in_world, name="start_in_world"),
    path("api/resume", home_views.resume, name="resume"),
    path("api/create/options", home_views.creation_options, name="creation_options"),
    path("api/character/create", home_views.create_character, name="create_character"),
    path("api/character/choices", home_views.character_choices, name="character_choices"),
    path("api/character/delete", home_views.delete_character,
         name="delete_character"),
    path("api/settings/models", home_views.model_settings,
         name="model_settings"),
    # "Make a report for the developer" (Settings): what goes in, the zip, and the two
    # ways to send it. Built server-side; see `play/report.py`.
    path("api/report", report_views.report_zip, name="report_zip"),
    path("api/report/links", report_views.report_links, name="report_links"),
    # First run: what is missing before a turn can be attempted, and the pull that
    # closes the gap. See `play/preflight.py` for why this is a per-launch check
    # rather than a step in the installer.
    path("api/setup", setup_views.setup_state, name="setup_state"),
    path("api/setup/pull", setup_views.setup_pull, name="setup_pull"),
    path("api/setup/install", setup_views.setup_install, name="setup_install"),
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
    path("api/herbarium", herb_views.herbarium, name="herbarium"),
    path("api/herb/study", herb_views.herb_study, name="herb_study"),
    path("api/herb/taste", herb_views.herb_taste, name="herb_taste"),
    path("api/herb/ask", herb_views.herb_ask, name="herb_ask"),
    path("api/herb/library", herb_views.herb_library, name="herb_library"),
    path("api/herb/manual", herb_views.herb_manual, name="herb_manual"),
    path("api/herb/<str:herb_id>", herb_views.herb_card, name="herb_card"),
    # The class builder. A page rather than a bench tab because a class is not a flat
    # form: its level table and its paths are repeating structures, and the effect
    # builder's one-card-per-thing shape cannot hold either.
    path("homebrew/classes/", class_views.class_builder, name="class_builder"),
    path("homebrew/spells/", spell_views.spell_builder, name="spell_builder"),
    path("homebrew/races/", race_views.race_builder, name="race_builder"),
    # Outfitting: the starting gold spent before the sandbox.
    path("outfit/", outfit_views.outfit_page, name="outfit"),
    path("api/outfit/<str:character_id>", outfit_views.outfit_state, name="outfit_state"),
    path("api/outfit/<str:character_id>/buy", outfit_views.outfit_buy, name="outfit_buy"),
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
