---
title: Laravel mentoring
template: main_legacy.html
topic_name: laravel
topic_link_text: Laravel
description: Učíš se Laravel? Hledáš někoho zkušenějšího, kdo ti poradí, když se zasekneš? Kdo ti ukáže správné postupy a nasměruje tě na kvalitní návody nebo kurzy?
---
{% from 'topic.html' import intro, mentions, members_roll %}

{{ intro('Nech si poradit s Laravelem', page.meta.description) }}

{{ mentions(topic, 'Laravelu') }}

{{ members_roll(pages, members, members_total_count, club_elapsed_months) }}
