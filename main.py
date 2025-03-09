from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.event import SystemExitEvent
from ulauncher.api.shared.event import PreferencesUpdateEvent
from ulauncher.api.shared.event import PreferencesEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction
from ulauncher.api.shared.action.OpenUrlAction import OpenUrlAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from firefox import FirefoxDatabase

import re
import urllib.parse


class FirefoxExtension(Extension):
    def __init__(self):
        super(FirefoxExtension, self).__init__()

        #   Firefox database object
        self.database = FirefoxDatabase()

        #   Ulauncher Events
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(SystemExitEvent, SystemExitEventListener())
        self.subscribe(PreferencesEvent, PreferencesEventListener())
        self.subscribe(PreferencesUpdateEvent, PreferencesUpdateEventListener())


class PreferencesEventListener(EventListener):
    def on_event(self, event: PreferencesEvent, extension: FirefoxExtension):
        #   Results Order
        extension.database.order = event.preferences["order"]
        #   Results Number
        try:
            n = int(event.preferences["limit"])
        except:
            n = 10
        extension.database.limit = n


class PreferencesUpdateEventListener(EventListener):
    def on_event(self, event: PreferencesUpdateEvent, extension: FirefoxExtension):
        #   Results Order
        if event.id == "order":
            extension.database.order = event.new_value
        #   Results Number
        elif event.id == "limit":
            try:
                n = int(event.new_value)
                extension.database.limit = n
            except:
                pass


class SystemExitEventListener(EventListener):
    def on_event(self, _: SystemExitEvent, extension: FirefoxExtension):
        extension.database.close()


class KeywordQueryEventListener(EventListener):

    def _parse_url(self, query, default_protocol="https"):
        m = re.match(
            r"^(?:([a-z-A-Z]+)://)?([a-zA-Z0-9/-_]+\.[a-zA-Z0-9/-_\.]+)(?:\?(.*))?$",
            query,
        )
        url = ""
        if m:
            protocol = default_protocol
            if m.group(1):
                protocol = m.group(1)
            base = m.group(2)
            params = m.group(3)
            encoded = f"?{urllib.parse.quote(params)}" if params else ""
            url = f"{protocol}://{base}{encoded}"
        return url

    def on_event(self, event: KeywordQueryEvent, extension: FirefoxExtension):
        query = event.get_argument() if event.get_argument() else ""
        items = []

        #    Open website
        desc = ""
        action = None
        url = self._parse_url(query)

        if url:
            desc = url
            action = OpenUrlAction(url)
        else:
            desc = "Type in a valid URL and press Enter..."
            action = DoNothingAction()

        items.append(
            ExtensionResultItem(
                icon="images/icon.png",
                name="Open URL",
                description=desc,
                on_enter=action,
            )
        )

        #   Search Firefox bookmarks and history
        results = extension.database.search(query)

        for link in results:
            url = link[0]
            title = link[1] if link[1] else url

            if url != query:
                items.append(
                    ExtensionResultItem(
                        icon="images/icon.png",
                        name=title,
                        description=url,
                        on_enter=OpenUrlAction(url),
                        on_alt_enter=SetUserQueryAction(
                            f'{extension.preferences["kw"]} {url}'
                        ),
                    )
                )

        return RenderResultListAction(items)


if __name__ == "__main__":
    FirefoxExtension().run()
