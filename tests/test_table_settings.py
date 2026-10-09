"""Settings from the table, without leaving the game.

The owner, 2026-10-05: "add a button for settings to the table screen as it is now i have to
go to the main page then to settings." The table had Music and Hide sheet in its top bar and
no way to Settings but back to the shelf. The button opens the shelf's own Settings page in a
panel over the game, so there is one Settings page, not a second copy that drifts.
"""
from __future__ import annotations

from pathlib import Path

TABLE = Path("play/templates/play/table.html")
HOME = Path("play/templates/play/home.html")
SHELL = Path("play/static/js/table/12-shell.js")


def test_the_table_has_a_settings_button_and_a_panel_over_the_game():
    html = TABLE.read_text(encoding="utf-8")
    assert 'id="settingsbtn"' in html and 'aria-controls="settingslayer"' in html
    assert 'id="settingslayer"' in html and 'role="dialog"' in html
    assert '<iframe id="settingsframe"' in html


def test_the_button_opens_the_shelfs_own_settings_embedded():
    js = SHELL.read_text(encoding="utf-8")
    # Built in a variable since 2026-10-08, so a stalled model's "Make a report" can open
    # the same page already unfolded on the report (`&report=1`).
    assert 'let src = "/?tab=settings&embed=1";' in js and "frame.src = src;" in js
    # Esc inside the frame never reaches the table; the page posts this instead.
    assert 'e.data.pgm === "close-settings"' in js and "btn.focus();" in js


def test_the_shelf_opens_on_settings_and_hides_its_chrome_when_embedded():
    html = HOME.read_text(encoding="utf-8")
    assert 'QUERY.get("tab") === "settings"' in html
    assert 'document.body.classList.add("embedded")' in html
    assert "body.embedded > header" in html
    assert 'pgm: "close-settings"' in html


def test_arriving_on_settings_loads_the_model_settings():
    """Seen live, 2026-10-05: the panel showed only "Sound and motion" for good. The page
    fetched the model settings on load only when the setup redirect sent it there
    (`SENT_TO_SETUP`); arriving by `?tab=settings` skipped the fetch, so the pane sat on
    "Reading the model settings..." forever, the trap the comment above it describes."""
    html = HOME.read_text(encoding="utf-8")
    assert 'if (TAB === "settings" && !SETTINGS) {\n  fetch("/api/settings/models")' in html
    assert 'if (TAB === "settings" && !LAN) lanFetch("/api/lan");' in html
