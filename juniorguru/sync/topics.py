import re
from collections import Counter

from juniorguru.lib.timer import measure
from juniorguru.lib import loggers
from juniorguru.models import ClubMessage, Topic, db


logger = loggers.get('topics')


KEYWORDS = {re.compile(r'\b' + key + r'\b', re.IGNORECASE): value for key, value in {
    r'pyladies|pylady': 'pyladies',
    r'cs50': 'cs50',
    r'enget\w+': 'engeto',
    r'czechitas': 'czechitas',
    r'(datov\w+|digit\w+) akademi\w+': 'czechitas',
    r'it[ \-]?network': 'itnetwork',
    r'pohovor\w*': 'interviews',
    r'react ?girls': 'reactgirls',
    r'python\w*': 'python',
    r'djang\w+': 'django',
    r'php': 'php',
    r'p[ée]h[aá]pk\w+': 'php',
    r'\w*sql\w*': 'sql',
    r'nette': 'nette',
    r'sym(f|ph)ony': 'symfony',
    r'laravel\w*': 'laravel',
    r'js': 'javascript',
    r'javascript\w*': 'javascript',
    r'flask\w*': 'flask',
    r'react\w*': 'react',
    r'vue': 'vue',
    r'linux\w*': 'linux',
    r'bash\w*': 'linux',
    r'příkaz\w*': 'linux',
    r'docker\w*': 'docker',
    r's?css': 'css',
    r'git\w*': 'git',
    r'github\w*': 'github',
    r'oop': 'oop',
    r'wordpress\w*': 'wordpress',
    r'aoc': 'adventofcode',
    r'advent ?of ?code': 'adventofcode',
    r'100 ?days ?of ?code': '100daysofcode',
    r'sdacademy': 'sdacademy',
    r'sda': 'sdacademy',
    r'software development a[ck]adem\w+': 'sdacademy',
    r'udemy': 'udemy',
    r'learn2code': 'learn2code',
    r'l2c': 'learn2code',
    r'prima ?kurzy': 'primakurzy',
    r'kurzy\.vsb': 'vsb',
    r'všb': 'vsb',
    r'django ?girls': 'djangogirls',
    r'coding ?boo?tcamp( pra(ha|gue))?': 'codingbootcamppraha',
    r'data4you': 'codingbootcamppraha',
    r'testov[aá]\w*': 'testing',
    r'testing': 'testing',
    r'teste[rř]\w*': 'testing',
    r'dat(a|ař\w*|ov\w+)': 'data',
    r'codility': 'codility',
    r'open[ \-]?sourc\w+': 'opensource',
    r'green ?fox( academy| akademi[ei])?': 'greenfox',
    r'gfa': 'greenfox',
    r'unicorn\w*': 'unicorn',
    r'(it\s*)?step(\.org)?': 'step',
    r'c(\#|sharp\w*)': 'csharp',
    r'jav(a|ou|ista|istka|isti|istky|e|ě)': 'java',
    # r'kotlin\w+': 'kotlin',
    # r'android\w+': 'android',
}.items()}

TOPIC_CHANNELS = {re.compile(key): value for key, value in {
    r'mentoring': 'mentoring',
    r'^pohovory$': 'interviews',
    r'^php$': 'php',
    r'^python$': 'python',
    r'^100daysofcode$': '100daysofcode',
    r'^adventofcode$': 'adventofcode',
    # r'^java$': 'java',
}.items()}


@measure('topics')
def main():
    with db:
        Topic.drop_table()
        Topic.create_table()

    topics = {}
    with db:
        messages = ClubMessage.listing()
    for message in messages:
        topic_channel_keyword = get_topic_channel_keyword(message.channel_name)
        if topic_channel_keyword:
            topics.setdefault(topic_channel_keyword, Counter())
            topics[topic_channel_keyword]['topic_channels_messages_count'] += 1

        for keyword_re, keyword in KEYWORDS.items():
            if keyword_re.search(message.content):
                topics.setdefault(keyword, Counter())
                topics[keyword]['mentions_count'] += 1
    with db:
        for name, data in topics.items():
            logger.info(f"{name} {dict(data)}")
            Topic.create(**{'name': name, **data})


def get_topic_channel_keyword(channel_name):
    for keyword_re, keyword in TOPIC_CHANNELS.items():
        if keyword_re.search(channel_name):
            return keyword
    return None


if __name__ == '__main__':
    main()
