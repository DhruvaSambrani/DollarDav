import os
import subprocess
import tempfile

import vobject
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import (Button, Footer, Header, Label, ListItem, ListView,
                             Markdown)


def util_file(text):
    tmp = tempfile.NamedTemporaryFile(mode="w+", suffix=".md")
    tmp.write(text)
    tmp.flush()
    process = subprocess.Popen(
        [os.environ.get("EDITOR", "xdg-open"), tmp.name])
    process.wait()
    tmp.seek(0)
    return tmp.readlines()


def util_get_notes(DIRPATH):
    notes = []
    for f in filter(lambda x: ".ics" in x, os.listdir(DIRPATH)):
        PATH = DIRPATH+"/"+f
        try:
            vobj = vobject.readOne(open(PATH))
            vobj.vjournal
            notes.append(Note(PATH, vobj))
        except AttributeError:
            pass
    return notes


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Screen with a dialog to quit."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to delete note?", id="question"),
            Button("[u]Y[/u]es", variant="error", id="del"),
            Button("Ca[u]n[/u]cel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_key(self, event: events.Key) -> None:
        if event.key == "y":
            self.query_one("#del").action_press()
        if event.key == "n":
            self.query_one("#cancel").action_press()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(result=event.button.id == "del")


class NotesApp(App):
    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("n", "new_note", "New Note"),
        ("i", "edit", "Edit"),
        ("d", "request_del_note", "Delete Note"),
        ("q", "request_quit", "Quit")
    ]
    CSS_PATH = "main.css"

    def __init__(self, DIRPATH):
        super().__init__()
        self.DIRPATH = DIRPATH
        self.container = ListView(classes="listbox")
        self.textbox = Markdown("", classes="textbox")
        self.title = "NotesApp"
        self.sub_title = ".ics notes"

    async def on_mount(self):
        await self.update_container(True)
        self.update_text()

    def update_text(self):
        self.textbox.update(self.notes[self.container.index].markdown())

    async def update_container(self, re_read):
        if re_read:
            self.notes = util_get_notes(self.DIRPATH)
        self.container.clear()
        for li in map(lambda x: ListItem(Label(x.summary())), self.notes):
            await self.container.append(li)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        yield self.container
        yield self.textbox

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    def action_cursor_up(self) -> None:
        self.container.action_cursor_up()
        self.update_text()

    def action_cursor_down(self) -> None:
        self.container.action_cursor_down()
        self.update_text()

    async def action_edit(self) -> None:
        self._driver.stop_application_mode()
        try:
            self.notes[self.container.index].edit()
        finally:
            await self.update_container(False)
            self.refresh()
            self._driver.start_application_mode()

    async def del_note(self, confirm: bool):
        if confirm:
            self.notes[self.container.index].delete()
            await self.update_container(True)

    def action_request_del_note(self):
        self.push_screen(ConfirmDeleteScreen(), callback=self.del_note)

    async def action_new_note(self):
        rawcal = vobject.iCalendar()
        rawcal.add("vjournal")
        self._driver.stop_application_mode()
        newtext = util_file("SUMMARY\nDESCRIPTION FROM HERE")
        rawcal.vjournal.add("summary").value = newtext[0].strip()
        rawcal.vjournal.add("description").value = "".join(newtext[1:]).strip()
        newcal = vobject.readOne(rawcal.serialize())
        n = Note(self.DIRPATH+"/"+newcal.vjournal.uid.value+".ics", newcal)
        self.notes.append(n)
        await self.update_container(False)
        self.refresh()
        self._driver.start_application_mode()

    def action_request_quit(self):
        for n in self.notes:
            n.write()
        self.app.exit()


class Note:
    def __init__(self, path, vobj) -> None:
        self.vobj = vobj
        self.path = path
        try:
            self.vobj.vjournal.description
        except AttributeError:
            self.vobj.vjournal.add("description").value = "No description"

    def summary(self):
        return self.vobj.vjournal.summary.value

    def description(self):
        return self.vobj.vjournal.description.value

    def markdown(self):
        return "# " + self.summary() + "\n\n" + self.description()

    def edit(self):
        newtext = util_file(self.summary()+"\n"+self.description())
        self.vobj.vjournal.summary.value = newtext[0].strip()
        self.vobj.vjournal.description.value = "".join(newtext[1:]).strip()

    def delete(self):
        os.remove(self.path)

    def write(self):
        print(self.path)
        with open(self.path, "w") as f:
            f.write(self.vobj.serialize())
            f.flush()


if __name__ == "__main__":
    PATH = "/home/dhruva/.calendars/personal/0d12521a-5702-7828-c1c2-98e14486af54"
    app = NotesApp(PATH)
    app.run()
