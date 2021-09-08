---
title: JavaScript mentoring
template: main_legacy.html
topic_name: javascript
topic_link_text: JavaScript
description: Učíš se JavaScript? Hledáš někoho zkušenějšího, kdo ti poradí, když se zasekneš? Kdo ti ukáže správné postupy a nasměruje tě na kvalitní návody nebo kurzy?
---
{% from 'topic.html' import intro, mentions, members_roll with context %}

{{ intro('Nech si poradit s JavaScriptem', page.meta.description) }}

{{ mentions(topic, 'JavaScriptu') }}

{{ members_roll(pages, members, members_total_count, club_elapsed_months) }}
