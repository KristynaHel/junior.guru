---
title: "Diskutuj o #100daysofcode"
template: main_legacy.html
topic_name: 100daysofcode
topic_link_text: "#100daysofcode"
description: "Chystáš se pracovat na #100daysofcode? Hledáš kamarády, se kterými se budeš hecovat a kterým se můžeš pochlubit svým řešením? Chceš jednotlivé výtvory probrat s někým zkušenějším?"
---
{% from 'macros_topic.html' import intro, mentions, members_roll with context %}

{{ intro('Řešit #100daysofcode sám je nuda', page.meta.description) }}

{{ mentions(topic, '#100daysofcode') }}

{{ members_roll(pages, members, members_total_count, club_elapsed_months) }}
