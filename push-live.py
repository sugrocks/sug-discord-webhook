import os
import sys
import json
import configparser
import urllib.error
import urllib.parse
import urllib.request
from time import sleep
import basc_py4chan as fch
from collections import deque
from datetime import datetime

relconf = 0
firstrun = True

config = configparser.ConfigParser()
watching = deque('')

co = fch.Board('co', True)
trash = fch.Board('trash', True)


def status_print(text):
    sys.stdout.write('\r[{0}] {1}'.format(str(datetime.now()), str(text)))


def push_thread(thread, edition=''):
    if edition == '':
        edition = '/sug/ no.' + thread.topic.post_id

    post = thread.topic
    image = {}
    footer = {}

    if post.file.file_extension != 'webm' and not post.spoiler:
        image = {
            'url': post.file.file_url
        }
    elif post.file.file_extension == 'webm':
        footer = {
            'text': '(A webm is attached)',
            'icon_url': 'https://s.kdy.ch/4ch-warning.png'
        }
    elif post.spoiler:
        footer = {
            'text': '(Image is spoiled)',
            'icon_url': 'https://s.kdy.ch/4ch-warning.png'
        }

    data = {
        'username': '/' + thread._board.name + '/',
        'embeds': [
            {
                'title': 'New thread: ' + edition,
                'color': 3518996,
                'url': thread.url,
                'footer': footer,
                'image': image
            }
        ]
    }

    params = json.dumps(data).encode('utf8')
    headers = {
        'content-type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; sug/1.0)'
    }

    for hook in dict(config.items('new')):
        url = "https://discordapp.com/api/webhooks/%s/%s" % (hook, config.get('new', hook))
        req = urllib.request.Request(url, data=params, headers=headers)

        try:
            response = urllib.request.urlopen(req)
        except:
            try:
                sleep(3)
                response = urllib.request.urlopen(req)
            except:
                continue

        rep = response.read().decode('utf8')
        if rep != '':
            print('\n' + rep)


def push_post(post, edition=''):
    if edition == '':
        edition = '/sug/ no.' + post._thread.topic.post_id

    image = {}
    footer = {}

    if post.has_file and post.file.file_extension != 'webm' and not post.spoiler:
        image = {
            'url': post.file.file_url
        }
    elif post.has_file and post.file.file_extension == 'webm':
        footer = {
            'text': '(A webm is attached)',
            'icon_url': 'https://s.kdy.ch/4ch-warning.png'
        }
    elif post.spoiler:
        footer = {
            'text': '(Image is spoiled)',
            'icon_url': 'https://s.kdy.ch/4ch-warning.png'
        }

    data = {
        'username': '/' + post._thread._board.name + '/',
        'embeds': [
            {
                'title': post.name + ' - No.' + str(post.post_id) + ' (' + edition + ')',
                'description': post.text_comment,
                'color': 3518996,
                'url': post.url,
                'footer': footer,
                'image': image
            }
        ]
    }

    params = json.dumps(data).encode('utf8')
    headers = {
        'content-type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; sug/1.0)'
    }

    for hook in dict(config.items(post._thread._board.name)):
        url = "https://discordapp.com/api/webhooks/%s/%s" % (hook, config.get(post._thread._board.name, hook))
        req = urllib.request.Request(url, data=params, headers=headers)

        try:
            response = urllib.request.urlopen(req)
        except:
            try:
                sleep(3)
                response = urllib.request.urlopen(req)
            except:
                continue

        rep = response.read().decode('utf8')
        if rep != '':
            print('\n' + rep)


def check_config():
    global relconf

    if relconf > 60:
        relconf = 0
    if relconf == 0:
        config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))


def check_sug():
    global relconf, firstrun

    req = urllib.request.Request('https://api.sug.rocks/threads.json')
    r = urllib.request.urlopen(req).read()
    cont = json.loads(r.decode('utf-8'))
    for item in cont:
        if item['board'] != 'sugen' and not item['status']['archived']:
            if not any(x['id'] == item['id'] for x in watching):
                try:
                    if item['board'] == 'co':
                        thread = co.get_thread(int(item['id']), False, True)
                    elif item['board'] == 'trash':
                        thread = trash.get_thread(int(item['id']), False, True)

                    print('\nAdded: ' + item['edition'])
                    watching.append({'id': item['id'], 'edition': item['edition'], 'thread': thread})
                    if not firstrun:
                        push_thread(thread, item['edition'])
                except:
                    pass
    firstrun = False


def check_threads():
    toremove = []
    for w in watching:
        upcount = w['thread'].update()
        if not hasattr(w['thread'], 'topic'):
            toremove.append(w)
            print('\n' + str(w['id']) + ' will be removed')
        else:
            if upcount > 0:
                status_print(str(w['id']) + ': ' + str(upcount) + ' new posts')
                newposts = w['thread'].all_posts[-upcount:]
                for post in newposts:
                    push_post(post, w['edition'])

    for r in toremove:
        watching.remove(r)


if __name__ == '__main__':
    while True:
        check_config()
        check_sug()
        check_threads()
        relconf += 1
        sleep(5)
