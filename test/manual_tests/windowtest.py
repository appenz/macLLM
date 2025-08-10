import os
import sys

# Ensure project root is on sys.path when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from macllm.macllm import create_macllm
from macllm.models.fake_connector import FakeConnector
from PyObjCTools import AppHelper

user = "What is the capital of France?"
agent = "The capital of France is Paris."
context = "France,[h] officially the French Republic,[i] is a country primarily located in Western Europe. Its overseas regions and territories include French Guiana in South America, Saint Pierre and Miquelon in the North Atlantic, the French West Indies, and many islands in Oceania and the Indian Ocean, giving it one of the largest discontiguous exclusive economic zones in the world. Metropolitan France shares borders with Belgium and Luxembourg to the north; Germany to the northeast; Switzerland to the east; Italy and Monaco to the southeast; Andorra and Spain to the south; and a maritime border with the United Kingdom to the northwest. Its metropolitan area extends from the Rhine to the Atlantic Ocean and from the Mediterranean Sea to the English Channel and the North Sea. Its eighteen integral regions—five of which are overseas—span a combined area of 632,702 km2 (244,288 sq mi) and have an estimated total population of over 68.6 million as of January 2025. France is a semi-presidential republic. Its capital, largest city and main cultural and economic centre is Paris."


def main():
    app = create_macllm(debug=True, start_ui=False)
    app.llm = FakeConnector()

    app.chat_history.add_chat_entry("user", user, user)
    app.chat_history.add_chat_entry("assistant", agent, agent)
    app.chat_history.add_context("clipboard", "clipboard-1", "clipboard", context, icon="📋")
    app.chat_history.add_context("file", "file-1.txt", "file", context, icon="📁")
#    app.chat_history.add_context("clipboard", "clipboard-2", "clipboard", context, icon="📋")
#    app.chat_history.add_context("file", "file-2.txt", "file", context, icon="📁")
#    app.chat_history.add_context("clipboard", "clipboard-3", "clipboard", context, icon="📋")
#    app.chat_history.add_context("file", "file-3.txt", "file", context, icon="📁")
#    app.chat_history.add_context("clipboard", "clipboard-4", "clipboard", context, icon="📋")
#    app.chat_history.add_context("file", "file-4.txt", "file", context, icon="📁")

    app.ui.start(dont_run_app=True)
    app.ui.hotkey_pressed()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()

