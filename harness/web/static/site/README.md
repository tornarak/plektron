# Site marks

Third-party logos, used as link marks on outbound references in the reading
view. Not this project's work and not under its licence.

Both were downloaded from Wikimedia Commons rather than drawn here, and the
distinction matters: a hand-approximated logo is a wrong logo, and these are
trademarks whose whole function is to be recognised.

| file | source | notes |
|---|---|---|
| `wikipedia.svg` | [Wikipedia's W](https://commons.wikimedia.org/wiki/File:Wikipedia%27s_W.svg) | Trademark of the Wikimedia Foundation. Used nominatively, to mark a link that goes to Wikipedia. Given `fill="currentColor"` so it follows the page's text colour in both themes. |
| `wikidata.svg` | [Wikidata logo](https://commons.wikimedia.org/wiki/File:Wikidata-logo.svg) | Trademark of the Wikimedia Foundation. Brand colours kept — a logo recoloured is not the logo. |

Both gained a `viewBox` so they scale from CSS; nothing else was changed.

`edition_ui.LINK_KINDS` maps a record's `link:` prefix to the address and the
mark, so the entity files hold identifiers (`wikipedia:Chukchi_people`) and never
URLs.
